"""Gmail skill tools for LLM function calling.

These tools are dynamically loaded by the framework when the skill is activated.
"""
import json
import logging
import sys
import importlib.util
from pathlib import Path
from typing import Dict, Any

# Add project root to path for src imports
project_root = str(Path(__file__).parent.parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.core.skill_tool import SkillTool

# Load the gmail_integration module from THIS skill folder explicitly
try:
    _integration_path = Path(__file__).parent / "gmail_integration.py"
    _spec = importlib.util.spec_from_file_location("gmail_integration_module", _integration_path)
    _integration_module = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_integration_module)
    
    search_emails = _integration_module.search_emails
    get_unread_emails = _integration_module.get_unread_emails
    get_emails_from_sender = _integration_module.get_emails_from_sender
    get_emails_by_subject = _integration_module.get_emails_by_subject
    get_recent_emails = _integration_module.get_recent_emails
    read_email = _integration_module.read_email
    get_email_count = _integration_module.get_email_count
    mark_as_read = _integration_module.mark_as_read
    archive_emails = _integration_module.archive_emails
    trash_emails = _integration_module.trash_emails
    add_label = _integration_module.add_label
    get_promotional_emails = _integration_module.get_promotional_emails
    get_old_read_emails = _integration_module.get_old_read_emails
    get_social_emails = _integration_module.get_social_emails
    GMAIL_AVAILABLE = True
except Exception as e:
    GMAIL_AVAILABLE = False
    logging.warning(f"Gmail integration not available: {e}")


def _check_gmail_available() -> str:
    """Check if Gmail is available, return error message if not."""
    if not GMAIL_AVAILABLE:
        return "Gmail tools are not available. Please install required packages: pip install google-auth-oauthlib google-auth-httplib2 google-api-python-client"
    return None


class GetUnreadEmails(SkillTool):
    """Get unread emails from Gmail inbox."""
    
    name = "get_unread_emails"
    description = "Get unread emails from Gmail inbox. Use this when user asks about unread emails, new messages, or checking their inbox. Keep max_results under 20 for efficiency."
    parameters = {
        "type": "object",
        "properties": {
            "max_results": {
                "type": "integer",
                "description": "Maximum number of emails to return (default: 10, max recommended: 20)"
            }
        },
        "required": []
    }
    
    async def execute(self, max_results: int = 10) -> str:
        error = _check_gmail_available()
        if error:
            return error
        
        try:
            emails = get_unread_emails(max_results=max_results)
            return json.dumps({
                "count": len(emails),
                "emails": emails
            }, indent=2)
        except Exception as e:
            return f"Error fetching unread emails: {str(e)}"


class SearchEmails(SkillTool):
    """Search Gmail emails with custom query."""
    
    name = "search_emails"
    description = "Search Gmail emails using Gmail search syntax. Supports searching by sender (from:), subject (subject:), date (after:, before:), and text content. Keep max_results under 20. Avoid include_body unless absolutely necessary."
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Gmail search query (e.g., 'from:john@example.com', 'subject:meeting', 'invoice')"
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of emails to return (default: 10, max recommended: 20)"
            },
            "include_body": {
                "type": "boolean",
                "description": "Whether to include full email body. WARNING: Significantly increases data size. Only use if user explicitly needs full content (default: false)"
            }
        },
        "required": ["query"]
    }
    
    async def execute(self, query: str, max_results: int = 10, include_body: bool = False) -> str:
        error = _check_gmail_available()
        if error:
            return error
        
        try:
            emails = search_emails(query=query, max_results=max_results, include_body=include_body)
            return json.dumps({
                "query": query,
                "count": len(emails),
                "emails": emails
            }, indent=2)
        except Exception as e:
            return f"Error searching emails: {str(e)}"


class GetEmailsFromSender(SkillTool):
    """Get emails from a specific sender."""
    
    name = "get_emails_from_sender"
    description = "Get emails from a specific sender. Use this when user asks for emails from a particular person or email address."
    parameters = {
        "type": "object",
        "properties": {
            "sender": {
                "type": "string",
                "description": "Email address or name of the sender"
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of emails to return (default: 10)"
            }
        },
        "required": ["sender"]
    }
    
    async def execute(self, sender: str, max_results: int = 10) -> str:
        error = _check_gmail_available()
        if error:
            return error
        
        try:
            emails = get_emails_from_sender(sender=sender, max_results=max_results)
            return json.dumps({
                "sender": sender,
                "count": len(emails),
                "emails": emails
            }, indent=2)
        except Exception as e:
            return f"Error fetching emails from sender: {str(e)}"


class GetRecentEmails(SkillTool):
    """Get recent emails from the last N days."""
    
    name = "get_recent_emails"
    description = "Get recent emails from the last N days. Use this when user asks for recent emails, emails from this week, or emails from the past few days. Keep max_results under 20."
    parameters = {
        "type": "object",
        "properties": {
            "days": {
                "type": "integer",
                "description": "Number of days to look back (default: 7)"
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of emails to return (default: 10, max recommended: 20)"
            }
        },
        "required": []
    }
    
    async def execute(self, days: int = 7, max_results: int = 10) -> str:
        error = _check_gmail_available()
        if error:
            return error
        
        try:
            emails = get_recent_emails(days=days, max_results=max_results)
            return json.dumps({
                "days": days,
                "count": len(emails),
                "emails": emails
            }, indent=2)
        except Exception as e:
            return f"Error fetching recent emails: {str(e)}"


