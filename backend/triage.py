"""
Yahoo Mail Cleanup Agent - Email Triage Utilities
Handles batch extraction and JSON command execution
"""

import imaplib
import email
from email.header import decode_header
import json
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


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
    except Exception:
        return header
    return ''.join(decoded_parts)


def get_email_body_plain(msg):
    """Extract plain text body"""
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            content_disposition = str(part.get_content_disposition())
            if content_disposition == 'attachment':
                continue
            if part.get_content_type() == 'text/plain':
                try:
                    payload = part.get_payload(decode=True)
                    charset = part.get_content_charset() or 'utf-8'
                    body = payload.decode(charset, errors='replace')
                    break
                except:
                    pass
    else:
        try:
            payload = msg.get_payload(decode=True)
            charset = msg.get_content_charset() or 'utf-8'
            body = payload.decode(charset, errors='replace')
        except:
            pass
    return body[:500] if body else ""


def parse_sender(sender):
    """Parse sender into name and email"""
    sender = decode_email_header(sender)
    name = sender
    email_addr = ""

    if '<' in sender:
        import re
        match = re.search(r'^(.+?)\s*<([^>]+)>', sender)
        if match:
            name = match.group(1).strip()
            email_addr = match.group(2).strip()
    else:
        if '@' in sender:
            email_addr = sender.strip()
            name = sender.split('@')[0]

    return name, email_addr


def parse_date(date_str):
    """Parse email date to datetime"""
    if not date_str:
        return None
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(date_str)
    except:
        try:
            return datetime.strptime(date_str, '%a, %d %b %Y %H:%M:%S %z')
        except:
            return None


class EmailTriageExporter:
    """Export emails for AI triage analysis"""

    def __init__(self, mail_connection):
        self.mail = mail_connection

    def export_batch(self, folder='INBOX', limit=20, start=0):
        """
        Export a batch of emails as text summary for AI analysis
        Returns formatted text that can be pasted into AI
        """
        try:
            status, messages = self.mail.search(None, 'ALL')
            if status != 'OK':
                return None

            email_ids = messages[0].split() if messages[0] else []
            total = len(email_ids)

            # Apply pagination
            start = max(0, start)
            end = min(start + limit, total)
            page_ids = email_ids[start:end]

            batch_data = []
            for email_id in reversed(page_ids):
                try:
                    status, msg_data = self.mail.fetch(email_id, '(RFC822)')
                    if status != 'OK' or not msg_data:
                        continue

                    raw_email = msg_data[0][1]
                    msg = email.message_from_bytes(raw_email)

                    sender = decode_email_header(msg.get('From', ''))
                    name, email_addr = parse_sender(sender)
                    subject = decode_email_header(msg.get('Subject', '')) or '(No Subject)'
                    date = msg.get('Date', '')
                    message_id = email_id.decode()

                    # Get snippet
                    snippet = get_email_body_plain(msg)

                    # Check for unsubscribe header
                    unsubscribe_header = msg.get('List-Unsubscribe', '')
                    has_unsubscribe = bool(unsubscribe_header)

                    batch_data.append({
                        'id': message_id,
                        'sender_name': name,
                        'sender_email': email_addr,
                        'subject': subject,
                        'date': date,
                        'snippet': snippet,
                        'has_unsubscribe_header': has_unsubscribe,
                        'message_id_header': msg.get('Message-ID', '')
                    })
                except Exception as e:
                    logger.warning(f"Error processing email: {e}")
                    continue

            return {
                'batch_info': {
                    'total_emails': total,
                    'start_index': start,
                    'end_index': end,
                    'batch_size': len(batch_data)
                },
                'emails': batch_data,
                'folders_available': self._get_folders()
            }

        except Exception as e:
            logger.error(f"Batch export error: {e}")
            return None

    def format_for_ai(self, batch_data):
        """Format batch data as readable text for AI analysis"""
        if not batch_data:
            return "No emails to analyze."

        emails = batch_data.get('emails', [])
        if not emails:
            return "No emails in this batch."

        lines = []
        lines.append("=" * 80)
        lines.append("EMAIL BATCH FOR TRIAGE ANALYSIS")
        lines.append(f"Batch: {batch_data['batch_info']['start_index'] + 1} - {batch_data['batch_info']['end_index']} of {batch_data['batch_info']['total_emails']}")
        lines.append("=" * 80)
        lines.append("")

        for i, email_data in enumerate(emails, 1):
            lines.append("-" * 40)
            lines.append(f"EMAIL #{i}")
            lines.append(f"ID: {email_data['id']}")
            lines.append(f"FROM: {email_data['sender_name']} <{email_data['sender_email']}>")
            lines.append(f"SUBJECT: {email_data['subject']}")
            lines.append(f"DATE: {email_data['date']}")

            if email_data['has_unsubscribe_header']:
                lines.append("*** FLAG: List-Unsubscribe header detected ***")

            snippet = email_data['snippet'][:300]
            lines.append(f"SNIPPET: {snippet}...")
            lines.append("")

        lines.append("-" * 40)
        lines.append("")
        lines.append("FOLDERS AVAILABLE: Action, Archive, Newsletters, Reference, Urgent")
        lines.append("")

        return "\n".join(lines)

    def _get_folders(self):
        """Get list of available folders"""
        try:
            status, folders = self.mail.list()
            if status == 'OK':
                folder_list = []
                for folder in folders:
                    folder_data = folder.decode().split(' "/" ')
                    if len(folder_data) == 2:
                        folder_list.append(folder_data[1].strip('"'))
                return folder_list
        except:
            pass
        return ['INBOX', 'Trash', 'Drafts', 'Sent']


