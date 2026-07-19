from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
import httpx

from skills.whatsapp_messages import whatsapp_bridge_client as bridge
from skills.whatsapp_messages import whatsapp_managed_chats
from src.web.auth import require_api_key

router = APIRouter(prefix="/api/chatty/whatsapp", tags=["whatsapp"])

# Group auto-reply (JIDs ending in @g.us) was originally blocked here - a bad
# reply in a group is visible to everyone in it, not just one person - but
# was re-enabled at the user's explicit request. heartbeat_manager.py's
# _process_whatsapp_managed_chats still treats group chats more
# conservatively in its prompt as a partial mitigation.


class ManagedChatCreate(BaseModel):
    name: Optional[str] = None
    instructions: Optional[str] = None


class SendMessageBody(BaseModel):
    message: str


# ── Integrations (WhatsApp) ──────────────────────────────────────────────────
# Unlike Gmail there's no OAuth redirect: the live session lives in the
# whatsapp-bridge Node sidecar (Baileys), linked by scanning a QR code from
# the phone's WhatsApp app, so this just proxies the bridge's own status/qr
# endpoints for the dashboard to poll.
@router.get("/status", dependencies=[Depends(require_api_key)])
async def whatsapp_status():
    try:
        status = bridge.get_status()
    except httpx.ConnectError:
        return {"status": "unavailable", "phone": None, "qr": None}

    qr = None
    if status.get("status") == "qr_pending":
        qr = bridge.get_qr()
    return {"status": status.get("status"), "phone": status.get("phone"), "qr": qr}


@router.post("/disconnect", dependencies=[Depends(require_api_key)])
async def whatsapp_disconnect():
    try:
        bridge.logout()
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="whatsapp-bridge isn't running")
    return {"status": "disconnected"}


# ── Chats / messages (dashboard chat browser) ────────────────────────────────
@router.get("/chats", dependencies=[Depends(require_api_key)])
async def whatsapp_chats():
    try:
        chats = bridge.get_chats()
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="whatsapp-bridge isn't running")
    managed_jids = {c["jid"] for c in whatsapp_managed_chats.list_managed()}
    for chat in chats:
        chat["managed"] = chat.get("jid") in managed_jids
    return {"chats": chats}


@router.get("/chats/{jid}/messages", dependencies=[Depends(require_api_key)])
async def whatsapp_chat_messages(jid: str, limit: int = 50, before: Optional[str] = None):
    try:
        messages = bridge.get_thread(jid, limit=limit, before=before)
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="whatsapp-bridge isn't running")
    return {"messages": messages}


@router.post("/chats/{jid}/send", dependencies=[Depends(require_api_key)])
async def whatsapp_chat_send(jid: str, body: SendMessageBody):
    try:
        result = bridge.send_message(jid, body.message, origin="user")
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="whatsapp-bridge isn't running")
    except httpx.HTTPStatusError as e:
        detail = e.response.json().get("error", str(e)) if e.response.content else str(e)
        raise HTTPException(status_code=e.response.status_code, detail=detail)
    return result


@router.post("/chats/{jid}/read", dependencies=[Depends(require_api_key)])
async def whatsapp_chat_read(jid: str):
    try:
        bridge.mark_read(jid)
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="whatsapp-bridge isn't running")
    return {"success": True}


# ── Managed chats (autonomous auto-reply opt-in) ─────────────────────────────
# See src/managers/heartbeat_manager.py's _process_whatsapp_managed_chats for
# what actually happens with this list - this router only maintains the
# opt-in set, it never sends anything itself.
@router.get("/managed", dependencies=[Depends(require_api_key)])
async def whatsapp_managed_list():
    return {"managed": whatsapp_managed_chats.list_managed()}


@router.post("/chats/{jid}/managed", dependencies=[Depends(require_api_key)])
async def whatsapp_chat_manage(jid: str, body: ManagedChatCreate):
    entry = whatsapp_managed_chats.add_managed(jid, body.name, body.instructions)
    return entry


@router.delete("/chats/{jid}/managed", dependencies=[Depends(require_api_key)])
async def whatsapp_chat_unmanage(jid: str):
    whatsapp_managed_chats.remove_managed(jid)
    return {"status": "removed"}
