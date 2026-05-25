import email
import imaplib
import logging
import os
import re
from datetime import datetime, timedelta
from email.header import decode_header
from urllib.parse import urlparse

from flask import Flask, jsonify, request, session
from flask_cors import CORS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "change-me-in-railway")

mail_connection = None
connected_email = None
trash_folder_cache = None


def app_info():
    return {"ok": True, "app": "Carla's Awesome Yahoo Cleaner That Gus is Allowed to Use", "version": "v2.3"}


@app.route("/")
@app.route("/health")
@app.route("/api/health")
def health():
    return jsonify(app_info())


def decode_email_header(header):
    if header is None:
        return ""
    try:
        parts = []
        for content, charset in decode_header(header):
            if isinstance(content, bytes):
                parts.append(content.decode(charset or "utf-8", errors="replace"))
            else:
                parts.append(str(content))
        return "".join(parts)
    except Exception:
        return str(header)


def get_email_body(msg):
    body = ""
    html = ""
    try:
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_disposition() == "attachment":
                    continue
                payload = part.get_payload(decode=True)
                if not payload:
                    continue
                text = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
                if part.get_content_type() == "text/plain" and not body:
                    body = text
                elif part.get_content_type() == "text/html" and not html:
                    html = text
        else:
            payload = msg.get_payload(decode=True)
            if payload:
                body = payload.decode(msg.get_content_charset() or "utf-8", errors="replace")
    except Exception as exc:
        logger.warning("Body parse failed: %s", exc)
    text = body or html
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def extract_urls(text):
    return re.findall(r"https?://[^\s\"'<>]+", text or "")


def find_unsubscribe_links(text):
    terms = ["unsubscribe", "opt-out", "optout", "email-preferences", "manage-subscription", "unsub"]
    links = []
    for url in extract_urls(text):
        parsed = urlparse(url)
        haystack = f"{url} {parsed.netloc} {parsed.path}".lower()
        if any(term in haystack for term in terms):
            links.append(url)
    return list(dict.fromkeys(links))[:5]


def sender_domain(sender):
    match = re.search(r"<([^>]+)>", sender or "")
    address = match.group(1) if match else sender or ""
    return address.split("@")[-1].lower().strip() if "@" in address else ""


def imap_date(days_ago):
    return (datetime.now() - timedelta(days=days_ago)).strftime("%d-%b-%Y")


def connected():
    return mail_connection is not None


def select_inbox():
    if not connected():
        return False
    try:
        status, _ = mail_connection.select("INBOX")
        return status == "OK"
    except Exception:
        return False


def parse_folder_name(raw_folder):
    text = raw_folder.decode(errors="replace") if isinstance(raw_folder, bytes) else str(raw_folder)
    match = re.search(r'"([^"]+)"\s*$', text)
    return match.group(1) if match else text.split(" ")[-1].strip('"')


def list_folder_names():
    status, folders = mail_connection.list()
    if status != "OK" or not folders:
        return []
    return [parse_folder_name(folder) for folder in folders]


def find_trash_folder():
    global trash_folder_cache
    if trash_folder_cache:
        return trash_folder_cache
    folders = list_folder_names()
    for wanted in ["Trash", "Deleted", "Deleted Items", "INBOX/Trash", "Bulk Mail/Trash"]:
        for folder in folders:
            if folder.lower() == wanted.lower():
                trash_folder_cache = folder
                return folder
    for folder in folders:
        if "trash" in folder.lower() or "deleted" in folder.lower():
            trash_folder_cache = folder
            return folder
    trash_folder_cache = "Trash"
    return trash_folder_cache


def search_ids(*criteria):
    try:
        status, messages = mail_connection.search(None, *criteria)
        if status != "OK" or not messages or not messages[0]:
            return []
        return messages[0].split()
    except Exception as exc:
        logger.warning("Yahoo search failed for %s: %s", criteria, exc)
        return []


def quote_criteria(criteria):
    quoted = []
    quote_after = {"SUBJECT", "FROM", "TEXT", "TO", "CC", "BCC"}
    previous = None
    for part in criteria:
        if previous in quote_after and not str(part).startswith('"'):
            quoted.append(f'"{part}"')
        else:
            quoted.append(part)
        previous = part
    return quoted


def unique_ids(groups):
    seen = set()
    results = []
    for group in groups:
        for msg_id in group:
            key = msg_id.decode() if isinstance(msg_id, bytes) else str(msg_id)
            if key not in seen:
                seen.add(key)
                results.append(msg_id)
    return results


