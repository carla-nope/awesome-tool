"""
Yahoo Mail Declutter Tool - Backend v2
Search, quick-pick cleanup, sender cleanup, and unsubscribe-link review.
All bulk actions move messages to Trash for review in Yahoo.
"""

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
CORS(app)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "change-me-in-railway")

mail_connection = None
connected_email = None
trash_folder_cache = None


def decode_email_header(header):
    if header is None:
        return ""
    try:
        output = []
        for content, charset in decode_header(header):
            if isinstance(content, bytes):
                output.append(content.decode(charset or "utf-8", errors="replace"))
            else:
                output.append(str(content))
        return "".join(output)
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
    keywords = ["unsubscribe", "opt-out", "optout", "email-preferences", "manage-subscription", "unsub"]
    links = []
    for url in extract_urls(text):
        parsed = urlparse(url)
        haystack = f"{url} {parsed.netloc} {parsed.path}".lower()
        if any(keyword in haystack for keyword in keywords):
            links.append(url)
    return list(dict.fromkeys(links))[:5]


def sender_domain(sender):
    match = re.search(r"<([^>]+)>", sender or "")
    address = match.group(1) if match else sender or ""
    return address.split("@")[-1].lower().strip() if "@" in address else ""


def imap_date(days_ago):
    return (datetime.now() - timedelta(days=days_ago)).strftime("%d-%b-%Y")


def parse_folder_name(raw_folder):
    text = raw_folder.decode(errors="replace") if isinstance(raw_folder, bytes) else str(raw_folder)
    match = re.search(r'"([^"]+)"\s*$', text)
    if match:
        return match.group(1)
    return text.split(" ")[-1].strip('"')


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
        lower = folder.lower()
        if "trash" in lower or "deleted" in lower:
            trash_folder_cache = folder
            return folder
    trash_folder_cache = "Trash"
    return trash_folder_cache


def require_connection():
    return mail_connection is not None


def search_ids(*criteria):
    try:
        status, messages = mail_connection.search(None, *criteria)
        if status != "OK" or not messages or not messages[0]:
            return []
        return messages[0].split()
    except Exception as exc:
        logger.warning("Yahoo search failed for %s: %s", criteria, exc)
        return []


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
    return {
        "verification_codes": [
            ("SUBJECT", "verification"), ("SUBJECT", "verify"), ("SUBJECT", "code"),
            ("SUBJECT", "passcode"), ("SUBJECT", "login code"), ("SUBJECT", "security code"),
            ("SUBJECT", "authentication"), ("SUBJECT", "2FA"),
        ],
        "password_resets": [
            ("SUBJECT", "password"), ("SUBJECT", "reset"), ("SUBJECT", "recover"),
            ("SUBJECT", "account access"), ("SUBJECT", "sign-in"), ("SUBJECT", "login"),
        ],
        "receipts": [
            ("SUBJECT", "receipt"), ("SUBJECT", "invoice"), ("SUBJECT", "order confirmation"),
            ("SUBJECT", "payment"), ("SUBJECT", "purchase"), ("SUBJECT", "transaction"),
            ("SUBJECT", "your order"),
        ],
        "shipping": [
            ("SUBJECT", "ship"), ("SUBJECT", "shipped"), ("SUBJECT", "shipping"),
            ("SUBJECT", "delivery"), ("SUBJECT", "delivered"), ("SUBJECT", "tracking"),
            ("SUBJECT", "out for delivery"),
        ],
        "carts": [
            ("SUBJECT", "cart"), ("SUBJECT", "checkout"), ("SUBJECT", "left something"),
            ("SUBJECT", "still interested"),
        ],
        "newsletters": [
            ("SUBJECT", "newsletter"), ("SUBJECT", "digest"), ("SUBJECT", "weekly"),
            ("SUBJECT", "roundup"), ("SUBJECT", "updates"),
        ],
        "promotions": [
            ("SUBJECT", "sale"), ("SUBJECT", "deal"), ("SUBJECT", "coupon"),
            ("SUBJECT", "offer"), ("SUBJECT", "limited time"), ("SUBJECT", "clearance"),
            ("SUBJECT", "% off"),
        ],
        "trials": [
            ("SUBJECT", "trial"), ("SUBJECT", "expires"), ("SUBJECT", "expired"),
            ("SUBJECT", "renew"), ("SUBJECT", "subscription"),
        ],
        "social": [
            ("SUBJECT", "follow"), ("SUBJECT", "liked"), ("SUBJECT", "mentioned"),
            ("SUBJECT", "tagged"), ("SUBJECT", "comment"), ("FROM", "facebook"),
            ("FROM", "instagram"), ("FROM", "linkedin"), ("FROM", "twitter"),
        ],
        "noreply": [
            ("FROM", "noreply"), ("FROM", "no-reply"), ("FROM", "donotreply"),
            ("FROM", "do-not-reply"),
        ],
        "old_unread_1y": [("UNSEEN", "BEFORE", imap_date(365))],
        "old_unread_2y": [("UNSEEN", "BEFORE", imap_date(730))],
        "old_read_2y": [("SEEN", "BEFORE", imap_date(730))],
        "old_read_5y": [("SEEN", "BEFORE", imap_date(1825))],
        "old_promotions_6m": [("SUBJECT", "sale", "BEFORE", imap_date(180)), ("SUBJECT", "coupon", "BEFORE", imap_date(180))],
        "old_receipts_2y": [("SUBJECT", "receipt", "BEFORE", imap_date(730)), ("SUBJECT", "invoice", "BEFORE", imap_date(730))],
    }.get(name)


