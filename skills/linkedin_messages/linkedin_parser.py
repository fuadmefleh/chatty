"""LinkedIn read access for LLM tool calls, backed by linkedin_client.py.

Mirrors whatsapp_parser.py's shape: thin async wrappers that turn a
"not connected" / session-error condition into a friendly info message
for the model instead of raising, so a tool call degrades gracefully
rather than surfacing a stack trace mid-conversation.
"""
from datetime import datetime
from typing import Any, Dict, List

from skills.linkedin_messages import linkedin_client as client
from skills.linkedin_messages.linkedin_client import LinkedInSessionError

_NOT_CONNECTED = (
    "LinkedIn isn't connected. Paste a session cookie on the dashboard's "
    "Settings page to link it."
)


def _info(message: str) -> List[Dict[str, Any]]:
    return [{"type": "info", "message": message, "timestamp": datetime.now().isoformat()}]


async def get_conversations() -> List[Dict[str, Any]]:
    """List recent LinkedIn conversations."""
    try:
        rows = client.get_conversations()
    except LinkedInSessionError:
        return _info(_NOT_CONNECTED)
    if not rows:
        return _info("No LinkedIn conversations found.")
    return [client.format_conversation(r) for r in rows]


async def get_conversation_messages(conversation_id: str) -> List[Dict[str, Any]]:
    """Get messages in a specific LinkedIn conversation."""
    try:
        rows = client.get_conversation_messages(conversation_id)
    except LinkedInSessionError:
        return _info(_NOT_CONNECTED)
    if not rows:
        return _info(f"No messages found for conversation '{conversation_id}'.")
    return [client.format_message(r) for r in rows]


async def get_feed(limit: int = 20) -> List[Dict[str, Any]]:
    """Get recent posts from the user's LinkedIn feed."""
    try:
        rows = client.get_feed_posts(limit=limit)
    except LinkedInSessionError:
        return _info(_NOT_CONNECTED)
    if not rows:
        return _info("No feed posts found.")
    return [client.format_post(r) for r in rows]


async def get_connections() -> List[Dict[str, Any]]:
    """List the user's LinkedIn connections."""
    try:
        rows = client.get_connections()
    except LinkedInSessionError:
        return _info(_NOT_CONNECTED)
    if not rows:
        return _info("No connections found.")
    return [client.format_connection(r) for r in rows]
