"""Gmail Integration for reading and searching emails."""
import os

# Google's OAuth server sometimes grants a superset of the requested scopes
# (e.g. tacking on https://www.googleapis.com/auth/cse for accounts with
# Gmail client-side encryption enabled) - oauthlib treats any scope mismatch
# as a hard error by default (`raise Warning(...)`, which is a real Exception
# in Python), aborting an otherwise-successful token exchange. Must be set
# before oauthlib's OAuth2Session is constructed, hence top-of-module.
os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")

import pickle
import base64
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow, Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


# If modifying these scopes, delete the token file
# gmail.modify allows: marking as read, archiving, labeling, trashing (but not permanent deletion)
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.modify'
]

# Paths
SKILLS_DIR = Path(__file__).parent
CREDENTIALS_FILE = SKILLS_DIR / 'credentials.json'
TOKEN_FILE = Path(__file__).parent.parent.parent / 'data' / 'gmail_token.json'

# Separate client for the web-based reconnect flow (chatty_web_server's
# /api/chatty/gmail/* routes): Google's "Desktop app" OAuth client type used
# by CREDENTIALS_FILE above only supports loopback redirect URIs (that's why
# get_gmail_service() opens a browser on the server host via run_local_server
# instead of redirecting anywhere). A custom HTTPS redirect_uri - required so
# the *user's* browser can complete the flow against the real server -
# requires a "Web application" OAuth client instead, downloaded separately
# from Google Cloud Console and placed here.
WEB_CREDENTIALS_FILE = SKILLS_DIR / 'web_credentials.json'
GMAIL_OAUTH_REDIRECT_URI = os.getenv(
    "GMAIL_OAUTH_REDIRECT_URI", "https://fuadmefleh.fyi/api/chatty/gmail/callback"
)
OAUTH_STATE_TTL_SECONDS = 600

# In-memory CSRF state for the web reconnect flow: state -> (code_verifier,
# issued_at). Single-user app, so no need to persist this anywhere durable -
# it only has to survive the few seconds between redirecting to Google's
# consent screen and Google redirecting back.
_pending_oauth_states: Dict[str, Tuple[str, float]] = {}


def get_gmail_service():
    """Get authenticated Gmail API service."""
    creds = None
    
    # Load token if it exists
    if TOKEN_FILE.exists():
        with open(TOKEN_FILE, 'rb') as token:
            creds = pickle.load(token)
    
    # If no valid credentials, let user log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_FILE.exists():
                raise FileNotFoundError(
                    f"Gmail credentials file not found at {CREDENTIALS_FILE}. "
                    "Please download credentials.json from Google Cloud Console "
                    "and place it in the skills/gmail/ directory."
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_FILE), SCOPES)
            
            print("\n" + "="*70)
            print("GMAIL AUTHENTICATION")
            print("="*70)
            print("\nOpening browser for authentication...")
            print("After authorizing, you can close the browser tab.")
            print("="*70 + "\n")
            
            # Try with explicit port and success message
            try:
                creds = flow.run_local_server(
                    port=8080,
                    success_message='Authentication successful! You can close this window.',
                    open_browser=True
                )
            except Exception as e:
                print(f"\nError during authentication: {e}")
                print("\nTrying alternative method...")
                creds = flow.run_local_server(port=0, open_browser=True)
            
            print("\n" + "="*70)
            print("Authentication successful!")
            print("="*70 + "\n")
        
        # Save the credentials for future use
        TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(TOKEN_FILE, 'wb') as token:
            pickle.dump(creds, token)
    
    return build('gmail', 'v1', credentials=creds)


def get_gmail_status() -> Dict[str, Any]:
    """Report Gmail connection status for the web dashboard without
    triggering any auth flow or network call - just inspects what's on disk.
    Deliberately doesn't attempt a token refresh here (that happens lazily,
    on actual use, inside get_gmail_service); this is a cheap read-only
    check, not an action."""
    if not TOKEN_FILE.exists():
        return {"status": "disconnected", "reconnect_available": WEB_CREDENTIALS_FILE.exists()}
    try:
        with open(TOKEN_FILE, 'rb') as token:
            creds = pickle.load(token)
    except Exception:
        return {"status": "disconnected", "reconnect_available": WEB_CREDENTIALS_FILE.exists()}

    if creds and creds.valid:
        status = "connected"
    elif creds and creds.expired and creds.refresh_token:
        status = "expired"
    else:
        status = "disconnected"
    return {"status": status, "reconnect_available": WEB_CREDENTIALS_FILE.exists()}