def recipe_searches(name):
    recipes = {
        "verification_codes": [("SUBJECT", "verification"), ("SUBJECT", "verify"), ("SUBJECT", "code"), ("SUBJECT", "passcode"), ("SUBJECT", "login code"), ("SUBJECT", "security code")],
        "password_resets": [("SUBJECT", "password"), ("SUBJECT", "reset"), ("SUBJECT", "recover"), ("SUBJECT", "account access"), ("SUBJECT", "sign-in"), ("SUBJECT", "login")],
        "receipts": [("SUBJECT", "receipt"), ("SUBJECT", "invoice"), ("SUBJECT", "order confirmation"), ("SUBJECT", "payment"), ("SUBJECT", "purchase"), ("SUBJECT", "your order")],
        "shipping": [("SUBJECT", "ship"), ("SUBJECT", "shipped"), ("SUBJECT", "shipping"), ("SUBJECT", "delivery"), ("SUBJECT", "delivered"), ("SUBJECT", "tracking")],
        "carts": [("SUBJECT", "cart"), ("SUBJECT", "checkout"), ("SUBJECT", "left something"), ("SUBJECT", "still interested")],
        "newsletters": [("SUBJECT", "newsletter"), ("SUBJECT", "digest"), ("SUBJECT", "weekly"), ("SUBJECT", "roundup"), ("SUBJECT", "updates")],
        "promotions": [("SUBJECT", "sale"), ("SUBJECT", "deal"), ("SUBJECT", "coupon"), ("SUBJECT", "offer"), ("SUBJECT", "limited time"), ("SUBJECT", "clearance"), ("SUBJECT", "save"), ("SUBJECT", "discount")],
        "trials": [("SUBJECT", "trial"), ("SUBJECT", "expires"), ("SUBJECT", "expired"), ("SUBJECT", "renew"), ("SUBJECT", "subscription")],
        "social": [("SUBJECT", "follow"), ("SUBJECT", "liked"), ("SUBJECT", "mentioned"), ("SUBJECT", "tagged"), ("SUBJECT", "comment"), ("FROM", "facebook"), ("FROM", "instagram"), ("FROM", "linkedin")],
        "noreply": [("FROM", "noreply"), ("FROM", "no-reply"), ("FROM", "donotreply"), ("FROM", "do-not-reply")],
        "old_unread_1y": [("UNSEEN", "BEFORE", imap_date(365))],
        "old_unread_2y": [("UNSEEN", "BEFORE", imap_date(730))],
        "old_read_2y": [("SEEN", "BEFORE", imap_date(730))],
        "old_read_5y": [("SEEN", "BEFORE", imap_date(1825))],
        "old_promotions_6m": [("SUBJECT", "sale", "BEFORE", imap_date(180)), ("SUBJECT", "coupon", "BEFORE", imap_date(180)), ("SUBJECT", "deal", "BEFORE", imap_date(180)), ("SUBJECT", "offer", "BEFORE", imap_date(180))],
        "old_receipts_2y": [("SUBJECT", "receipt", "BEFORE", imap_date(730)), ("SUBJECT", "invoice", "BEFORE", imap_date(730)), ("SUBJECT", "order", "BEFORE", imap_date(730))],
    }
    return recipes.get(name)


def run_recipe(name):
    searches = recipe_searches(name)
    if searches is None:
        return None
    return unique_ids([search_ids(*quote_criteria(criteria)) for criteria in searches])


def fetch_header_message(msg_id):
    fetch_patterns = [
        "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])",
        "(BODY[HEADER.FIELDS (FROM SUBJECT DATE)])",
        "(RFC822.HEADER)",
    ]
    for pattern in fetch_patterns:
        try:
            status, data = mail_connection.fetch(msg_id, pattern)
            if status == "OK" and data:
                for part in data:
                    if isinstance(part, tuple) and part[1]:
                        return email.message_from_bytes(part[1])
        except Exception as exc:
            logger.warning("Header fetch failed for %s using %s: %s", msg_id, pattern, exc)
    return None


def summarize_email(msg_id, matched_by=None):
    status, data = mail_connection.fetch(msg_id, "(RFC822)")
    if status != "OK" or not data:
        return None
    msg = None
    for part in data:
        if isinstance(part, tuple) and part[1]:
            msg = email.message_from_bytes(part[1])
            break
    if msg is None:
        return None
    subject = decode_email_header(msg.get("Subject", ""))
    sender = decode_email_header(msg.get("From", ""))
    body = get_email_body(msg)
    links = find_unsubscribe_links(body)
    return {"id": msg_id.decode() if isinstance(msg_id, bytes) else str(msg_id), "subject": subject, "sender": sender, "sender_domain": sender_domain(sender), "date": msg.get("Date", ""), "snippet": body[:240] if body else "(No content)", "has_unsubscribe": bool(links), "unsubscribe_links": links, "matched_by": matched_by or "Search result"}