class EmailCommandExecutor:
    """Execute JSON commands returned by AI"""

    def __init__(self, mail_connection):
        self.mail = mail_connection
        # Lazy import to avoid circular dependency
        self._unsubscribe_service = None

    @property
    def unsubscribe_service(self):
        """Lazy load unsubscribe service"""
        if self._unsubscribe_service is None:
            from unsubscribe_service import UnsubscribeService
            self._unsubscribe_service = UnsubscribeService(self.mail)
        return self._unsubscribe_service

    def execute_commands(self, commands_json):
        """
        Execute a list of JSON commands
        Expected format:
        [
            {"id": "123", "action": "delete"},
            {"id": "124", "action": "move", "destination": "Newsletters"},
            {"id": "125", "action": "unsubscribe"},
            {"id": "126", "action": "unsubscribe", "unsubscribe_url": "https://..."}
        ]
        """
        if isinstance(commands_json, str):
            try:
                commands = json.loads(commands_json)
            except json.JSONDecodeError as e:
                return {'error': f'Invalid JSON: {e}'}
        else:
            commands = commands_json

        results = []

        for cmd in commands:
            action = cmd.get('action', '').lower()
            email_id = cmd.get('id')

            if not email_id:
                results.append({'error': 'Missing email ID', 'command': cmd})
                continue

            try:
                if action == 'delete':
                    result = self._delete_email(email_id)
                elif action == 'move':
                    folder = cmd.get('destination', 'INBOX')
                    result = self._move_email(email_id, folder)
                elif action == 'archive':
                    result = self._move_email(email_id, 'Archive')
                elif action == 'unsubscribe':
                    sender = cmd.get('sender', '')
                    unsubscribe_url = cmd.get('unsubscribe_url')
                    result = self._unsubscribe(email_id, sender, unsubscribe_url)
                else:
                    result = {'error': f'Unknown action: {action}'}

                result['id'] = email_id
                result['action'] = action
                results.append(result)

            except Exception as e:
                results.append({
                    'id': email_id,
                    'action': action,
                    'error': str(e)
                })

        successful = sum(1 for r in results if 'error' not in r)
        return {
            'total': len(results),
            'successful': successful,
            'failed': len(results) - successful,
            'results': results
        }

    def _delete_email(self, email_id):
        """Move email to trash"""
        try:
            self.mail.move(email_id, 'INBOX/Trash')
            return {'status': 'success', 'detail': 'Moved to Trash'}
        except imaplib.IMAP4.error as e:
            # Try alternate trash location
            try:
                self.mail.move(email_id, 'Trash')
                return {'status': 'success', 'detail': 'Moved to Trash'}
            except:
                self.mail.store(email_id, '+FLAGS', '\\Deleted')
                self.mail.expunge()
                return {'status': 'success', 'detail': 'Marked for deletion'}

    def _move_email(self, email_id, folder):
        """Move email to specified folder"""
        # Map friendly names to actual folder names
        folder_map = {
            'action': 'Action',
            'archive': 'Archive',
            'newsletters': 'Newsletters',
            'reference': 'Reference',
            'urgent': 'Urgent'
        }

        actual_folder = folder_map.get(folder.lower(), folder)

        try:
            self.mail.move(email_id, f'INBOX/{actual_folder}')
            return {'status': 'success', 'detail': f'Moved to {actual_folder}'}
        except imaplib.IMAP4.error:
            # Try without INBOX prefix
            try:
                self.mail.move(email_id, actual_folder)
                return {'status': 'success', 'detail': f'Moved to {actual_folder}'}
            except Exception as e:
                return {'status': 'error', 'detail': str(e)}

    def _unsubscribe(self, email_id, sender='', unsubscribe_url=None):
        """
        Unsubscribe from sender using actual HTTP unsubscribe URL
        1. If unsubscribe_url provided, visits it to complete opt-out
        2. Deletes all emails from that sender
        """
        if sender:
            try:
                # If no URL provided, try to find it from the email
                if not unsubscribe_url:
                    try:
                        status, msg_data = self.mail.fetch(email_id, '(RFC822)')
                        if status == 'OK' and msg_data:
                            msg = email.message_from_bytes(msg_data[0][1])
                            from unsubscribe_service import find_unsubscribe_url
                            body = get_email_body_plain(msg)
                            unsubscribe_url = find_unsubscribe_url(body)
                    except Exception as e:
                        logger.warning(f"Could not find unsubscribe URL: {e}")

                # Use the unsubscribe service for actual unsubscribe
                service_result = self.unsubscribe_service.full_unsubscribe(
                    sender=sender,
                    unsubscribe_url=unsubscribe_url
                )

                return {
                    'status': 'success',
                    'detail': f"Unsubscribe {'succeeded' if service_result['unsubscribe_success'] else 'completed (delete only)'}: {service_result['emails_deleted']} emails deleted",
                    'unsubscribe_url_attempted': bool(unsubscribe_url),
                    'unsubscribe_success': service_result['unsubscribe_success'],
                    'emails_deleted': service_result['emails_deleted']
                }
            except Exception as e:
                return {'status': 'error', 'detail': str(e)}

        return {'status': 'error', 'detail': 'No sender specified'}


