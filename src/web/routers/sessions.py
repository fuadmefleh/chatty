from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.web import config
from src.web.auth import require_api_key

router = APIRouter(prefix="/api/chatty/sessions", tags=["sessions"], dependencies=[Depends(require_api_key)])


class SessionRename(BaseModel):
    title: str


@router.get("")
async def get_sessions():
    """List conversation sessions (newest first)."""
    from src.core.memory import ConversationHistoryManager
    mgr = ConversationHistoryManager(config.WEB_USER_ID)
    sessions = await mgr.get_sessions()
    # Return lightweight session info (no full message bodies)
    result = []
    for s in sessions:
        result.append({
            "id": s["id"],
            "first_ts": s["first_ts"],
            "last_ts": s["last_ts"],
            "message_count": s["message_count"],
            "summary": s["summary"],
            "title": s["title"],
        })
    return result


@router.get("/{session_id}")
async def get_session_messages(session_id: int):
    """Return messages for a specific session."""
    from src.core.memory import ConversationHistoryManager
    mgr = ConversationHistoryManager(config.WEB_USER_ID)
    messages = await mgr.get_session(session_id)
    return messages


@router.put("/{session_id}")
async def rename_session(session_id: int, body: SessionRename):
    """Set a custom title for a session (stored separately from its auto-computed summary)."""
    from src.core.memory import ConversationHistoryManager
    mgr = ConversationHistoryManager(config.WEB_USER_ID)
    sessions = await mgr.get_sessions()
    if not (0 <= session_id < len(sessions)):
        raise HTTPException(status_code=404, detail="Session not found")
    await mgr.set_session_title(sessions[session_id]["first_ts"], body.title)
    return {"id": session_id, "title": body.title}


@router.delete("/{session_id}")
async def delete_session(session_id: int):
    """Delete a session."""
    from src.core.memory import ConversationHistoryManager
    mgr = ConversationHistoryManager(config.WEB_USER_ID)
    ok = await mgr.delete_session(session_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"deleted": True}