def move_to_trash(msg_id):
    folder = find_trash_folder()
    try:
        status, _ = mail_connection.move(str(msg_id), folder)
        if status == "OK":
            return True, folder, None
    except Exception as exc:
        logger.warning("MOVE failed for %s: %s", msg_id, exc)
    try:
        status, _ = mail_connection.copy(str(msg_id), folder)
        if status == "OK":
            mail_connection.store(str(msg_id), "+FLAGS", "\\Deleted")
            mail_connection.expunge()
            return True, folder, None
        return False, folder, f"COPY returned {status}"
    except Exception as exc:
        return False, folder, str(exc)


@app.route("/api/connect", methods=["POST"])
def connect():
    global mail_connection, connected_email, trash_folder_cache
    data = request.get_json() or {}
    email_address = data.get("email")
    password = data.get("password")
    if not email_address or not password:
        return jsonify({"success": False, "error": "Email and app password required"}), 400
    try:
        mail = imaplib.IMAP4_SSL("imap.mail.yahoo.com", 993)
        mail.login(email_address, password)
        mail.select("INBOX")
        mail_connection = mail
        connected_email = email_address
        trash_folder_cache = None
        session["connected"] = True
        session["email"] = email_address
        return jsonify({"success": True, "email": email_address, "message": f"Connected to {email_address}"})
    except imaplib.IMAP4.error as exc:
        return jsonify({"success": False, "error": f"Yahoo authentication failed. Use a Yahoo app password. Details: {exc}"}), 401
    except Exception as exc:
        return jsonify({"success": False, "error": f"Connection failed: {exc}"}), 500


@app.route("/api/status")
def status():
    global mail_connection, connected_email
    if mail_connection is None:
        return jsonify({"connected": False})
    try:
        mail_connection.noop()
        return jsonify({"connected": True, "email": connected_email})
    except Exception:
        mail_connection = None
        connected_email = None
        return jsonify({"connected": False})


@app.route("/api/disconnect", methods=["POST"])
def disconnect():
    global mail_connection, connected_email, trash_folder_cache
    if mail_connection:
        try:
            mail_connection.logout()
        except Exception:
            pass
    mail_connection = None
    connected_email = None
    trash_folder_cache = None
    session.clear()
    return jsonify({"success": True})


@app.route("/api/folders")
def folders():
    if not connected():
        return jsonify({"error": "Not connected"}), 401
    try:
        return jsonify({"folders": list_folder_names(), "trash_folder": find_trash_folder()})
    except Exception as exc:
        return jsonify({"folders": [], "trash_folder": "Trash", "warning": str(exc)})


@app.route("/api/search", methods=["POST"])
def search():
    if not connected():
        return jsonify({"error": "Not connected"}), 401
    data = request.get_json() or {}
    limit = min(int(data.get("limit", 75)), 200)
    criteria = []
    if data.get("sender"):
        criteria += ["FROM", f'"{data["sender"]}"']
    if data.get("subject"):
        criteria += ["SUBJECT", f'"{data["subject"]}"']
    if data.get("query"):
        criteria += ["TEXT", f'"{data["query"]}"']
    if data.get("read_state") == "unread":
        criteria.append("UNSEEN")
    if data.get("read_state") == "read":
        criteria.append("SEEN")
    if data.get("before"):
        criteria += ["BEFORE", datetime.strptime(data["before"], "%Y-%m-%d").strftime("%d-%b-%Y")]
    if data.get("since"):
        criteria += ["SINCE", datetime.strptime(data["since"], "%Y-%m-%d").strftime("%d-%b-%Y")]
    if not criteria:
        criteria = ["ALL"]
    select_inbox()
    ids = list(reversed(search_ids(*criteria)))
    emails = [item for msg_id in ids[:limit] if (item := summarize_email(msg_id, "Manual search"))]
    return jsonify({"emails": emails, "total": len(ids), "shown": len(emails)})


@app.route("/api/quick-pick/<name>")
def quick_pick(name):
    if not connected():
        return jsonify({"error": "Not connected"}), 401
    limit = min(request.args.get("limit", 75, type=int), 200)
    select_inbox()
    ids = run_recipe(name)
    if ids is None:
        return jsonify({"error": f"Unknown quick-pick recipe: {name}"}), 400
    ordered = ids if name.startswith("old_") else list(reversed(ids))
    emails = [item for msg_id in ordered[:limit] if (item := summarize_email(msg_id, name.replace("_", " ")))]
    return jsonify({"emails": emails, "total": len(ids), "shown": len(emails), "recipe": name})