class ReadEmail(SkillTool):
    """Read full email content by message ID."""
    
    name = "read_email"
    description = "Read full email content including body by message ID. Use this to get the complete content of a specific email."
    parameters = {
        "type": "object",
        "properties": {
            "message_id": {
                "type": "string",
                "description": "Gmail message ID"
            }
        },
        "required": ["message_id"]
    }
    
    async def execute(self, message_id: str) -> str:
        error = _check_gmail_available()
        if error:
            return error
        
        try:
            email = read_email(message_id=message_id)
            return json.dumps(email, indent=2)
        except Exception as e:
            return f"Error reading email: {str(e)}"


class GetEmailCount(SkillTool):
    """Get count of emails matching a query."""
    
    name = "get_email_count"
    description = "Get count of emails matching a query. Use this to count unread emails, emails from a sender, or emails matching search criteria."
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Gmail search query (e.g., 'is:unread', 'from:john@example.com'). Leave empty to count all emails."
            }
        },
        "required": []
    }
    
    async def execute(self, query: str = "") -> str:
        error = _check_gmail_available()
        if error:
            return error
        
        try:
            count = get_email_count(query=query)
            return json.dumps({
                "query": query or "all emails",
                "count": count
            }, indent=2)
        except Exception as e:
            return f"Error counting emails: {str(e)}"


class MarkAsRead(SkillTool):
    """Mark emails as read."""
    
    name = "mark_as_read"
    description = "Mark one or more emails as read by their message IDs. Use this to clean up unread emails."
    parameters = {
        "type": "object",
        "properties": {
            "message_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of Gmail message IDs to mark as read"
            }
        },
        "required": ["message_ids"]
    }
    
    async def execute(self, message_ids: list) -> str:
        error = _check_gmail_available()
        if error:
            return error
        
        try:
            result = mark_as_read(message_ids=message_ids)
            return json.dumps(result, indent=2)
        except Exception as e:
            return f"Error marking emails as read: {str(e)}"


class ArchiveEmails(SkillTool):
    """Archive emails (remove from inbox)."""
    
    name = "archive_emails"
    description = "Archive one or more emails by removing them from the inbox. Emails remain accessible in All Mail. Use this to clean up the inbox while keeping emails."
    parameters = {
        "type": "object",
        "properties": {
            "message_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of Gmail message IDs to archive"
            }
        },
        "required": ["message_ids"]
    }
    
    async def execute(self, message_ids: list) -> str:
        error = _check_gmail_available()
        if error:
            return error
        
        try:
            result = archive_emails(message_ids=message_ids)
            return json.dumps(result, indent=2)
        except Exception as e:
            return f"Error archiving emails: {str(e)}"


class TrashEmails(SkillTool):
    """Move emails to trash."""
    
    name = "trash_emails"
    description = "Move one or more emails to trash. Emails can be recovered from trash for 30 days. Use this for unwanted emails."
    parameters = {
        "type": "object",
        "properties": {
            "message_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of Gmail message IDs to trash"
            }
        },
        "required": ["message_ids"]
    }
    
    async def execute(self, message_ids: list) -> str:
        error = _check_gmail_available()
        if error:
            return error
        
        try:
            result = trash_emails(message_ids=message_ids)
            return json.dumps(result, indent=2)
        except Exception as e:
            return f"Error trashing emails: {str(e)}"


class AddLabel(SkillTool):
    """Add label to emails."""
    
    name = "add_label"
    description = "Add a label to one or more emails for organization. Creates the label if it doesn't exist. Use this to categorize emails."
    parameters = {
        "type": "object",
        "properties": {
            "message_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of Gmail message IDs to label"
            },
            "label_name": {
                "type": "string",
                "description": "Name of the label to add (e.g., 'Important', 'Finance', 'Shopping')"
            }
        },
        "required": ["message_ids", "label_name"]
    }
    
    async def execute(self, message_ids: list, label_name: str) -> str:
        error = _check_gmail_available()
        if error:
            return error
        
        try:
            result = add_label(message_ids=message_ids, label_name=label_name)
            return json.dumps(result, indent=2)
        except Exception as e:
            return f"Error adding label: {str(e)}"


class GetPromotionalEmails(SkillTool):
    """Get promotional emails."""
    
    name = "get_promotional_emails"
    description = "Get promotional emails from the Promotions category. Use this to find marketing and promotional emails for cleanup."
    parameters = {
        "type": "object",
        "properties": {
            "max_results": {
                "type": "integer",
                "description": "Maximum number of emails to return (default: 50)"
            }
        },
        "required": []
    }
    
    async def execute(self, max_results: int = 50) -> str:
        error = _check_gmail_available()
        if error:
            return error
        
        try:
            emails = get_promotional_emails(max_results=max_results)
            return json.dumps({
                "count": len(emails),
                "emails": emails
            }, indent=2)
        except Exception as e:
            return f"Error fetching promotional emails: {str(e)}"


class GetOldReadEmails(SkillTool):
    """Get old read emails from inbox."""
    
    name = "get_old_read_emails"
    description = "Get old read emails from inbox that are older than specified days. Use this to find emails to archive or clean up."
    parameters = {
        "type": "object",
        "properties": {
            "days": {
                "type": "integer",
                "description": "Get emails older than this many days (default: 30)"
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of emails to return (default: 100)"
            }
        },
        "required": []
    }
    
    async def execute(self, days: int = 30, max_results: int = 100) -> str:
        error = _check_gmail_available()
        if error:
            return error
        
        try:
            emails = get_old_read_emails(days=days, max_results=max_results)
            return json.dumps({
                "days": days,
                "count": len(emails),
                "emails": emails
            }, indent=2)
        except Exception as e:
            return f"Error fetching old read emails: {str(e)}"