def _prune_expired_oauth_states() -> None:
    cutoff = time.time() - OAUTH_STATE_TTL_SECONDS
    for state, (_, issued_at) in list(_pending_oauth_states.items()):
        if issued_at < cutoff:
            del _pending_oauth_states[state]


def get_gmail_auth_url() -> str:
    """Build the Google consent-screen URL for the web-based reconnect flow
    and stash the PKCE verifier for this attempt under its `state`, so
    complete_gmail_auth can finish the exchange when Google redirects back.
    Distinct from get_gmail_service's local-server flow, which opens a
    browser on the server host and doesn't work from a remote web UI."""
    if not WEB_CREDENTIALS_FILE.exists():
        raise FileNotFoundError(
            f"Web OAuth client not found at {WEB_CREDENTIALS_FILE}. Create a 'Web application' "
            f"OAuth client in Google Cloud Console with authorized redirect URI "
            f"{GMAIL_OAUTH_REDIRECT_URI!r} and save its downloaded JSON there."
        )
    flow = Flow.from_client_secrets_file(
        str(WEB_CREDENTIALS_FILE), scopes=SCOPES, redirect_uri=GMAIL_OAUTH_REDIRECT_URI,
        autogenerate_code_verifier=True,
    )
    auth_url, state = flow.authorization_url(
        access_type='offline', prompt='consent', include_granted_scopes='true',
    )
    _prune_expired_oauth_states()
    _pending_oauth_states[state] = (flow.code_verifier, time.time())
    return auth_url


def complete_gmail_auth(code: str, state: str) -> None:
    """Exchange an authorization code from the OAuth callback for a token,
    completing the web reconnect flow started by get_gmail_auth_url. Saves
    the result in the same pickle format get_gmail_service() reads, so
    existing Gmail skill calls pick it up transparently.

    Raises ValueError if `state` doesn't match one we issued (forged/replayed
    callback, or one that's aged out past OAUTH_STATE_TTL_SECONDS)."""
    _prune_expired_oauth_states()
    pending = _pending_oauth_states.pop(state, None)
    if pending is None:
        raise ValueError("Unknown or expired OAuth state")
    code_verifier, _ = pending

    flow = Flow.from_client_secrets_file(
        str(WEB_CREDENTIALS_FILE), scopes=SCOPES, redirect_uri=GMAIL_OAUTH_REDIRECT_URI,
        autogenerate_code_verifier=False, code_verifier=code_verifier,
    )
    flow.fetch_token(code=code)

    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(TOKEN_FILE, 'wb') as token:
        pickle.dump(flow.credentials, token)


def disconnect_gmail() -> bool:
    """Delete the stored Gmail token, forcing the next use to reconnect.
    Returns whether a token was actually present to delete."""
    if TOKEN_FILE.exists():
        TOKEN_FILE.unlink()
        return True
    return False


def parse_email_body(payload: Dict[str, Any]) -> str:
    """Extract email body from message payload."""
    body_text = ""
    
    # Check if body is directly in payload
    if 'body' in payload and 'data' in payload['body']:
        body_data = payload['body']['data']
        body_text = base64.urlsafe_b64decode(body_data).decode('utf-8')
    
    # Check for multipart messages
    elif 'parts' in payload:
        for part in payload['parts']:
            mime_type = part.get('mimeType', '')
            
            # Prefer text/plain over text/html
            if mime_type == 'text/plain':
                if 'data' in part['body']:
                    body_data = part['body']['data']
                    body_text = base64.urlsafe_b64decode(body_data).decode('utf-8')
                    break
            
            # Fallback to HTML
            elif mime_type == 'text/html' and not body_text:
                if 'data' in part['body']:
                    body_data = part['body']['data']
                    body_text = base64.urlsafe_b64decode(body_data).decode('utf-8')
            
            # Handle nested parts
            elif 'parts' in part:
                nested_body = parse_email_body(part)
                if nested_body:
                    body_text = nested_body
    
    return body_text.strip()


def get_header_value(headers: List[Dict[str, str]], name: str) -> Optional[str]:
    """Get header value by name."""
    for header in headers:
        if header['name'].lower() == name.lower():
            return header['value']
    return None