@app.route("/api/quick-pick-counts")
def quick_pick_counts():
    if not connected():
        return jsonify({"counts": {}}), 401
    names = ["verification_codes", "password_resets", "receipts", "shipping", "carts", "newsletters", "promotions", "trials", "social", "noreply", "old_unread_1y", "old_unread_2y", "old_read_2y", "old_read_5y", "old_promotions_6m", "old_receipts_2y"]
    select_inbox()
    return jsonify({"counts": {name: len(run_recipe(name) or []) for name in names}})


@app.route("/api/move-to-trash", methods=["POST"])
def move_selected_to_trash():
    if not connected():
        return jsonify({"error": "Not connected"}), 401
    ids = (request.get_json() or {}).get("email_ids", [])
    if not ids:
        return jsonify({"error": "No messages selected"}), 400
    select_inbox()
    moved = 0
    failed = []
    folder = find_trash_folder()
    for msg_id in ids:
        ok, folder, err = move_to_trash(msg_id)
        if ok:
            moved += 1
        else:
            failed.append({"id": msg_id, "error": err})
    return jsonify({"success": len(failed) == 0, "moved": moved, "deleted": moved, "failed": failed, "trash_folder": folder, "message": f"Moved {moved} message(s) to {folder}."})


@app.route("/api/delete", methods=["POST"])
def legacy_delete_alias():
    return move_selected_to_trash()


@app.route("/api/top-senders")
def top_senders():
    if not connected():
        return jsonify({"error": "Not connected"}), 401
    limit = min(request.args.get("sample", 150, type=int), 250)
    select_inbox()
    ids = list(reversed(search_ids("ALL")))[:limit]
    senders = {}
    fetched = 0
    for msg_id in ids:
        msg = fetch_header_message(msg_id)
        if msg is None:
            continue
        fetched += 1
        sender = decode_email_header(msg.get("From", "Unknown"))
        key = sender_domain(sender) or sender or "Unknown"
        senders.setdefault(key, {"sender": sender, "domain": key, "count": 0, "samples": []})
        senders[key]["count"] += 1
        if len(senders[key]["samples"]) < 3:
            senders[key]["samples"].append(decode_email_header(msg.get("Subject", "")))
    ranked = sorted(senders.values(), key=lambda x: x["count"], reverse=True)[:50]
    return jsonify({"senders": ranked, "sampled": len(ids), "headers_read": fetched})


@app.route("/api/sender/<path:value>")
def sender_messages(value):
    if not connected():
        return jsonify({"error": "Not connected"}), 401
    limit = min(request.args.get("limit", 75, type=int), 200)
    select_inbox()
    ids = list(reversed(search_ids("FROM", f'"{value}"')))
    emails = [item for msg_id in ids[:limit] if (item := summarize_email(msg_id, f"From {value}"))]
    return jsonify({"emails": emails, "total": len(ids), "shown": len(emails), "sender": value})


@app.route("/api/unsubscribe-finder")
def unsubscribe_finder():
    if not connected():
        return jsonify({"error": "Not connected"}), 401
    sample = min(request.args.get("sample", 120, type=int), 250)
    select_inbox()
    ids = list(reversed(search_ids("ALL")))[:sample]
    grouped = {}
    for msg_id in ids:
        try:
            summary = summarize_email(msg_id, "unsubscribe finder")
            if not summary or not summary["unsubscribe_links"]:
                continue
            key = summary["sender_domain"] or summary["sender"]
            grouped.setdefault(key, {"sender": summary["sender"], "domain": key, "count": 0, "links": [], "samples": []})
            grouped[key]["count"] += 1
            grouped[key]["links"].extend(summary["unsubscribe_links"])
            if len(grouped[key]["samples"]) < 3:
                grouped[key]["samples"].append({"id": summary["id"], "subject": summary["subject"], "date": summary["date"]})
        except Exception:
            continue
    results = []
    for item in grouped.values():
        item["links"] = list(dict.fromkeys(item["links"]))[:3]
        results.append(item)
    results.sort(key=lambda x: x["count"], reverse=True)
    return jsonify({"groups": results[:50], "sampled": len(ids)})


@app.route("/api/stats")
def stats():
    if not connected():
        return jsonify({"error": "Not connected"}), 401
    select_inbox()
    return jsonify({"total_emails": len(search_ids("ALL")), "unread_count": len(search_ids("UNSEEN")), "trash_folder": find_trash_folder()})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    logger.info("Starting backend on port %s", port)
    app.run(host="0.0.0.0", port=port, debug=False)
