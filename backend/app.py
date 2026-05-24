"""
Yahoo Mail Cleanup Agent - Backend
Handles IMAP connection and email operations for Yahoo Mail
"""

import imaplib
import email
from email.header import decode_header
import re
from datetime import datetime
from flask import Flask, request, jsonify, session
from flask_cors import CORS
import json
import logging
from urllib.parse import urlparse

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)
app.secret_key = 'yahoo-mail-cleanup-secret-key-change-in-production'

# Global connection state
mail_connection = None
connected_email = None


def decode_email_header(header):
    """Decode email header properly"""
    if header is None:
        return ""

    decoded_parts = []
    try:
        parts = decode_header(header)
        for content, charset in parts:
            if isinstance(content, bytes):
                charset = charset or 'utf-8'
                try:
                    decoded_parts.append(content.decode(charset, errors='replace'))
                except (LookupError, UnicodeDecodeError):
                    decoded_parts.append(content.decode('utf-8', errors='replace'))
            else:
                decoded_parts.append(content)
    except Exception as e:
        logger.warning(f"Header decode error: {e}")
        return header

    return ''.join(decoded_parts)


def extract_urls(text):
    """Extract URLs from text"""
    url_pattern = re.compile(
        r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    )
    return url_pattern.findall(text)


def find_unsubscribe_links(text, urls):
    """Find unsubscribe links from URLs"""
    unsubscribe_keywords = ['unsubscribe', 'opt-out', 'optout', 'email-preferences',
                           'manage-subscription', 'notification-preferences', 'unsub']
    unsubscribe_links = []

    for url in urls:
        url_lower = url.lower()
        parsed = urlparse(url)
        path_domain = f"{parsed.netloc}{parsed.path}".lower()

        for keyword in unsubscribe_keywords:
            if keyword in url_lower or keyword in path_domain:
                unsubscribe_links.append(url)
                break

    return unsubscribe_links


def categorize_email(sender_domain, subject, has_unsubscribe):
    """Categorize email type"""
    subject_lower = (subject or '').lower()

    if any(x in subject_lower for x in ['facebook', 'twitter', 'instagram', 'linkedin', 'social']):
        return 'social'
    elif any(x in subject_lower for x in ['linkedin', 'job', 'indeed', 'resume', 'interview']):
        return 'job'
    elif any(x in subject_lower for x in ['amazon', 'ebay', 'order', 'shipping', 'delivery', 'tracking']):
        return 'shopping'
    elif has_unsubscribe and 'newsletter' in subject_lower:
        return 'newsletter'
    elif has_unsubscribe:
        return 'marketing'
    else:
        return 'other'


def get_email_body(msg):
    """Extract email body text"""
    body = ""
    html_content = ""

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get_content_disposition())

            if content_disposition == 'attachment':
                continue

            if content_type == 'text/plain' and not body:
                try:
                    payload = part.get_payload(decode=True)
                    charset = part.get_content_charset() or 'utf-8'
                    body = payload.decode(charset, errors='replace')
                except:
                    pass
            elif content_type == 'text/html' and not html_content:
                try:
                    payload = part.get_payload(decode=True)
                    charset = part.get_content_charset() or 'utf-8'
                    html_content = payload.decode(charset, errors='replace')
                except:
                    pass
    else:
        try:
            payload = msg.get_payload(decode=True)
            charset = msg.get_content_charset() or 'utf-8'
            body = payload.decode(charset, errors='replace')
        except:
            pass

    # Strip HTML for plain text if needed
    if body:
        body = re.sub(r'<[^>]+>', ' ', body)
        body = re.sub(r'\s+', ' ', body).strip()

    return body or html_content


