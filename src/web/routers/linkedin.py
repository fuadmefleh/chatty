from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from skills.linkedin_messages import linkedin_client as client
from skills.linkedin_messages.linkedin_client import LinkedInSessionError
from src.web.auth import require_api_key

router = APIRouter(prefix="/api/chatty/linkedin", tags=["linkedin"])


class ConnectBody(BaseModel):
    li_at: str
    jsessionid: str


# ── Integrations (LinkedIn) ──────────────────────────────────────────────────
# No official OAuth here (LinkedIn doesn't grant messaging/feed/connections
# scopes to third-party apps): the session is a browser-captured `li_at` +
# JSESSIONID cookie pair pasted on the Settings page, stored in
# data/linkedin_session.json and replayed against LinkedIn's own internal
# Voyager API. See skills/linkedin_messages/linkedin_client.py for the risk
# callout on this being unofficial/against LinkedIn's terms.
@router.get("/status", dependencies=[Depends(require_api_key)])
async def linkedin_status():
    return client.get_status()


@router.post("/connect", dependencies=[Depends(require_api_key)])
async def linkedin_connect(body: ConnectBody):
    try:
        summary = client.connect(body.li_at, body.jsessionid)
    except LinkedInSessionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "connected", "name": summary["name"]}


@router.post("/disconnect", dependencies=[Depends(require_api_key)])
async def linkedin_disconnect():
    client.clear_session()
    return {"status": "disconnected"}


@router.get("/conversations", dependencies=[Depends(require_api_key)])
async def linkedin_conversations():
    try:
        rows = client.get_conversations()
    except LinkedInSessionError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return {"conversations": [client.format_conversation(r) for r in rows]}


@router.get("/conversations/{conversation_id}/messages", dependencies=[Depends(require_api_key)])
async def linkedin_conversation_messages(conversation_id: str):
    try:
        rows = client.get_conversation_messages(conversation_id)
    except LinkedInSessionError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return {"messages": [client.format_message(r) for r in rows]}


@router.get("/feed", dependencies=[Depends(require_api_key)])
async def linkedin_feed(limit: int = 20):
    try:
        rows = client.get_feed_posts(limit=limit)
    except LinkedInSessionError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return {"posts": [client.format_post(r) for r in rows]}


@router.get("/connections", dependencies=[Depends(require_api_key)])
async def linkedin_connections():
    try:
        rows = client.get_connections()
    except LinkedInSessionError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return {"connections": [client.format_connection(r) for r in rows]}
