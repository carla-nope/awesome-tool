"""
Unsubscribe Service - Handles actual unsubscribe operations
Visits unsubscribe URLs and completes opt-out at sender's server
"""

import requests
import re
import logging
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure requests session with browser-like headers
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1'
}

# Unsubscribe URL patterns
UNSUBSCRIBE_PATTERNS = [
    r'unsubscribe[^"\'<>\s]*',
    r'opt-?out[^"\'<>\s]*',
    r'manage[^"\'<>\s]*(subscription|preferences|email)',
    r'email[^"\'<>\s]*preferences',
    r'notification[^"\'<>\s]*preferences',
    r'list[^"\'<>\s]*unsub',
    r'\?unsubcribe=',
    r'\?optout=',
    r'\?u=',
]


def find_unsubscribe_url(email_body, existing_urls=None):
    """
    Find unsubscribe URL from email body or existing URLs
    Returns the unsubscribe URL or None
    """
    all_urls = set()

    if existing_urls:
        all_urls.update(existing_urls)

    # Extract from email body if provided
    if email_body:
        url_pattern = re.compile(
            r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
        )
        found = url_pattern.findall(email_body)
        all_urls.update(found)

    # Search for unsubscribe-related URLs
    for url in all_urls:
        url_lower = url.lower()
        parsed = urlparse(url)
        path_domain = f"{parsed.netloc}{parsed.path}".lower()

        for pattern in UNSUBSCRIBE_PATTERNS:
            if re.search(pattern, url_lower) or re.search(pattern, path_domain):
                return url

    return None


def find_unsubscribe_link_in_html(html_content):
    """
    Parse HTML content and find actual unsubscribe link
    Looks for <a> tags with unsubscribe-related text
    """
    try:
        soup = BeautifulSoup(html_content, 'html.parser')

        # Find all links
        for link in soup.find_all('a', href=True):
            link_text = link.get_text().lower()
            link_href = link.get('href', '').lower()

            unsubscribe_keywords = ['unsubscribe', 'opt out', 'opt-out', 'stop email', 'remove me']

            for keyword in unsubscribe_keywords:
                if keyword in link_text or keyword in link_href:
                    href = link.get('href')
                    if href.startswith('http'):
                        return href
                    elif href.startswith('/'):
                        # Try to construct full URL
                        parsed = urlparse(html_content)
                        base_url = f"{parsed.scheme}://{parsed.netloc}"
                        return urljoin(base_url, href)

        # Also search by onclick handlers
        for element in soup.find_all(attrs={'onclick': True}):
            onclick = element.get('onclick', '')
            if 'unsubscribe' in onclick.lower():
                # Try to extract URL from onclick
                match = re.search(r'["\']([^"\']*unsubscribe[^"\']*)["\']', onclick)
                if match:
                    return match.group(1)

    except Exception as e:
        logger.warning(f"HTML parsing error: {e}")

    return None


def check_unsubscribe_page(url, session=None):
    """
    Check if URL is a valid unsubscribe page
    Returns (is_valid, page_content, unsubscribe_link)
    """
    if session is None:
        session = requests.Session()

    try:
        response = session.get(url, headers=HEADERS, timeout=15, allow_redirects=True)

        if response.status_code != 200:
            return False, None, None

        # Check page title or content
        content_lower = response.text.lower()

        # Check for unsubscribe confirmation or form
        if any(keyword in content_lower for keyword in [
            'unsubscribe', 'opt-out', 'opt out', 'email preferences',
            'email is now unsubscribed', 'successfully unsubscribed',
            'you have been unsubscribed', 'stop sending'
        ]):
            # Try to find unsubscribe button/link
            unsubscribe_link = find_unsubscribe_link_in_html(response.text)
            return True, response.text, unsubscribe_link

        return True, response.text, None

    except requests.RequestException as e:
        logger.error(f"Request error: {e}")
        return False, None, None