@app.route('/api/connect', methods=['POST'])
def connect():
    """Connect to Yahoo Mail"""
    global mail_connection, connected_email

    data = request.get_json()
    email_address = data.get('email')
    password = data.get('password')

    if not email_address or not password:
        return jsonify({'success': False, 'error': 'Email and password required'}), 400

    try:
        # Yahoo IMAP server
        mail = imaplib.IMAP4_SSL("imap.mail.yahoo.com", 993)
        mail.login(email_address, password)

        # Select INBOX
        mail.select('INBOX')

        mail_connection = mail
        connected_email = email_address

        session['connected'] = True
        session['email'] = email_address

        logger.info(f"Connected to Yahoo Mail: {email_address}")

        return jsonify({
            'success': True,
            'message': f'Connected to {email_address}',
            'email': email_address
        })

    except imaplib.IMAP4.error as e:
        error_msg = str(e)
        if b'AUTH' in error_msg.encode() if isinstance(error_msg, str) else b'AUTH' in e:
            return jsonify({'success': False, 'error': 'Invalid credentials. Please check your email and app password.'}), 401
        return jsonify({'success': False, 'error': f'Authentication failed: {error_msg}'}), 401
    except Exception as e:
        logger.error(f"Connection error: {e}")
        return jsonify({'success': False, 'error': f'Connection failed: {str(e)}'}), 500


@app.route('/api/status', methods=['GET'])
def status():
    """Check connection status"""
    global mail_connection, connected_email

    if mail_connection is None:
        return jsonify({'connected': False})

    try:
        mail_connection.noop()  # Test connection
        return jsonify({
            'connected': True,
            'email': connected_email
        })
    except:
        mail_connection = None
        connected_email = None
        return jsonify({'connected': False})


@app.route('/api/disconnect', methods=['POST'])
def disconnect():
    """Disconnect from Yahoo Mail"""
    global mail_connection, connected_email

    if mail_connection:
        try:
            mail_connection.logout()
        except:
            pass
        mail_connection = None
        connected_email = None

    session.clear()
    return jsonify({'success': True, 'message': 'Disconnected'})