# System prompt template for email triage
EMAIL_TRIAGE_SYSTEM_PROMPT = """
You are my Personal AI Email Strategist. Your goal is to process batches of my Yahoo emails and provide actionable, structured outputs to help me manage my inbox.

**Task Workflow:**
1. **Categorization:** Analyze the provided batch of emails. For each email, provide:
   - **Sender/Subject**
   - **Urgency (High/Medium/Low/None)**
   - **Category** (Choose from: [Action Required, Newsletter, Reference, Junk, Urgent])
   - **Suggested Action** ([Delete, Unsubscribe, Move to Folder: X, Archive])
   - **Reasoning** (One sentence explaining why)

2. **Output Format:** Always present your analysis in a Markdown table.

3. **Execution Ready:** If I choose to proceed, your final response should include a "Summary of Commands" section that outputs in a clean JSON format so I can pass it to my automation script.

**Constraint Checklist:**
- Never perform an action without my "Approved" signal for that specific batch.
- If an email contains a "List-Unsubscribe" header or link, explicitly flag it as ACTION: UNSUBSCRIBE.
- Maintain a professional and efficient tone.

**Current Context:**
- My goal is to achieve Inbox Zero.
- I am a professional grant manager; ignore any "junk" but be hyper-vigilant for any communication related to grant recovery or professional deadlines.
- Current folders available: [Action, Archive, Newsletters, Reference, Urgent].

**JSON Output Format:**
Always include this JSON block after your analysis table:
```json
[
  {"id": "EMAIL_ID", "action": "delete"},
  {"id": "EMAIL_ID", "action": "move", "destination": "Newsletters"},
  {"id": "EMAIL_ID", "action": "unsubscribe"}
]
```
"""