"""LinkedIn tools for LLM function calling. Read-only - no send/post tool."""
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
_impl_path = Path(__file__).parent / "linkedin_parser.py"
_spec = importlib.util.spec_from_file_location("linkedin_parser", _impl_path)
_parser = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_parser)


class ListLinkedInConversationsTool(SkillTool):
    """List recent LinkedIn conversations."""

    name = "list_linkedin_conversations"
    description = "List the user's recent LinkedIn message conversations. Use this when the user wants to see who's been messaging them on LinkedIn."
    parameters = {"type": "object", "properties": {}}

    async def execute(self) -> str:
        try:
            conversations = await _parser.get_conversations()
            return json.dumps({"success": True, "conversations": conversations, "count": len(conversations)}, indent=2)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})


class GetLinkedInConversationTool(SkillTool):
    """Get messages in a specific LinkedIn conversation."""

    name = "get_linkedin_conversation"
    description = "Read the messages in a specific LinkedIn conversation. Use this after listing conversations to see what was actually said."
    parameters = {
        "type": "object",
        "properties": {
            "conversation_id": {
                "type": "string",
                "description": "The conversation_id from list_linkedin_conversations"
            }
        },
        "required": ["conversation_id"],
    }

    async def execute(self, conversation_id: str) -> str:
        try:
            messages = await _parser.get_conversation_messages(conversation_id)
            return json.dumps({"success": True, "messages": messages, "count": len(messages)}, indent=2)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})


class GetLinkedInFeedTool(SkillTool):
    """Get recent posts from the user's LinkedIn feed."""

    name = "get_linkedin_feed"
    description = "Get recent posts from the user's LinkedIn home feed. Use this when the user wants a summary of what's happening on their LinkedIn feed."
    parameters = {
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "description": "Number of feed posts to retrieve (default: 20)",
                "default": 20,
                "minimum": 1,
                "maximum": 50,
            }
        },
    }

    async def execute(self, limit: int = 20) -> str:
        try:
            posts = await _parser.get_feed(limit=limit)
            return json.dumps({"success": True, "posts": posts, "count": len(posts)}, indent=2)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})


class ListLinkedInConnectionsTool(SkillTool):
    """List the user's LinkedIn connections."""

    name = "list_linkedin_connections"
    description = "List the user's LinkedIn connections (their network). Use this when the user asks about their LinkedIn connections or network."
    parameters = {"type": "object", "properties": {}}

    async def execute(self) -> str:
        try:
            connections = await _parser.get_connections()
            return json.dumps({"success": True, "connections": connections, "count": len(connections)}, indent=2)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})
