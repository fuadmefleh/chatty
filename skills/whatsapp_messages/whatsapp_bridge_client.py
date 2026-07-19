"""Thin HTTP client for the whatsapp-bridge Node sidecar (whatsapp-bridge/).

Baileys (the library that actually speaks WhatsApp's multi-device protocol)
only has a JS implementation, so the live session runs in a separate Node
process; this module is the only thing on the Python side that talks to it.
Mirrors the role skills/gmail/gmail_integration.py plays for Gmail.
"""
import os
from typing import Any, Dict, List, Optional

import httpx

BRIDGE_URL = os.getenv("WHATSAPP_BRIDGE_URL", "http://127.0.0.1:8017")
BRIDGE_SECRET = os.getenv("WHATSAPP_BRIDGE_SECRET", "")

_TIMEOUT = 10.0


def _headers() -> Dict[str, str]:
    return {"X-Bridge-Secret": BRIDGE_SECRET}


def _get(path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    resp = httpx.get(f"{BRIDGE_URL}{path}", params=params, headers=_headers(), timeout=_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _post(path: str, json: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    resp = httpx.post(f"{BRIDGE_URL}{path}", json=json, headers=_headers(), timeout=_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def get_status() -> Dict[str, Any]:
    """Returns {"status": "disconnected"|"qr_pending"|"connected", "phone": str|None}."""
    return _get("/status")


def get_qr() -> Optional[str]:
    """Returns a data-URL PNG of the current login QR code, or None if not
    awaiting a scan (already connected, or bridge not yet initialized)."""
    return _get("/qr").get("qr")


def logout() -> None:
    _post("/logout")


def get_recent_messages(limit: int = 20, days: int = 7) -> List[Dict[str, Any]]:
    return _get("/messages/recent", {"limit": limit, "days": days}).get("messages", [])


def search_messages(query: str, contact: Optional[str] = None, days: int = 30, limit: int = 50) -> List[Dict[str, Any]]:
    params: Dict[str, Any] = {"query": query, "days": days, "limit": limit}
    if contact:
        params["contact"] = contact
    return _get("/messages/search", params).get("messages", [])


def get_contact_messages(contact: str, limit: int = 30, days: int = 30) -> List[Dict[str, Any]]:
    return _get(f"/messages/contact/{contact}", {"limit": limit, "days": days}).get("messages", [])


def get_active_contacts(days: int = 30) -> List[Dict[str, Any]]:
    return _get("/contacts", {"days": days}).get("contacts", [])


def get_chats(limit: int = 200) -> List[Dict[str, Any]]:
    return _get("/chats", {"limit": limit}).get("chats", [])


def get_thread(jid: str, limit: int = 50, before: Optional[str] = None) -> List[Dict[str, Any]]:
    params: Dict[str, Any] = {"limit": limit}
    if before:
        params["before"] = before
    return _get(f"/messages/thread/{jid}", params).get("messages", [])


def mark_read(jid: str) -> None:
    _post(f"/chats/{jid}/read")


def send_message(to: str, message: str, origin: str = "user") -> Dict[str, Any]:
    return _post("/send", {"to": to, "message": message, "origin": origin})