def run_recipe(name):
    searches = recipe_searches(name)
    if searches is None:
        return None
    groups = []
    for criteria in searches:
        normalized = []
        for i, part in enumerate(criteria):
            if i % 2 == 1 and part not in [imap_date(365), imap_date(730), imap_date(1825), imap_date(180)]:
                normalized.append(f'"{part}"')
            else:
                normalized.append(part)
        groups.append(search_ids(*normalized))
    return unique_ids(groups)


def summarize_email(msg_id, matched_by=None):
    status, data = mail_connection.fetch(msg_id, "(RFC822)")
    if status != "OK" or not data:
        return None
    msg = email.message_from_bytes(data[0][1])
    subject = decode_email_header(msg.get("Subject", ""))
    sender = decode_email_header(msg.get("From", ""))
    body = get_email_body(msg)
    unsub_links = find_unsubscribe_links(body)
    return {
        "id": msg_id.decode() if isinstance(msg_id, bytes) else str(msg_id),
        "subject": subject,
        "sender": sender,
        "sender_domain": sender_domain(sender),
        "date": msg.get("Date", ""),
        "snippet": body[:240] if body else "(No content)",
        "has_unsubscribe": bool(unsub_links),
        "unsubscribe_links": unsub_links,
        "matched_by": matched_by or "Search result",
    }


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


@app.route("/api/health")
def health():
    return jsonify({"ok": True, "app": "Yahoo Mail Declutter Tool v2"})


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
        logger.error("Connection failed: %s", exc)
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
    if not require_connection():
        return jsonify({"error": "Not connected"}), 401
    try:
        return jsonify({"folders": list_folder_names(), "trash_folder": find_trash_folder()})
    except Exception as exc:
        return jsonify({"folders": [], "trash_folder": "Trash", "warning": str(exc)})


@app.route("/api/search", methods=["POST"])
def search():
    if not require_connection():
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
    mail_connection.select("INBOX")
    ids = list(reversed(search_ids(*criteria)))
    emails = [item for msg_id in ids[:limit] if (item := summarize_email(msg_id, "Manual search"))]
    return jsonify({"emails": emails, "total": len(ids), "shown": len(emails)})


@app.route("/api/quick-pick/<name>")
def quick_pick(name):
    if not require_connection():
        return jsonify({"error": "Not connected"}), 401
    limit = min(request.args.get("limit", 75, type=int), 200)
    mail_connection.select("INBOX")
    ids = run_recipe(name)
    if ids is None:
        return jsonify({"error": f"Unknown quick-pick recipe: {name}"}), 400
    ordered = ids if name.startswith("old_") else list(reversed(ids))
    emails = [item for msg_id in ordered[:limit] if (item := summarize_email(msg_id, name.replace("_", " ")))]
    return jsonify({"emails": emails, "total": len(ids), "shown": len(emails), "recipe": name})


