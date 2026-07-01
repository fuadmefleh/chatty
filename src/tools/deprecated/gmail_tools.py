"""Gmail tools for LLM function calling."""
import json
import logging
from typing import Dict, Any
from src.core.base_tool import BaseTool

# Import Gmail integration functions
try:
    from skills.gmail.gmail_integration import (
        search_emails,
        get_unread_emails,
        get_emails_from_sender,
        get_emails_by_subject,
        get_recent_emails,
        read_email,
        get_email_count
    )
    GMAIL_TOOLS_AVAILABLE = True
except ImportError as e:
    GMAIL_TOOLS_AVAILABLE = False
    logging.warning(f"Gmail tools not available: {e}")


class GetUnreadEmailsTool(BaseTool):
    """Get unread emails from Gmail inbox."""
    
    @property
    def name(self) -> str:
        return "get_unread_emails"
    
    @property
    def description(self) -> str:
        return "Get unread emails from Gmail inbox. Use this when user asks about unread emails, new messages, or checking their inbox."
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of emails to return (default: 10)",
                    "default": 10
                }
            },
            "required": []
        }
    
    async def execute(self, max_results: int = 10) -> str:
        if not GMAIL_TOOLS_AVAILABLE:
            return "Gmail tools are not available. Please install required packages: pip install google-auth-oauthlib google-auth-httplib2 google-api-python-client"
        
        try:
            emails = get_unread_emails(max_results=max_results)
            return json.dumps({
                "count": len(emails),
                "emails": emails
            }, indent=2)
        except Exception as e:
            return f"Error fetching unread emails: {str(e)}"


class SearchEmailsTool(BaseTool):
    """Search Gmail emails with custom query."""
    
    @property
    def name(self) -> str:
        return "search_emails"
    
    @property
    def description(self) -> str:
        return "Search Gmail emails using Gmail search syntax. Supports searching by sender (from:), subject (subject:), date (after:, before:), and text content. Use this for specific email searches."
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Gmail search query (e.g., 'from:john@example.com', 'subject:meeting', 'invoice')"
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of emails to return (default: 10)",
                    "default": 10
                },
                "include_body": {
                    "type": "boolean",
                    "description": "Whether to include full email body in results (default: false)",
                    "default": False
                }
            },
            "required": ["query"]
        }
    
    async def execute(self, query: str, max_results: int = 10, include_body: bool = False) -> str:
        if not GMAIL_TOOLS_AVAILABLE:
            return "Gmail tools are not available. Please install required packages: pip install google-auth-oauthlib google-auth-httplib2 google-api-python-client"
        
        try:
            emails = search_emails(query=query, max_results=max_results, include_body=include_body)
            return json.dumps({
                "query": query,
                "count": len(emails),
                "emails": emails
            }, indent=2)
        except Exception as e:
            return f"Error searching emails: {str(e)}"


class GetEmailsFromSenderTool(BaseTool):
    """Get emails from a specific sender."""
    
    @property
    def name(self) -> str:
        return "get_emails_from_sender"
    
    @property
    def description(self) -> str:
        return "Get emails from a specific sender. Use this when user asks for emails from a particular person or email address."
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "sender": {
                    "type": "string",
                    "description": "Email address or name of the sender"
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of emails to return (default: 10)",
                    "default": 10
                }
            },
            "required": ["sender"]
        }
    
    async def execute(self, sender: str, max_results: int = 10) -> str:
        if not GMAIL_TOOLS_AVAILABLE:
            return "Gmail tools are not available. Please install required packages: pip install google-auth-oauthlib google-auth-httplib2 google-api-python-client"
        
        try:
            emails = get_emails_from_sender(sender=sender, max_results=max_results)
            return json.dumps({
                "sender": sender,
                "count": len(emails),
                "emails": emails
            }, indent=2)
        except Exception as e:
            return f"Error fetching emails from sender: {str(e)}"


class GetRecentEmailsTool(BaseTool):
    """Get recent emails from the last N days."""
    
    @property
    def name(self) -> str:
        return "get_recent_emails"
    
    @property
    def description(self) -> str:
        return "Get recent emails from the last N days. Use this when user asks for recent emails, emails from this week, or emails from the past few days."
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "days": {
                    "type": "integer",
                    "description": "Number of days to look back (default: 7)",
                    "default": 7
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of emails to return (default: 10)",
                    "default": 10
                }
            },
            "required": []
        }
    
    async def execute(self, days: int = 7, max_results: int = 10) -> str:
        if not GMAIL_TOOLS_AVAILABLE:
            return "Gmail tools are not available. Please install required packages: pip install google-auth-oauthlib google-auth-httplib2 google-api-python-client"
        
        try:
            emails = get_recent_emails(days=days, max_results=max_results)
            return json.dumps({
                "days": days,
                "count": len(emails),
                "emails": emails
            }, indent=2)
        except Exception as e:
            return f"Error fetching recent emails: {str(e)}"


class ReadEmailTool(BaseTool):
    """Read full email content by message ID."""
    
    @property
    def name(self) -> str:
        return "read_email"
    
    @property
    def description(self) -> str:
        return "Read full email content including body by message ID. Use this to get the complete content of a specific email."
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
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
        if not GMAIL_TOOLS_AVAILABLE:
            return "Gmail tools are not available. Please install required packages: pip install google-auth-oauthlib google-auth-httplib2 google-api-python-client"
        
        try:
            email = read_email(message_id=message_id)
            return json.dumps(email, indent=2)
        except Exception as e:
            return f"Error reading email: {str(e)}"


class GetEmailCountTool(BaseTool):
    """Get count of emails matching a query."""
    
    @property
    def name(self) -> str:
        return "get_email_count"
    
    @property
    def description(self) -> str:
        return "Get count of emails matching a query. Use this to count unread emails, emails from a sender, or emails matching search criteria."
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Gmail search query (e.g., 'is:unread', 'from:john@example.com'). Leave empty to count all emails.",
                    "default": ""
                }
            },
            "required": []
        }
    
    async def execute(self, query: str = "") -> str:
        if not GMAIL_TOOLS_AVAILABLE:
            return "Gmail tools are not available. Please install required packages: pip install google-auth-oauthlib google-auth-httplib2 google-api-python-client"
        
        try:
            count = get_email_count(query=query)
            return json.dumps({
                "query": query or "all emails",
                "count": count
            }, indent=2)
        except Exception as e:
            return f"Error counting emails: {str(e)}"
