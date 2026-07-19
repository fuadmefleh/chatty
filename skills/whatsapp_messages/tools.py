"""WhatsApp messages tools for LLM function calling."""
import json
import sys
import importlib.util
from pathlib import Path

# Add project root to path
project_root = str(Path(__file__).parent.parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.core.skill_tool import SkillTool

# Load implementation module from this folder
_impl_path = Path(__file__).parent / "whatsapp_parser.py"
_spec = importlib.util.spec_from_file_location("whatsapp_parser", _impl_path)
_parser = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_parser)


class ReadRecentWhatsAppMessagesTool(SkillTool):
    """Read recent WhatsApp messages."""

    name = "read_recent_whatsapp_messages"
    description = "Read recent WhatsApp messages from the user's chat history. Use this when the user wants to see their latest WhatsApp conversations."
    parameters = {
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "description": "Number of recent messages to retrieve (default: 20, max: 100)",
                "default": 20,
                "minimum": 1,
                "maximum": 100
            },
            "days": {
                "type": "integer", 
                "description": "Number of days back to search (default: 7)",
                "default": 7,
                "minimum": 1,
                "maximum": 90
            }
        }
    }

    async def execute(self, limit: int = 20, days: int = 7) -> str:
        try:
            messages = await _parser.get_recent_messages(limit=limit, days=days)
            result = {
                "success": True,
                "messages": messages,
                "count": len(messages),
                "timeframe": f"Last {days} days"
            }
            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})


class SearchWhatsAppMessagesTool(SkillTool):
    """Search WhatsApp messages for specific content."""

    name = "search_whatsapp_messages"
    description = "Search through WhatsApp messages for specific keywords, phrases, or content. Use this when the user wants to find specific messages or conversations."
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query - keywords or phrases to find in messages"
            },
            "contact": {
                "type": "string",
                "description": "Optional: search messages from a specific contact name"
            },
            "days": {
                "type": "integer",
                "description": "Number of days back to search (default: 30)",
                "default": 30,
                "minimum": 1,
                "maximum": 365
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of results to return (default: 50)",
                "default": 50,
                "minimum": 1,
                "maximum": 200
            }
        },
        "required": ["query"]
    }

    async def execute(self, query: str, contact: str = None, days: int = 30, limit: int = 50) -> str:
        try:
            messages = await _parser.search_messages(
                query=query,
                contact=contact,
                days=days,
                limit=limit
            )
            result = {
                "success": True,
                "query": query,
                "contact": contact,
                "messages": messages,
                "count": len(messages),
                "timeframe": f"Last {days} days"
            }
            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})


class GetWhatsAppContactMessagesTool(SkillTool):
    """Get messages from a specific WhatsApp contact."""

    name = "get_whatsapp_contact_messages"
    description = "Retrieve messages from a specific WhatsApp contact or group chat. Use this when the user wants to see messages from a particular person or group."
    parameters = {
        "type": "object",
        "properties": {
            "contact": {
                "type": "string",
                "description": "Name of the contact or group chat"
            },
            "limit": {
                "type": "integer",
                "description": "Number of messages to retrieve (default: 30)",
                "default": 30,
                "minimum": 1,
                "maximum": 100
            },
            "days": {
                "type": "integer",
                "description": "Number of days back to search (default: 30)",
                "default": 30,
                "minimum": 1,
                "maximum": 365
            }
        },
        "required": ["contact"]
    }

    async def execute(self, contact: str, limit: int = 30, days: int = 30) -> str:
        try:
            messages = await _parser.get_contact_messages(
                contact=contact,
                limit=limit,
                days=days
            )
            result = {
                "success": True,
                "contact": contact,
                "messages": messages,
                "count": len(messages),
                "timeframe": f"Last {days} days"
            }
            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})


class ListWhatsAppContactsTool(SkillTool):
    """List WhatsApp contacts and groups."""

    name = "list_whatsapp_contacts"
    description = "List all WhatsApp contacts and group chats that have messages. Use this to see who the user has been chatting with."
    parameters = {
        "type": "object",
        "properties": {
            "days": {
                "type": "integer",
                "description": "Number of days back to look for active contacts (default: 30)",
                "default": 30,
                "minimum": 1,
                "maximum": 365
            }
        }
    }

    async def execute(self, days: int = 30) -> str:
        try:
            contacts = await _parser.get_active_contacts(days=days)
            result = {
                "success": True,
                "contacts": contacts,
                "count": len(contacts),
                "timeframe": f"Active in last {days} days"
            }
            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})


class SendWhatsAppMessageTool(SkillTool):
    """Send a WhatsApp message to a contact."""

    name = "send_whatsapp_message"
    description = "Send a WhatsApp message to a phone number or contact. Only use this when the user explicitly asks to send a WhatsApp message - never send messages on your own initiative."
    parameters = {
        "type": "object",
        "properties": {
            "to": {
                "type": "string",
                "description": "Recipient's phone number, including country code (e.g. '+15551234567')"
            },
            "message": {
                "type": "string",
                "description": "The message text to send"
            }
        },
        "required": ["to", "message"]
    }

    async def execute(self, to: str, message: str) -> str:
        try:
            result = await _parser.send_message(to=to, message=message)
            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})