@app.route("/api/quick-pick-counts")
def quick_pick_counts():
    if not require_connection():
        return jsonify({"counts": {}}), 401
    names = [
        "verification_codes", "password_resets", "receipts", "shipping", "carts", "newsletters",
        "promotions", "trials", "social", "noreply", "old_unread_1y", "old_unread_2y",
        "old_read_2y", "old_read_5y", "old_promotions_6m", "old_receipts_2y"
    ]
    mail_connection.select("INBOX")
    counts = {}
    for name in names:
        counts[name] = len(run_recipe(name) or [])
    return jsonify({"counts": counts})


@app.route("/api/move-to-trash", methods=["POST"])
def move_selected_to_trash():
    if not require_connection():
        return jsonify({"error": "Not connected"}), 401
    ids = (request.get_json() or {}).get("email_ids", [])
    if not ids:
        return jsonify({"error": "No messages selected"}), 400
    mail_connection.select("INBOX")
    moved = 0
    failed = []
    folder = find_trash_folder()
    for msg_id in ids:
        ok, folder, err = move_to_trash(msg_id)
        if ok:
            moved += 1
        else:
            failed.append({"id": msg_id, "error": err})
    return jsonify({
        "success": len(failed) == 0,
        "moved": moved,
        "deleted": moved,
        "failed": failed,
        "trash_folder": folder,
        "message": f"Moved {moved} message(s) to {folder}. Review them in Yahoo before emptying Trash."
    })


@app.route("/api/delete", methods=["POST"])
def legacy_delete_alias():
    return move_selected_to_trash()


@app.route("/api/top-senders")
def top_senders():
    if not require_connection():
        return jsonify({"error": "Not connected"}), 401
    limit = min(request.args.get("sample", 500, type=int), 2000)
    mail_connection.select("INBOX")
    ids = list(reversed(search_ids("ALL")))[:limit]
    senders = {}
    for msg_id in ids:
        try:
            status, data = mail_connection.fetch(msg_id, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])")
            if status != "OK" or not data:
                continue
            msg = email.message_from_bytes(data[0][1])
            sender = decode_email_header(msg.get("From", "Unknown"))
            key = sender_domain(sender) or sender
            if key not in senders:
                senders[key] = {"sender": sender, "domain": key, "count": 0, "samples": []}
            senders[key]["count"] += 1
            if len(senders[key]["samples"]) < 3:
                senders[key]["samples"].append(decode_email_header(msg.get("Subject", "")))
        except Exception:
            continue
    ranked = sorted(senders.values(), key=lambda x: x["count"], reverse=True)[:50]
    return jsonify({"senders": ranked, "sampled": len(ids)})


@app.route("/api/sender/<path:value>")
def sender_messages(value):
    if not require_connection():
        return jsonify({"error": "Not connected"}), 401
    limit = min(request.args.get("limit", 75, type=int), 200)
    mail_connection.select("INBOX")
    ids = list(reversed(search_ids("FROM", f'"{value}"')))
    emails = [item for msg_id in ids[:limit] if (item := summarize_email(msg_id, f"From {value}"))]
    return jsonify({"emails": emails, "total": len(ids), "shown": len(emails), "sender": value})


@app.route("/api/unsubscribe-finder")
def unsubscribe_finder():
    if not require_connection():
        return jsonify({"error": "Not connected"}), 401
    sample = min(request.args.get("sample", 200, type=int), 1000)
    mail_connection.select("INBOX")
    ids = list(reversed(search_ids("ALL")))[:sample]
    grouped = {}
    for msg_id in ids:
        try:
            summary = summarize_email(msg_id, "unsubscribe finder")
            if not summary or not summary["unsubscribe_links"]:
                continue
            key = summary["sender_domain"] or summary["sender"]
            if key not in grouped:
                grouped[key] = {"sender": summary["sender"], "domain": key, "count": 0, "links": [], "samples": []}
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
    if not require_connection():
        return jsonify({"error": "Not connected"}), 401
    mail_connection.select("INBOX")
    return jsonify({
        "total_emails": len(search_ids("ALL")),
        "unread_count": len(search_ids("UNSEEN")),
        "trash_folder": find_trash_folder(),
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_DEBUG") == "1")