def attempt_unsubscribe(url, email_id=None, session=None):
    """
    Attempt to complete unsubscribe by visiting the URL
    Returns result dict with success status and details
    """
    if session is None:
        session = requests.Session()

    result = {
        'email_id': email_id,
        'unsubscribe_url': url,
        'success': False,
        'method': None,
        'details': None,
        'needs_manual': False
    }

    try:
        # First check what kind of page this is
        is_valid, page_content, found_link = check_unsubscribe_page(url, session)

        if not is_valid:
            result['details'] = 'Failed to access unsubscribe page'
            result['needs_manual'] = True
            return result

        # If we found a link on the page, use it
        if found_link and found_link != url:
            url = found_link
            result['unsubscribe_url'] = url
            is_valid, page_content, _ = check_unsubscribe_page(url, session)

        # Determine unsubscribe method
        content_lower = page_content.lower() if page_content else ''

        # Method 1: One-click unsubscribe (RFC 8058)
        if 'list-unsubscribe' in content_lower or 'one-click' in content_lower:
            # Check for POST-based unsubscribe
            if session.method == 'POST':
                result['method'] = 'one-click-post'
                # Would need to follow the spec for one-click
                result['details'] = 'One-click unsubscribe detected - needs confirmation'
                result['needs_manual'] = True

        # Method 2: Direct confirmation page
        if 'confirm' in content_lower or 'unsubscribe' in content_lower:
            if any(button in content_lower for button in ['confirm', 'unsubscribe', 'opt-out', 'stop']):
                # Submit the form if present
                soup = BeautifulSoup(page_content, 'html.parser')
                form = soup.find('form')

                if form:
                    action = form.get('action', url)
                    method = form.get('method', 'GET').upper()

                    # Build form data
                    form_data = {}
                    for input_field in form.find_all('input'):
                        name = input_field.get('name')
                        value = input_field.get('value', '')
                        input_type = input_field.get('type', 'text').lower()
                        if name and input_type not in ['submit', 'button']:
                            form_data[name] = value

                    # Submit form
                    form_response = session.request(
                        method=method,
                        url=action,
                        data=form_data if form_data else None,
                        headers=HEADERS,
                        timeout=15,
                        allow_redirects=True
                    )

                    if form_response.status_code in [200, 302, 303]:
                        result['success'] = True
                        result['method'] = 'form-submission'
                        result['details'] = 'Form submitted successfully'
                        return result

                # Try clicking the button via GET
                result['method'] = 'confirmation-page'
                result['details'] = 'Confirmation page found - manual click may be needed'
                result['needs_manual'] = True

        # Method 3: Direct unsubscribe link (GET request)
        if any(pattern in url.lower() for pattern in ['unsubscribe', 'optout', 'opt-out', 'unsub']):
            response = session.get(url, headers=HEADERS, timeout=15, allow_redirects=True)

            if response.status_code in [200, 302, 303]:
                final_url = response.url.lower()

                # Check if we reached a success page
                if any(success_word in final_url for success_word in [
                    'unsubscribed', 'success', 'confirmed', 'removed', 'done'
                ]):
                    result['success'] = True
                    result['method'] = 'direct-link'
                    result['details'] = 'Successfully unsubscribed via direct link'
                elif any(keyword in response.text.lower() for keyword in [
                    'unsubscribed', 'you have been removed', 'successfully'
                ]):
                    result['success'] = True
                    result['method'] = 'direct-link'
                    result['details'] = 'Successfully unsubscribed'
                else:
                    # Page reached but status unclear
                    result['method'] = 'direct-link-visited'
                    result['details'] = 'Link visited, confirmation unclear'
                    result['needs_manual'] = True

        # Method 4: Mailto unsubscribe (requires List-Unsubscribe-Post)
        if url.startswith('mailto:'):
            result['method'] = 'mailto'
            result['details'] = 'mailto unsubscribe - manual action required'
            result['needs_manual'] = True

    except requests.RequestException as e:
        result['details'] = f'Request failed: {str(e)}'
        result['needs_manual'] = True

    return result


def bulk_unsubscribe_from_sender(sender, mail_connection, unsubscribe_url=None):
    """
    Complete unsubscribe workflow for a sender:
    1. Visit unsubscribe URL
    2. Delete all emails from sender
    Returns result summary
    """
    results = {
        'sender': sender,
        'unsubscribe_attempted': False,
        'unsubscribe_success': False,
        'unsubscribe_details': None,
        'emails_deleted': 0,
        'errors': []
    }

    # Step 1: Attempt unsubscribe if URL provided
    if unsubscribe_url:
        results['unsubscribe_attempted'] = True
        unsubscribe_result = attempt_unsubscribe(unsubscribe_url)
        results['unsubscribe_success'] = unsubscribe_result['success']
        results['unsubscribe_details'] = unsubscribe_result
    else:
        results['unsubscribe_details'] = {'details': 'No unsubscribe URL found'}

    # Step 2: Delete all emails from this sender
    try:
        search_query = f'FROM "{sender}"'
        status, messages = mail_connection.search(None, search_query)

        if status == 'OK' and messages[0]:
            email_ids = messages[0].split()
            for email_id in email_ids:
                try:
                    mail_connection.move(email_id, 'INBOX/Trash')
                    results['emails_deleted'] += 1
                except Exception as e:
                    results['errors'].append(f'Failed to delete {email_id}: {str(e)}')
        else:
            results['errors'].append('No emails found from sender')

    except Exception as e:
        results['errors'].append(f'Email deletion failed: {str(e)}')

    return results


class UnsubscribeService:
    """
    Service class for unsubscribe operations
    """

    def __init__(self, mail_connection=None):
        self.mail = mail_connection
        self.session = requests.Session()

    def get_unsubscribe_url(self, email_body, existing_urls=None):
        """Find unsubscribe URL from email content"""
        return find_unsubscribe_url(email_body, existing_urls)

    def try_unsubscribe(self, unsubscribe_url, email_id=None):
        """Attempt unsubscribe via URL"""
        return attempt_unsubscribe(unsubscribe_url, email_id, self.session)

    def full_unsubscribe(self, sender, unsubscribe_url=None):
        """Complete unsubscribe workflow"""
        if not self.mail:
            return {'error': 'No mail connection'}

        return bulk_unsubscribe_from_sender(sender, self.mail, unsubscribe_url)

    def close(self):
        """Close the HTTP session"""
        self.session.close()