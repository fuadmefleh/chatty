"""WhatsApp message access, backed by the whatsapp-bridge Node sidecar.

Previously this scanned the local filesystem for WhatsApp Desktop DB files
or exported chat .txt files, but the actual database-parsing paths were
never implemented (they returned an empty list unconditionally) - the only
code path that ever produced real messages was the exported-.txt fallback,
which required the user to manually export and drop files on disk. This
now reads from a live, connected WhatsApp Web session instead; see
whatsapp_bridge_client.py and whatsapp-bridge/.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

from skills.whatsapp_messages import whatsapp_bridge_client as bridge


def _not_connected_message(detail: str) -> List[Dict[str, Any]]:
    return [{
        "timestamp": datetime.now().isoformat(),
        "contact": "System",
        "message": detail,
        "type": "info",
    }]


def _to_entry(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "timestamp": row.get("timestamp"),
        "contact": row.get("contact_name") or row.get("jid"),
        "message": row.get("message"),
        "type": "chat",
        "direction": row.get("direction"),
    }


def _call(fn, *args, **kwargs) -> Optional[List[Dict[str, Any]]]:
    try:
        return fn(*args, **kwargs)
    except httpx.ConnectError:
        return None
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            return None
        raise


async def get_recent_messages(limit: int = 20, days: int = 7) -> List[Dict[str, Any]]:
    """Get recent WhatsApp messages."""
    rows = _call(bridge.get_recent_messages, limit=limit, days=days)
    if rows is None:
        return _not_connected_message(
            "WhatsApp isn't connected. Scan the QR code on the dashboard's Settings page to link it."
        )
    return [_to_entry(r) for r in rows]


async def search_messages(query: str, contact: str = None, days: int = 30, limit: int = 50) -> List[Dict[str, Any]]:
    """Search WhatsApp messages for specific content."""
    rows = _call(bridge.search_messages, query=query, contact=contact, days=days, limit=limit)
    if rows is None:
        return _not_connected_message(
            "WhatsApp isn't connected. Scan the QR code on the dashboard's Settings page to link it."
        )
    if not rows:
        return _not_connected_message(f"No messages found for query: '{query}'.")
    return [_to_entry(r) for r in rows]


async def get_contact_messages(contact: str, limit: int = 30, days: int = 30) -> List[Dict[str, Any]]:
    """Get messages from a specific contact."""
    rows = _call(bridge.get_contact_messages, contact=contact, limit=limit, days=days)
    if rows is None:
        return _not_connected_message(
            "WhatsApp isn't connected. Scan the QR code on the dashboard's Settings page to link it."
        )
    if not rows:
        return _not_connected_message(f"No messages found from contact: '{contact}'.")
    return [_to_entry(r) for r in rows]


async def get_active_contacts(days: int = 30) -> List[Dict[str, Any]]:
    """Get list of active WhatsApp contacts."""
    rows = _call(bridge.get_active_contacts, days=days)
    if rows is None:
        return [{
            "contact": "System",
            "message_count": 0,
            "last_message_date": datetime.now().isoformat(),
            "type": "info",
            "message": "WhatsApp isn't connected. Scan the QR code on the dashboard's Settings page to link it.",
        }]
    return [{
        "contact": r.get("contact_name") or r.get("jid"),
        "message_count": r.get("message_count", 0),
        "last_message_date": r.get("last_message_date"),
        "type": "contact",
    } for r in rows]


async def send_message(to: str, message: str) -> Dict[str, Any]:
    """Send a WhatsApp message to a contact (phone number or JID)."""
    try:
        return bridge.send_message(to, message)
    except httpx.ConnectError:
        return {"success": False, "error": "WhatsApp bridge isn't running."}
    except httpx.HTTPStatusError as e:
        detail = e.response.json().get("error", str(e)) if e.response.content else str(e)
        return {"success": False, "error": detail}