def format_email_message(message: Dict[str, Any], include_body: bool = True) -> Dict[str, Any]:
    """Format email message into readable structure."""
    headers = message['payload']['headers']
    
    result = {
        'id': message['id'],
        'thread_id': message['threadId'],
        'subject': get_header_value(headers, 'Subject') or '(No Subject)',
        'from': get_header_value(headers, 'From') or 'Unknown',
        'to': get_header_value(headers, 'To') or 'Unknown',
        'date': get_header_value(headers, 'Date') or 'Unknown',
        'snippet': message.get('snippet', ''),
        'labels': message.get('labelIds', []),
    }
    
    if include_body:
        result['body'] = parse_email_body(message['payload'])
    
    return result


def search_emails(
    query: str = '',
    max_results: int = 10,
    include_body: bool = False,
    label_ids: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """
    Search Gmail messages.
    
    Args:
        query: Gmail search query (e.g., "from:john@example.com subject:meeting")
        max_results: Maximum number of results to return
        include_body: Whether to include full email body in results
        label_ids: List of label IDs to filter by (e.g., ['INBOX', 'UNREAD'])
    
    Returns:
        List of formatted email messages
    """
    try:
        service = get_gmail_service()
        
        # Build the request
        request_params = {
            'userId': 'me',
            'maxResults': max_results,
        }
        
        if query:
            request_params['q'] = query
        
        if label_ids:
            request_params['labelIds'] = label_ids
        
        # Get message list
        results = service.users().messages().list(**request_params).execute()
        messages = results.get('messages', [])
        
        if not messages:
            return []
        
        # Get full message details
        formatted_messages = []
        for msg in messages:
            msg_data = service.users().messages().get(
                userId='me',
                id=msg['id'],
                format='full'
            ).execute()
            formatted_messages.append(format_email_message(msg_data, include_body))
        
        return formatted_messages
    
    except HttpError as error:
        raise Exception(f"Gmail API error: {error}")


def get_unread_emails(max_results: int = 10) -> List[Dict[str, Any]]:
    """Get unread emails from inbox."""
    return search_emails(
        query='is:unread',
        max_results=max_results,
        label_ids=['INBOX']
    )


def get_emails_from_sender(sender: str, max_results: int = 10) -> List[Dict[str, Any]]:
    """Get emails from a specific sender."""
    return search_emails(
        query=f'from:{sender}',
        max_results=max_results
    )


def get_emails_by_subject(subject: str, max_results: int = 10) -> List[Dict[str, Any]]:
    """Search emails by subject."""
    return search_emails(
        query=f'subject:{subject}',
        max_results=max_results
    )


def get_recent_emails(days: int = 7, max_results: int = 10) -> List[Dict[str, Any]]:
    """Get emails from the last N days."""
    # Calculate date in format Gmail expects
    date_from = datetime.now() - timedelta(days=days)
    date_str = date_from.strftime('%Y/%m/%d')
    
    return search_emails(
        query=f'after:{date_str}',
        max_results=max_results
    )


def read_email(message_id: str) -> Dict[str, Any]:
    """Read full email by message ID."""
    try:
        service = get_gmail_service()
        message = service.users().messages().get(
            userId='me',
            id=message_id,
            format='full'
        ).execute()
        
        return format_email_message(message, include_body=True)
    
    except HttpError as error:
        raise Exception(f"Gmail API error: {error}")


def get_email_count(query: str = '') -> int:
    """Get count of emails matching query."""
    try:
        service = get_gmail_service()
        results = service.users().messages().list(
            userId='me',
            q=query,
            maxResults=1
        ).execute()
        
        return results.get('resultSizeEstimate', 0)
    
    except HttpError as error:
        raise Exception(f"Gmail API error: {error}")


def mark_as_read(message_ids: List[str]) -> Dict[str, Any]:
    """Mark emails as read.
    
    Args:
        message_ids: List of Gmail message IDs to mark as read
        
    Returns:
        Result dictionary with success status and details
    """
    try:
        service = get_gmail_service()
        
        # Batch modify to remove UNREAD label
        body = {
            'ids': message_ids,
            'removeLabelIds': ['UNREAD']
        }
        
        service.users().messages().batchModify(
            userId='me',
            body=body
        ).execute()

        return {
            'success': True,
            'count': len(message_ids),
            'message': f'Marked {len(message_ids)} email(s) as read'
        }
    
    except HttpError as error:
        return {
            'success': False,
            'error': f'Gmail API error: {error}'
        }


def archive_emails(message_ids: List[str]) -> Dict[str, Any]:
    """Archive emails (remove from INBOX).
    
    Args:
        message_ids: List of Gmail message IDs to archive
        
    Returns:
        Result dictionary with success status and details
    """
    try:
        service = get_gmail_service()
        
        # Batch modify to remove INBOX label
        body = {
            'ids': message_ids,
            'removeLabelIds': ['INBOX']
        }
        
        service.users().messages().batchModify(
            userId='me',
            body=body
        ).execute()

        return {
            'success': True,
            'count': len(message_ids),
            'message': f'Archived {len(message_ids)} email(s)'
        }
    
    except HttpError as error:
        return {
            'success': False,
            'error': f'Gmail API error: {error}'
        }


def trash_emails(message_ids: List[str]) -> Dict[str, Any]:
    """Move emails to trash.
    
    Args:
        message_ids: List of Gmail message IDs to trash
        
    Returns:
        Result dictionary with success status and details
    """
    try:
        service = get_gmail_service()
        
        # Batch trash messages
        body = {
            'ids': message_ids
        }
        
        service.users().messages().batchDelete(
            userId='me',
            body=body
        ).execute()
        
        return {
            'success': True,
            'count': len(message_ids),
            'message': f'Moved {len(message_ids)} email(s) to trash'
        }
    
    except HttpError as error:
        return {
            'success': False,
            'error': f'Gmail API error: {error}'
        }


def add_label(message_ids: List[str], label_name: str) -> Dict[str, Any]:
    """Add label to emails.
    
    Args:
        message_ids: List of Gmail message IDs
        label_name: Name of the label to add
        
    Returns:
        Result dictionary with success status and details
    """
    try:
        service = get_gmail_service()
        
        # Get or create label
        labels = service.users().labels().list(userId='me').execute()
        label_id = None
        
        for label in labels.get('labels', []):
            if label['name'].lower() == label_name.lower():
                label_id = label['id']
                break
        
        # Create label if it doesn't exist
        if not label_id:
            label_object = {
                'name': label_name,
                'labelListVisibility': 'labelShow',
                'messageListVisibility': 'show'
            }
            created_label = service.users().labels().create(
                userId='me',
                body=label_object
            ).execute()
            label_id = created_label['id']
        
        # Batch modify to add label
        body = {
            'ids': message_ids,
            'addLabelIds': [label_id]
        }
        
        service.users().messages().batchModify(
            userId='me',
            body=body
        ).execute()

        return {
            'success': True,
            'count': len(message_ids),
            'label': label_name,
            'message': f'Added label "{label_name}" to {len(message_ids)} email(s)'
        }
    
    except HttpError as error:
        return {
            'success': False,
            'error': f'Gmail API error: {error}'
        }


def get_promotional_emails(max_results: int = 50) -> List[Dict[str, Any]]:
    """Get promotional emails from the CATEGORY_PROMOTIONS label.
    
    Args:
        max_results: Maximum number of emails to return
        
    Returns:
        List of formatted email messages
    """
    return search_emails(
        query='category:promotions',
        max_results=max_results,
        include_body=False
    )


def get_old_read_emails(days: int = 30, max_results: int = 100) -> List[Dict[str, Any]]:
    """Get old read emails from inbox.
    
    Args:
        days: Get emails older than this many days
        max_results: Maximum number of emails to return
        
    Returns:
        List of formatted email messages
    """
    # Calculate date in format Gmail expects
    date_before = datetime.now() - timedelta(days=days)
    date_str = date_before.strftime('%Y/%m/%d')
    
    return search_emails(
        query=f'in:inbox is:read before:{date_str}',
        max_results=max_results,
        include_body=False
    )


def get_social_emails(max_results: int = 50) -> List[Dict[str, Any]]:
    """Get social media notification emails.
    
    Args:
        max_results: Maximum number of emails to return
        
    Returns:
        List of formatted email messages
    """
    return search_emails(
        query='category:social',
        max_results=max_results,
        include_body=False
    )


if __name__ == "__main__":
    # Test the integration
    print("Testing Gmail integration...")
    
    try:
        # Get unread count
        unread_count = get_email_count('is:unread')
        print(f"\nUnread emails: {unread_count}")
        
        # Get recent emails
        print("\nRecent emails (last 3 days):")
        emails = get_recent_emails(days=3, max_results=5)
        for email in emails:
            print(f"  - From: {email['from']}")
            print(f"    Subject: {email['subject']}")
            print(f"    Date: {email['date']}")
            print(f"    Snippet: {email['snippet'][:80]}...")
            print()
        
        print("Gmail integration test completed successfully!")
    
    except Exception as e:
        print(f"Error: {e}")