@app.route('/api/search', methods=['POST'])
def search_emails():
    """Search emails with filters"""
    global mail_connection

    if mail_connection is None:
        return jsonify({'error': 'Not connected'}), 401

    data = request.get_json()
    query = data.get('query', '')
    sender = data.get('sender', '')
    subject = data.get('subject', '')
    date_from = data.get('date_from', '')
    date_to = data.get('date_to', '')
    page = data.get('page', 1)
    per_page = data.get('per_page', 20)

    try:
        # Build search criteria
        search_criteria = []

        if sender:
            search_criteria.append(f'FROM "{sender}"')
        if subject:
            search_criteria.append(f'SUBJECT "{subject}"')
        if date_from:
            search_criteria.append(f'SINCE "{date_from}"')
        if date_to:
            search_criteria.append(f'BEFORE "{date_to}"')
        if query:
            search_criteria.append(f'TEXT "{query}"')

        if not search_criteria:
            search_criteria = ['ALL']

        # Execute search
        status, messages = mail_connection.search(None, *search_criteria)

        if status != 'OK':
            return jsonify({'error': 'Search failed'}), 500

        email_ids = messages[0].split() if messages[0] else []
        total = len(email_ids)

        # Paginate
        start = (page - 1) * per_page
        end = start + per_page
        page_ids = email_ids[start:end]

        # Fetch email summaries
        emails = []
        for email_id in reversed(page_ids):
            try:
                status, msg_data = mail_connection.fetch(email_id, '(RFC822)')
                if status == 'OK' and msg_data:
                    raw_email = msg_data[0][1]
                    msg = email.message_from_bytes(raw_email)

                    subject = decode_email_header(msg.get('Subject', ''))
                    sender = decode_email_header(msg.get('From', ''))
                    date = msg.get('Date', '')
                    message_id = email_id.decode()

                    # Get snippet
                    body = get_email_body(msg)
                    snippet = body[:200] if body else '(No content)'

                    # Extract URLs and check for unsubscribe
                    urls = extract_urls(body)
                    unsubscribe_links = find_unsubscribe_links(body, urls)

                    emails.append({
                        'id': message_id,
                        'subject': subject,
                        'sender': sender,
                        'date': date,
                        'snippet': snippet,
                        'has_unsubscribe': len(unsubscribe_links) > 0,
                        'unsubscribe_links': unsubscribe_links[:3]  # Limit to first 3
                    })
            except Exception as e:
                logger.warning(f"Error fetching email {email_id}: {e}")
                continue

        return jsonify({
            'emails': emails,
            'total': total,
            'page': page,
            'per_page': per_page,
            'pages': (total + per_page - 1) // per_page
        })

    except Exception as e:
        logger.error(f"Search error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/emails', methods=['GET'])
def get_emails():
    """Get emails from INBOX"""
    global mail_connection

    if mail_connection is None:
        return jsonify({'error': 'Not connected'}), 401

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    folder = request.args.get('folder', 'INBOX')

    try:
        status, _ = mail_connection.select(folder)
        if status != 'OK':
            return jsonify({'error': f'Cannot access folder {folder}'}), 500

        status, messages = mail_connection.search(None, 'ALL')

        if status != 'OK':
            return jsonify({'error': 'Failed to get messages'}), 500

        email_ids = messages[0].split() if messages[0] else []
        total = len(email_ids)

        start = (page - 1) * per_page
        end = start + per_page
        page_ids = email_ids[start:end]

        emails = []
        for email_id in reversed(page_ids):
            try:
                status, msg_data = mail_connection.fetch(email_id, '(RFC822)')
                if status == 'OK' and msg_data:
                    raw_email = msg_data[0][1]
                    msg = email.message_from_bytes(raw_email)

                    subject = decode_email_header(msg.get('Subject', ''))
                    sender = decode_email_header(msg.get('From', ''))
                    date = msg.get('Date', '')
                    message_id = email_id.decode()

                    body = get_email_body(msg)
                    snippet = body[:200] if body else '(No content)'

                    urls = extract_urls(body)
                    unsubscribe_links = find_unsubscribe_links(body, urls)

                    emails.append({
                        'id': message_id,
                        'subject': subject,
                        'sender': sender,
                        'date': date,
                        'snippet': snippet,
                        'has_unsubscribe': len(unsubscribe_links) > 0,
                        'unsubscribe_links': unsubscribe_links[:3]
                    })
            except Exception as e:
                logger.warning(f"Error fetching email {email_id}: {e}")
                continue

        return jsonify({
            'emails': emails,
            'total': total,
            'page': page,
            'per_page': per_page,
            'pages': (total + per_page - 1) // per_page,
            'folder': folder
        })

    except Exception as e:
        logger.error(f"Get emails error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/email/<email_id>', methods=['GET'])
def get_email_detail(email_id):
    """Get full email details"""
    global mail_connection

    if mail_connection is None:
        return jsonify({'error': 'Not connected'}), 401

    try:
        status, msg_data = mail_connection.fetch(email_id, '(RFC822)')

        if status != 'OK':
            return jsonify({'error': 'Failed to fetch email'}), 500

        raw_email = msg_data[0][1]
        msg = email.message_from_bytes(raw_email)

        subject = decode_email_header(msg.get('Subject', ''))
        sender = decode_email_header(msg.get('From', ''))
        to = decode_email_header(msg.get('To', ''))
        date = msg.get('Date', '')
        message_id = msg.get('Message-ID', '')

        body = get_email_body(msg)
        urls = extract_urls(body)
        unsubscribe_links = find_unsubscribe_links(body, urls)

        # Parse sender domain
        sender_domain = ''
        if '<' in sender:
            email_match = re.search(r'<([^>]+)>', sender)
            if email_match:
                sender_domain = email_match.group(1).split('@')[1] if '@' in email_match.group(1) else ''
        else:
            parts = sender.split('@')
            if len(parts) > 1:
                sender_domain = parts[1]

        category = categorize_email(sender_domain, subject, len(unsubscribe_links) > 0)

        return jsonify({
            'id': email_id,
            'subject': subject,
            'sender': sender,
            'to': to,
            'date': date,
            'message_id': message_id,
            'body': body,
            'urls': urls,
            'unsubscribe_links': unsubscribe_links,
            'category': category,
            'sender_domain': sender_domain
        })

    except Exception as e:
        logger.error(f"Email detail error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/delete', methods=['POST'])
def delete_emails():
    """Delete selected emails"""
    global mail_connection

    if mail_connection is None:
        return jsonify({'error': 'Not connected'}), 401

    data = request.get_json()
    email_ids = data.get('email_ids', [])
    permanent = data.get('permanent', False)

    if not email_ids:
        return jsonify({'error': 'No emails selected'}), 400

    try:
        deleted = 0
        for email_id in email_ids:
            if permanent:
                # Move to trash first, then permanently delete
                mail_connection.store(email_id, '+FLAGS', '\\Deleted')
            else:
                # Move to trash
                mail_connection.move(email_id, 'INBOX/Trash')
            deleted += 1

        if permanent:
            mail_connection.expunge()

        return jsonify({
            'success': True,
            'deleted': deleted,
            'message': f'{deleted} email(s) deleted'
        })

    except Exception as e:
        logger.error(f"Delete error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/unsubscribe', methods=['POST'])
def unsubscribe():
    """Mark emails from sender for deletion (simulated unsubscribe)"""
    global mail_connection

    if mail_connection is None:
        return jsonify({'error': 'Not connected'}), 401

    data = request.get_json()
    sender = data.get('sender', '')
    delete_all = data.get('delete_all', True)

    if not sender:
        return jsonify({'error': 'Sender required'}), 400

    try:
        # Search for emails from this sender
        search_query = f'FROM "{sender}"'
        status, messages = mail_connection.search(None, search_query)

        if status != 'OK':
            return jsonify({'error': 'Search failed'}), 500

        email_ids = messages[0].split() if messages[0] else []
        count = len(email_ids)

        # Move to trash
        deleted = 0
        for email_id in email_ids:
            try:
                mail_connection.move(email_id, 'INBOX/Trash')
                deleted += 1
            except:
                pass

        return jsonify({
            'success': True,
            'deleted': deleted,
            'message': f'Unsubscribed from {sender}. {deleted} email(s) moved to trash.'
        })

    except Exception as e:
        logger.error(f"Unsubscribe error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get email statistics"""
    global mail_connection

    if mail_connection is None:
        return jsonify({'error': 'Not connected'}), 401

    try:
        # Get total INBOX count
        status, messages = mail_connection.search(None, 'ALL')
        total_emails = len(messages[0].split()) if messages[0] else 0

        # Get unread count
        status, unread = mail_connection.search(None, 'UNSEEN')
        unread_count = len(unread[0].split()) if unread[0] else 0

        # Sample emails for category analysis (first 50)
        status, messages = mail_connection.search(None, 'ALL')
        email_ids = messages[0].split()[:50] if messages[0] else []

        categories = {'social': 0, 'job': 0, 'shopping': 0, 'newsletter': 0, 'marketing': 0, 'other': 0}
        top_senders = {}

        for email_id in email_ids:
            try:
                status, msg_data = mail_connection.fetch(email_id, '(RFC822)')
                if status == 'OK' and msg_data:
                    msg = email.message_from_bytes(msg_data[0][1])
                    sender = decode_email_header(msg.get('From', ''))
                    subject = decode_email_header(msg.get('Subject', ''))

                    # Count by sender
                    if sender in top_senders:
                        top_senders[sender] += 1
                    else:
                        top_senders[sender] = 1

                    # Categorize
                    body = get_email_body(msg)
                    urls = extract_urls(body)
                    unsubscribe_links = find_unsubscribe_links(body, urls)

                    # Parse sender domain
                    sender_domain = ''
                    if '<' in sender:
                        email_match = re.search(r'<([^>]+)>', sender)
                        if email_match:
                            sender_domain = email_match.group(1).split('@')[1] if '@' in email_match.group(1) else ''

                    category = categorize_email(sender_domain, subject, len(unsubscribe_links) > 0)
                    categories[category] = categories.get(category, 0) + 1
            except:
                continue

        # Sort top senders
        top_senders = sorted(top_senders.items(), key=lambda x: x[1], reverse=True)[:10]

        return jsonify({
            'total_emails': total_emails,
            'unread_count': unread_count,
            'categories': categories,
            'top_senders': [{'sender': s[0], 'count': s[1]} for s in top_senders]
        })

    except Exception as e:
        logger.error(f"Stats error: {e}")
        return jsonify({'error': str(e)}), 500


# Smart Cleanup Search endpoint
@app.route('/api/search/cleanup', methods=['GET'])
def search_cleanup():
    """Search for specific cleanup categories"""
    global mail_connection

    if mail_connection is None:
        return jsonify({'error': 'Not connected'}), 401

    cleanup_type = request.args.get('type', '')
    limit = request.args.get('limit', 50, type=int)
    older_than = request.args.get('older_than', '')

    try:
        mail_connection.select('INBOX')

        # Calculate date filters
        now = datetime.now()
        date_ranges = {
            '1y': (now.replace(year=now.year - 1)).strftime('%d-%b-%Y'),
            '2y': (now.replace(year=now.year - 2)).strftime('%d-%b-%Y'),
            '6m': (now.replace(month=max(1, now.month - 6))).strftime('%d-%b-%Y'),
            '1m': (now.replace(month=max(1, now.month - 1))).strftime('%d-%b-%Y'),
        }

        # Map cleanup types to IMAP search criteria
        cleanup_searches = {
            'verification_codes': {
                'criteria': '(OR SUBJECT "code" OR SUBJECT "verification" OR SUBJECT "confirm your" OR SUBJECT "verify" OR SUBJECT "OTP" OR SUBJECT "one-time" OR SUBJECT "login code" OR SUBJECT "authentication") SINCE ' + date_ranges['6m'],
                'older_than': ''
            },
            'password_reset': {
                'criteria': '(OR SUBJECT "password reset" OR SUBJECT "reset your password" OR SUBJECT "change your password" OR SUBJECT "forgot password" OR SUBJECT "reset password") SINCE ' + date_ranges['1y'],
                'older_than': ''
            },
            'shipping': {
                'criteria': '(OR SUBJECT "shipped" OR SUBJECT "out for delivery" OR SUBJECT "tracking" OR SUBJECT "delivered" OR SUBJECT "package" OR SUBJECT "delivery update") SINCE ' + date_ranges['1m'],
                'older_than': ''
            },
            'receipts': {
                'criteria': '(OR SUBJECT "receipt" OR SUBJECT "order confirmed" OR SUBJECT "purchase" OR SUBJECT "transaction" OR SUBJECT "invoice") SINCE ' + date_ranges['1y'],
                'older_than': ''
            },
            'cart': {
                'criteria': '(OR SUBJECT "abandoned cart" OR SUBJECT "left something" OR SUBJECT "complete your purchase" OR SUBJECT "still interested" OR SUBJECT "cart reminder") SINCE ' + date_ranges['6m'],
                'older_than': ''
            },
            'newsletters': {
                'criteria': '(OR SUBJECT "newsletter" OR SUBJECT "digest" OR SUBJECT "weekly update" OR SUBJECT "monthly update" OR SUBJECT "latest news") SINCE ' + date_ranges['6m'],
                'older_than': ''
            },
            'promotions': {
                'criteria': '(OR SUBJECT "sale" OR SUBJECT "limited time" OR SUBJECT "deal" OR SUBJECT "offer" OR SUBJECT "save" OR SUBJECT "clearance" OR SUBJECT "discount") SINCE ' + date_ranges['6m'],
                'older_than': ''
            },
            'expired_trials': {
                'criteria': '(OR SUBJECT "trial expired" OR SUBJECT "trial ending" OR SUBJECT "upgrade now" OR SUBJECT "trial ended" OR SUBJECT "subscribe now") SINCE ' + date_ranges['6m'],
                'older_than': ''
            },
            'social': {
                'criteria': '(OR SUBJECT "followers" OR SUBJECT "liked" OR SUBJECT "commented" OR SUBJECT "new follower" OR SUBJECT "social" OR SUBJECT "connection request") SINCE ' + date_ranges['6m'],
                'older_than': ''
            },
            'comment_alerts': {
                'criteria': '(OR SUBJECT "comment" OR SUBJECT "replied" OR SUBJECT "mentioned" OR SUBJECT "notification" OR SUBJECT "activity on") SINCE ' + date_ranges['6m'],
                'older_than': ''
            },
            'old_unread': {
                'criteria': 'UNSEEN',
                'older_than': date_ranges['1y']
            },
            'old_read': {
                'criteria': 'SEEN',
                'older_than': date_ranges['2y']
            },
            'auto_confirmations': {
                'criteria': '(OR SUBJECT "confirmation" OR SUBJECT "confirm" OR SUBJECT "confirmed" OR SUBJECT "automated" OR SUBJECT "system") SINCE ' + date_ranges['1y'],
                'older_than': ''
            },
            'old_newsletters': {
                'criteria': '(OR SUBJECT "newsletter" OR SUBJECT "digest" OR SUBJECT "subscribe" OR SUBJECT "unsubscribe")',
                'older_than': date_ranges['6m']
            }
        }

        if cleanup_type not in cleanup_searches:
            return jsonify({'error': f'Unknown cleanup type: {cleanup_type}'}), 400

        search_config = cleanup_searches[cleanup_type]
        search_criteria = search_config['criteria']

        # Add older_than date filter if specified
        if search_config['older_than']:
            search_criteria = f'{search_criteria} BEFORE {search_config["older_than"]}'

        status, messages = mail_connection.search(None, search_criteria)

        if status != 'OK':
            return jsonify({'error': 'Search failed', 'details': str(status)}), 500

        email_ids = messages[0].split() if messages[0] else []

        # Limit results
        email_ids = email_ids[:limit]

        emails = []
        for email_id in email_ids:
            try:
                status, msg_data = mail_connection.fetch(email_id, '(RFC822)')
                if status == 'OK' and msg_data:
                    raw_email = msg_data[0][1]
                    msg = email.message_from_bytes(raw_email)

                    subject = decode_email_header(msg.get('Subject', ''))
                    sender = decode_email_header(msg.get('From', ''))
                    date = msg.get('Date', '')
                    message_id = email_id.decode()

                    body = get_email_body(msg)
                    snippet = body[:200] if body else '(No content)'

                    urls = extract_urls(body)
                    unsubscribe_links = find_unsubscribe_links(body, urls)

                    emails.append({
                        'id': message_id,
                        'subject': subject,
                        'sender': sender,
                        'date': date,
                        'snippet': snippet,
                        'has_unsubscribe': len(unsubscribe_links) > 0,
                        'unsubscribe_links': unsubscribe_links[:3],
                        'category': cleanup_type
                    })
            except Exception as e:
                logger.warning(f"Error fetching email {email_id}: {e}")
                continue

        return jsonify({
            'emails': emails,
            'total': len(emails),
            'type': cleanup_type
        })

    except Exception as e:
        logger.error(f"Cleanup search error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/folders', methods=['GET'])
def get_folders():
    """Get list of folders"""
    global mail_connection

    if mail_connection is None:
        return jsonify({'error': 'Not connected'}), 401

    try:
        status, folders = mail_connection.list()

        folder_list = []
        if status == 'OK':
            for folder in folders:
                # Parse folder info
                folder_data = folder.decode().split(' "/" ')
                if len(folder_data) == 2:
                    folder_list.append(folder_data[1].strip('"'))

        return jsonify({'folders': folder_list})

    except Exception as e:
        logger.error(f"Folders error: {e}")
        return jsonify({'error': str(e)}), 500


# ========== EMAIL TRIAGE ENDPOINTS ==========

from triage import EmailTriageExporter, EmailCommandExecutor, EMAIL_TRIAGE_SYSTEM_PROMPT


@app.route('/api/triage/batch', methods=['GET'])
def get_triage_batch():
    """Get a batch of emails formatted for AI triage analysis"""
    global mail_connection

    if mail_connection is None:
        return jsonify({'error': 'Not connected'}), 401

    start = request.args.get('start', 0, type=int)
    limit = request.args.get('limit', 20, type=int)

    try:
        exporter = EmailTriageExporter(mail_connection)
        batch_data = exporter.export_batch(start=start, limit=limit)

        if not batch_data:
            return jsonify({'error': 'Failed to export batch'}), 500

        formatted_text = exporter.format_for_ai(batch_data)

        return jsonify({
            'success': True,
            'batch': batch_data,
            'formatted_text': formatted_text,
            'system_prompt': EMAIL_TRIAGE_SYSTEM_PROMPT
        })

    except Exception as e:
        logger.error(f"Triage batch error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/triage/execute', methods=['POST'])
def execute_triage_commands():
    """Execute JSON commands generated by AI triage analysis"""
    global mail_connection

    if mail_connection is None:
        return jsonify({'error': 'Not connected'}), 401

    data = request.get_json()
    commands = data.get('commands', [])

    if not commands:
        return jsonify({'error': 'No commands provided'}), 400

    try:
        executor = EmailCommandExecutor(mail_connection)
        result = executor.execute_commands(commands)

        return jsonify(result)

    except Exception as e:
        logger.error(f"Execute commands error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/triage/system-prompt', methods=['GET'])
def get_system_prompt():
    """Get the email triage system prompt for context"""
    return jsonify({
        'system_prompt': EMAIL_TRIAGE_SYSTEM_PROMPT,
        'instructions': """
This system prompt helps you analyze email batches. When you receive a batch:

1. Review each email and assign:
   - Urgency: High/Medium/Low/None
   - Category: Action Required, Newsletter, Reference, Junk, Urgent
   - Action: Delete, Unsubscribe, Move to Folder:X, Archive

2. Always output a Markdown table with your analysis

3. After user approval, output JSON commands:
   ```json
   [
     {"id": "EMAIL_ID", "action": "delete"},
     {"id": "EMAIL_ID", "action": "move", "destination": "Newsletters"},
     {"id": "EMAIL_ID", "action": "unsubscribe", "sender": "newsletter@example.com", "unsubscribe_url": "https://..."}
   ]
   ```
"""
    })


# ========== TRUE UNSUBSCRIBE ENDPOINTS ==========

from unsubscribe_service import UnsubscribeService, find_unsubscribe_url, attempt_unsubscribe


@app.route('/api/unsubscribe/find-url', methods=['POST'])
def find_unsubscribe_url_endpoint():
    """Find unsubscribe URL from an email"""
    global mail_connection

    if mail_connection is None:
        return jsonify({'error': 'Not connected'}), 401

    data = request.get_json()
    email_id = data.get('email_id')

    if not email_id:
        return jsonify({'error': 'Email ID required'}), 400

    try:
        # Fetch email content
        status, msg_data = mail_connection.fetch(email_id, '(RFC822)')
        if status != 'OK':
            return jsonify({'error': 'Failed to fetch email'}), 500

        import email as email_lib
        msg = email_lib.message_from_bytes(msg_data[0][1])

        # Get body text
        body = b''
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == 'text/plain':
                    payload = part.get_payload(decode=True)
                    charset = part.get_content_charset() or 'utf-8'
                    body = payload.decode(charset, errors='replace')
                    break
        else:
            payload = msg.get_payload(decode=True)
            charset = msg.get_content_charset() or 'utf-8'
            body = payload.decode(charset, errors='replace')

        # Find unsubscribe URL
        url = find_unsubscribe_url(body)

        return jsonify({
            'success': True,
            'email_id': email_id,
            'unsubscribe_url': url,
            'found': url is not None
        })

    except Exception as e:
        logger.error(f"Find unsubscribe URL error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/unsubscribe/visit', methods=['POST'])
def visit_unsubscribe_url():
    """Visit an unsubscribe URL to complete opt-out"""
    data = request.get_json()
    url = data.get('url')
    email_id = data.get('email_id')

    if not url:
        return jsonify({'error': 'URL required'}), 400

    try:
        result = attempt_unsubscribe(url, email_id)

        return jsonify({
            'success': True,
            'result': result
        })

    except Exception as e:
        logger.error(f"Unsubscribe visit error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/unsubscribe/full', methods=['POST'])
def full_unsubscribe():
    """Complete unsubscribe: find URL, visit it, delete emails from sender"""
    global mail_connection

    if mail_connection is None:
        return jsonify({'error': 'Not connected'}), 401

    data = request.get_json()
    sender = data.get('sender')
    email_id = data.get('email_id')
    unsubscribe_url = data.get('unsubscribe_url')

    if not sender:
        return jsonify({'error': 'Sender required'}), 400

    try:
        service = UnsubscribeService(mail_connection)

        # If no URL provided, try to find it
        if not unsubscribe_url and email_id:
            status, msg_data = mail_connection.fetch(email_id, '(RFC822)')
            if status == 'OK':
                import email as email_lib
                msg = email_lib.message_from_bytes(msg_data[0][1])
                body = ''
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == 'text/plain':
                            payload = part.get_payload(decode=True)
                            charset = part.get_content_charset() or 'utf-8'
                            body = payload.decode(charset, errors='replace')
                            break
                else:
                    payload = msg.get_payload(decode=True)
                    charset = msg.get_content_charset() or 'utf-8'
                    body = payload.decode(charset, errors='replace')
                unsubscribe_url = find_unsubscribe_url(body)

        result = service.full_unsubscribe(sender=sender, unsubscribe_url=unsubscribe_url)

        return jsonify({
            'success': True,
            'result': result
        })

    except Exception as e:
        logger.error(f"Full unsubscribe error: {e}")
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)