"""Chatty Web Server - FastAPI backend for the Chatty web dashboard.

Port: 8016
Provides REST + WebSocket endpoints for:
- Chat (WebSocket, streams agent responses)
- Notes (CRUD)
- Transcriptions (create/list/delete - staged for automatic memory mining)
- Audio ingestion (raw-body upload -> WhisperX STT -> transcriptions queue)
- Reminders (read + delete)
- Memory viewer (read-only)
- Code browser (read-only)
- System status (skills, pm2)
"""
import asyncio
import fnmatch
import json
import os
import subprocess
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Optional

import httpx
from fastapi import (
    FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, Header,
    Query, Request, BackgroundTasks,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from dotenv import load_dotenv

# Load env
load_dotenv()

# ── Ensure project root is on sys.path so src/ imports work ─────────────────
PROJECT_ROOT = Path(__file__).parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.logging_config import get_api_logger
from src.core.skills_manager import SkillsManager
from skills.notes.notes_manager import NotesManager
from skills.transcriptions.transcriptions_manager import TranscriptionsManager
from skills.watchlist.watchlist_manager import WatchlistManager
from src.managers.insights_manager import InsightsManager
from skills.pi_agent.requests_manager import FeatureRequestsManager
from skills.pi_agent.runner import run_pi_agent
from skills.pi_agent import lock as pi_lock

logger = get_api_logger()

# ── Config ───────────────────────────────────────────────────────────────────
API_KEY = os.getenv("CHATTY_WEB_API_KEY", "changeme")
WEB_USER_ID = os.getenv("WEB_USER_ID", "")
REMINDERS_DIR = PROJECT_ROOT / "reminders"
MEMORY_DIR = PROJECT_ROOT / "memory"
PORT = int(os.getenv("CHATTY_WEB_PORT", "8016"))

# Expects a WhisperX-based STT engine reachable at this URL (run separately,
# not part of this repo) rather than embedding a second Whisper install.
# Handles diarization itself (gracefully skipped server-side if it has no
# HUGGINGFACE_TOKEN configured).
STT_ENGINE_URL = os.getenv("STT_ENGINE_URL", "http://127.0.0.1:8003")

# ── Code browser config ──────────────────────────────────────────────────────
CODE_EXCLUDE_DIRS = {
    ".git", "venv", "env", "ENV", "node_modules", "__pycache__",
    "data", "memory", "logs", "reminders", "dist", "build",
    ".vite", ".opencode", ".claude", ".vscode", ".idea",
    ".pytest_cache", "coverage",
}
CODE_EXCLUDE_FILE_GLOBS = (
    ".env", ".env.*", "credentials.json", "*_token*", "*_tokens*",
    "*.pickle", "*.db", "*.sqlite", "*.sqlite3", "*.pem", "*.key", "*secret*",
)
CODE_BINARY_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".webp", ".bmp", ".pdf",
    ".zip", ".tar", ".gz", ".whl", ".pyc", ".so", ".woff", ".woff2", ".ttf", ".eot",
}
CODE_LANGUAGE_MAP = {
    ".py": "python", ".ts": "typescript", ".tsx": "tsx", ".js": "javascript",
    ".jsx": "jsx", ".json": "json", ".css": "css", ".html": "markup",
    ".md": "markdown", ".sh": "bash", ".yml": "yaml", ".yaml": "yaml",
    ".toml": "toml", ".cfg": "text", ".ini": "text", ".txt": "text",
}
CODE_MAX_FILE_BYTES = 500_000  # reject rather than truncate

# ── App setup ────────────────────────────────────────────────────────────────
app = FastAPI(title="Chatty Web API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Shared state ─────────────────────────────────────────────────────────────
notes_manager = NotesManager()
transcriptions_manager = TranscriptionsManager()
watchlist_manager = WatchlistManager()
insights_manager = InsightsManager()
feature_requests_manager = FeatureRequestsManager()
skills_manager: Optional[SkillsManager] = None
_pi_worker_task: Optional[asyncio.Task] = None


@app.on_event("startup")
async def startup_event():
    global skills_manager
    skills_manager = SkillsManager()
    await skills_manager.load_skills()
    print(f"[chatty-web] Loaded {len(skills_manager.skills)} skills")
    print(f"[chatty-web] Listening on port {PORT}")


# ── Auth dependency ──────────────────────────────────────────────────────────
async def require_api_key(x_api_key: str = Header(default="")):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")


# ── Health / root ─────────────────────────────────────────────────────────────
@app.get("/")
async def root():
    return {"service": "chatty-web-api", "status": "ok", "version": "1.0.0"}


@app.get("/api/chatty/health")
async def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


# ── Notes ────────────────────────────────────────────────────────────────────
class NoteCreate(BaseModel):
    content: str

class NoteUpdate(BaseModel):
    content: str


@app.get("/api/chatty/notes", dependencies=[Depends(require_api_key)])
async def get_notes():
    notes = notes_manager.get_notes(WEB_USER_ID)
    return [n.to_dict() for n in notes]


@app.post("/api/chatty/notes", dependencies=[Depends(require_api_key)], status_code=201)
async def create_note(body: NoteCreate):
    note = notes_manager.add_note(WEB_USER_ID, body.content)
    return note.to_dict()


@app.put("/api/chatty/notes/{note_id}", dependencies=[Depends(require_api_key)])
async def update_note(note_id: str, body: NoteUpdate):
    note = notes_manager.update_note(WEB_USER_ID, note_id, body.content)
    if note is None:
        raise HTTPException(status_code=404, detail="Note not found")
    return note.to_dict()


@app.delete("/api/chatty/notes/{note_id}", dependencies=[Depends(require_api_key)])
async def delete_note(note_id: str):
    ok = notes_manager.delete_note(WEB_USER_ID, note_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Note not found")
    return {"deleted": True}


# ── Transcriptions ───────────────────────────────────────────────────────────
# Raw transcriptions (e.g. iOS voice memos) awaiting automatic mining into
# long-term memory by the heartbeat - not user-editable notes. Listing only
# returns pending ones by default; already-mined ones are archived server-side.
class TranscriptionCreate(BaseModel):
    content: str
    source: str = "ios_app"


@app.get("/api/chatty/transcriptions", dependencies=[Depends(require_api_key)])
async def get_transcriptions(include_archived: bool = False):
    pending = [{**t.to_dict(), "mined": False} for t in transcriptions_manager.get_pending(WEB_USER_ID)]
    if not include_archived:
        return pending
    archived = [{**t.to_dict(), "mined": True} for t in transcriptions_manager.get_archived(WEB_USER_ID)]
    return pending + archived


@app.post("/api/chatty/transcriptions", dependencies=[Depends(require_api_key)], status_code=201)
async def create_transcription(body: TranscriptionCreate):
    transcription = transcriptions_manager.add_transcription(WEB_USER_ID, body.content, body.source)
    return transcription.to_dict()


@app.delete("/api/chatty/transcriptions/{transcription_id}", dependencies=[Depends(require_api_key)])
async def delete_transcription(transcription_id: str):
    ok = transcriptions_manager.delete_transcription(WEB_USER_ID, transcription_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Transcription not found")
    return {"deleted": True}


@app.get("/api/chatty/transcriptions/{transcription_id}/audio", dependencies=[Depends(require_api_key)])
async def get_transcription_audio(transcription_id: str):
    path = transcriptions_manager.get_audio_path(WEB_USER_ID, transcription_id)
    if not path or not path.exists():
        raise HTTPException(status_code=404, detail="Audio not found")
    return FileResponse(path, media_type="audio/mp4")


# ── Audio ingestion (iOS app) ────────────────────────────────────────────────
# Raw-body (not multipart) audio chunk upload. Transcribed via the WhisperX
# STT engine already running on this host, then fed into the same
# TranscriptionsManager pending queue as text transcriptions - the existing
# heartbeat mining step (HeartbeatManager._process_transcription_mining)
# picks it up from there unchanged.
def _format_transcript(stt_result: dict) -> str:
    """Render an STT engine result as plain text, using per-speaker lines
    when diarization segments are present."""
    segments = stt_result.get("segments") or []
    if segments and isinstance(segments[0], dict) and "speaker" in segments[0]:
        lines = []
        for seg in segments:
            text = (seg.get("text") or "").strip()
            if text:
                lines.append(f"{seg.get('speaker', '?')}: {text}")
        if lines:
            return "\n".join(lines)
    return (stt_result.get("text") or "").strip()


async def _transcribe_and_store_audio(
    audio_bytes: bytes, device_id: str, chunk_start: str, chunk_duration: str, source: str
) -> None:
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{STT_ENGINE_URL}/transcribe",
                files={"file": ("chunk.m4a", audio_bytes, "audio/mp4")},
                data={"language": "en", "diarize": "true"},
            )
            resp.raise_for_status()
            result = resp.json()

        transcript = _format_transcript(result)
        if not transcript:
            logger.info(f"Audio chunk from device {device_id} at {chunk_start} had no speech, skipping")
            return

        audio_filename = transcriptions_manager.save_audio(audio_bytes)
        content = f"[{chunk_start}] (device {device_id}, {chunk_duration}s audio) {transcript}"
        transcriptions_manager.add_transcription(WEB_USER_ID, content, source=source, audio_filename=audio_filename)
        logger.info(f"Transcribed and queued audio chunk from device {device_id} at {chunk_start}")

    except Exception as e:
        logger.error(f"Failed to transcribe audio chunk from device {device_id} at {chunk_start}: {e}")


@app.post("/api/chatty/audio", dependencies=[Depends(require_api_key)], status_code=202)
async def receive_audio(
    request: Request,
    background_tasks: BackgroundTasks,
    x_device_id: str = Header(default=""),
    x_chunk_start: str = Header(default=""),
    x_chunk_duration: str = Header(default=""),
    x_source: str = Header(default="ios_app"),
):
    audio_bytes = await request.body()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio body")

    background_tasks.add_task(
        _transcribe_and_store_audio, audio_bytes, x_device_id, x_chunk_start, x_chunk_duration, x_source
    )
    return {"accepted": True}


# ── Watchlist ────────────────────────────────────────────────────────────────
class WatchTopicCreate(BaseModel):
    topic: str
    kind: str = "news"


@app.get("/api/chatty/watchlist", dependencies=[Depends(require_api_key)])
async def get_watchlist():
    return [t.to_dict() for t in watchlist_manager.get_topics(WEB_USER_ID)]


@app.post("/api/chatty/watchlist", dependencies=[Depends(require_api_key)], status_code=201)
async def create_watch_topic(body: WatchTopicCreate):
    topic = body.topic.strip()
    if not topic:
        raise HTTPException(status_code=400, detail="Topic is required")
    if body.kind not in ("news", "stock", "github"):
        raise HTTPException(status_code=400, detail="kind must be one of: news, stock, github")
    watch_topic = watchlist_manager.add_topic(WEB_USER_ID, topic, kind=body.kind)
    return watch_topic.to_dict()


@app.delete("/api/chatty/watchlist/{topic_id}", dependencies=[Depends(require_api_key)])
async def delete_watch_topic(topic_id: str):
    ok = watchlist_manager.remove_topic(WEB_USER_ID, topic_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Topic not found")
    return {"deleted": True}


# ── Insights ─────────────────────────────────────────────────────────────────
@app.get("/api/chatty/insights", dependencies=[Depends(require_api_key)])
async def get_insights(limit: int = Query(default=50, ge=1, le=200)):
    return [i.to_dict() for i in insights_manager.get_insights(WEB_USER_ID, limit)]


@app.delete("/api/chatty/insights/{insight_id}", dependencies=[Depends(require_api_key)])
async def delete_insight(insight_id: str):
    ok = insights_manager.delete_insight(WEB_USER_ID, insight_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Insight not found")
    return {"deleted": True}


# ── Reminders ────────────────────────────────────────────────────────────────
def _load_reminders() -> List[dict]:
    reminders = []
    if not REMINDERS_DIR.exists():
        return reminders
    for f in sorted(REMINDERS_DIR.glob("*.json"), reverse=True):
        try:
            data = json.loads(f.read_text())
            data["_file"] = f.name
            reminders.append(data)
        except Exception:
            pass
    return reminders


@app.get("/api/chatty/reminders", dependencies=[Depends(require_api_key)])
async def get_reminders():
    return _load_reminders()


@app.delete("/api/chatty/reminders/{filename}", dependencies=[Depends(require_api_key)])
async def delete_reminder(filename: str):
    # Security: only allow .json files within REMINDERS_DIR
    if "/" in filename or "\\" in filename or not filename.endswith(".json"):
        raise HTTPException(status_code=400, detail="Invalid filename")
    target = REMINDERS_DIR / filename
    if not target.exists():
        raise HTTPException(status_code=404, detail="Reminder not found")
    target.unlink()
    return {"deleted": True}


# ── Feature Requests (routed to the local Pi + qwen3.6-27b coding agent) ──────
class FeatureRequestCreate(BaseModel):
    prompt: str


async def _process_pi_queue():
    """Drain queued feature requests one at a time through the Pi agent."""
    global _pi_worker_task
    try:
        while True:
            req = feature_requests_manager.next_queued()
            if req is None:
                break

            feature_requests_manager.update(req.id, status="running")

            # Coordinate with the heartbeat's self-upgrade pipeline (a separate
            # process) so two `pi` runs never touch the repo at once. Bounded
            # wait so a stuck self-upgrade can't permanently wedge this queue.
            waited = 0
            while not pi_lock.acquire("web_queue"):
                if waited >= 900:  # 15 min
                    feature_requests_manager.append_log(
                        req.id, "Proceeding despite an active self-upgrade lock (waited 15 min)."
                    )
                    break
                await asyncio.sleep(5)
                waited += 5

            try:
                async for event in run_pi_agent(req.prompt):
                    etype = event.get("type")
                    content = event.get("content", "")

                    if etype == "file_change":
                        path = content.split(": ", 1)[-1] if ": " in content else content
                        feature_requests_manager.add_file_changed(req.id, path)
                        feature_requests_manager.append_log(req.id, content)
                    elif etype == "completed":
                        feature_requests_manager.update(req.id, status="completed", summary=content)
                    elif etype == "error":
                        feature_requests_manager.update(req.id, status="error", summary=content)
                        feature_requests_manager.append_log(req.id, f"Error: {content}")
                    elif content:
                        feature_requests_manager.append_log(req.id, content)
            except Exception as e:
                feature_requests_manager.update(req.id, status="error", summary=str(e))
            finally:
                pi_lock.release("web_queue")

            # Safety net: if the generator ended without an explicit terminal status
            latest = feature_requests_manager.get(req.id)
            if latest and latest.status == "running":
                feature_requests_manager.update(req.id, status="completed", summary="Finished.")
    finally:
        _pi_worker_task = None


def _ensure_pi_worker_running():
    global _pi_worker_task
    if _pi_worker_task is None or _pi_worker_task.done():
        _pi_worker_task = asyncio.create_task(_process_pi_queue())


@app.get("/api/chatty/requests", dependencies=[Depends(require_api_key)])
async def get_requests():
    return [r.to_dict() for r in feature_requests_manager.list()]


@app.post("/api/chatty/requests", dependencies=[Depends(require_api_key)], status_code=201)
async def create_request(body: FeatureRequestCreate):
    prompt = body.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt is required")
    req = feature_requests_manager.create(prompt)
    _ensure_pi_worker_running()
    return req.to_dict()


@app.delete("/api/chatty/requests/{request_id}", dependencies=[Depends(require_api_key)])
async def delete_request(request_id: str):
    req = feature_requests_manager.get(request_id)
    if req is None:
        raise HTTPException(status_code=404, detail="Request not found")
    if req.status == "running":
        raise HTTPException(status_code=409, detail="Cannot delete a running request")
    feature_requests_manager.delete(request_id)
    return {"deleted": True}


# ── Memory viewer ─────────────────────────────────────────────────────────────
@app.get("/api/chatty/memory", dependencies=[Depends(require_api_key)])
async def get_memory(days: int = Query(default=7, ge=1, le=90)):
    user_memory_dir = MEMORY_DIR / WEB_USER_ID
    result = {"short_term": [], "long_term": []}

    for scope_key, folder_name in [("short_term", "short_term"), ("long_term", "long_term")]:
        scope_dir = user_memory_dir / folder_name
        if not scope_dir.exists():
            continue
        files = sorted(scope_dir.glob("*.md"), key=lambda p: p.stem, reverse=True)[:days]
        for f in files:
            result[scope_key].append({
                "date": f.stem,
                "content": f.read_text(encoding="utf-8"),
                "filename": f.name,
            })

    return result


# ── Code browser (read-only) ──────────────────────────────────────────────────
def _is_excluded_component(name: str) -> bool:
    if name.startswith(".") or name in CODE_EXCLUDE_DIRS:
        return True
    lower = name.lower()
    return any(fnmatch.fnmatch(lower, pat) for pat in CODE_EXCLUDE_FILE_GLOBS)


def _resolve_code_path(rel_path: str) -> Path:
    root = PROJECT_ROOT.resolve()
    candidate = (PROJECT_ROOT / (rel_path or "").strip().lstrip("/")).resolve()
    try:
        parts = candidate.relative_to(root).parts
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid path")
    if any(_is_excluded_component(p) for p in parts):
        raise HTTPException(status_code=403, detail="Path is not browsable")
    if not candidate.exists():
        raise HTTPException(status_code=404, detail="Not found")
    return candidate


@app.get("/api/chatty/code/tree", dependencies=[Depends(require_api_key)])
async def get_code_tree(path: str = Query(default="")):
    target = _resolve_code_path(path)
    if not target.is_dir():
        raise HTTPException(status_code=400, detail="Path is not a directory")

    root = PROJECT_ROOT.resolve()
    entries = []
    for child in sorted(target.iterdir(), key=lambda p: (p.is_file(), p.name.lower())):
        if _is_excluded_component(child.name):
            continue
        is_dir = child.is_dir()
        entries.append({
            "name": child.name,
            "path": str(child.resolve().relative_to(root)),
            "type": "dir" if is_dir else "file",
            "size": None if is_dir else child.stat().st_size,
        })

    resolved = target.resolve()
    return {
        "path": "" if resolved == root else str(resolved.relative_to(root)),
        "entries": entries,
    }


@app.get("/api/chatty/code/file", dependencies=[Depends(require_api_key)])
async def get_code_file(path: str = Query(default="")):
    target = _resolve_code_path(path)
    if not target.is_file():
        raise HTTPException(status_code=400, detail="Path is not a file")

    ext = target.suffix.lower()
    if ext in CODE_BINARY_EXTENSIONS:
        raise HTTPException(status_code=415, detail="Binary file — preview not supported")

    size = target.stat().st_size
    if size > CODE_MAX_FILE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large to preview ({size:,} bytes, limit {CODE_MAX_FILE_BYTES:,})",
        )

    try:
        content = target.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=415, detail="Binary file — preview not supported")

    return {
        "path": str(target.resolve().relative_to(PROJECT_ROOT.resolve())),
        "name": target.name,
        "size": size,
        "language": CODE_LANGUAGE_MAP.get(ext, "text"),
        "content": content,
    }


# ── System status ─────────────────────────────────────────────────────────────
@app.get("/api/chatty/system", dependencies=[Depends(require_api_key)])
async def get_system():
    # Skills
    skill_list = []
    if skills_manager:
        for name, skill in skills_manager.skills.items():
            skill_list.append({
                "name": name,
                "description": skill.description,
                "tool_count": len(skill.tools),
                "tools": [t.name for t in skill.tools],
            })

    # pm2 status
    pm2_processes = []
    try:
        result = subprocess.run(
            ["pm2", "jlist"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            procs = json.loads(result.stdout)
            for p in procs:
                pm2_processes.append({
                    "name": p.get("name"),
                    "status": p.get("pm2_env", {}).get("status"),
                    "pid": p.get("pid"),
                    "uptime": p.get("pm2_env", {}).get("pm_uptime"),
                    "restarts": p.get("pm2_env", {}).get("restart_time", 0),
                })
    except Exception as e:
        pm2_processes = [{"error": str(e)}]

    return {
        "skills": skill_list,
        "pm2": pm2_processes,
        "web_user_id": WEB_USER_ID,
        "timestamp": datetime.utcnow().isoformat(),
    }


# ── Chat Sessions ─────────────────────────────────────────────────────────────
@app.get("/api/chatty/sessions", dependencies=[Depends(require_api_key)])
async def get_sessions():
    """List conversation sessions (newest first)."""
    from src.core.memory import ConversationHistoryManager
    mgr = ConversationHistoryManager(WEB_USER_ID)
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
        })
    return result


@app.get("/api/chatty/sessions/{session_id}", dependencies=[Depends(require_api_key)])
async def get_session_messages(session_id: int):
    """Return messages for a specific session."""
    from src.core.memory import ConversationHistoryManager
    mgr = ConversationHistoryManager(WEB_USER_ID)
    messages = await mgr.get_session(session_id)
    return messages


# ── WebSocket Chat ────────────────────────────────────────────────────────────
@app.websocket("/api/chatty/chat")
async def websocket_chat(websocket: WebSocket, api_key: str = Query(default=""), session_id: str = Query(default="")):
    if api_key != API_KEY:
        await websocket.close(code=4401)
        return

    await websocket.accept()

    # Import here to avoid circular deps at module load
    from src.agents.web_chat_agent import WebChatAgent
    from src.core.memory import MemoryManager, ConversationHistoryManager

    memory_manager = MemoryManager(WEB_USER_ID)
    agent = WebChatAgent(skills_manager=skills_manager, memory_manager=memory_manager)

    # Conversation history manager for persistent JSON history
    history_mgr = ConversationHistoryManager(WEB_USER_ID)

    # Load session context if a session_id is provided
    active_session_id: Optional[int] = None
    if session_id and session_id.isdigit():
        active_session_id = int(session_id)
        try:
            session_msgs = await history_mgr.get_session(active_session_id)
            if session_msgs:
                # Pre-populate agent history with session messages
                agent._history = session_msgs
        except Exception as e:
            logger.error(f"Failed to preload session {active_session_id} for user {WEB_USER_ID}: {e}")

    # Notify client of active session
    await websocket.send_text(json.dumps({
        "type": "session_loaded",
        "session_id": active_session_id,
        "message_count": len(agent._history) if active_session_id is not None else 0,
    }))

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
                user_message = data.get("message", "").strip()
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({"type": "error", "text": "Invalid JSON"}))
                continue

            if not user_message:
                continue

            # Stream agent response and collect full text
            assistant_response = ""
            try:
                async for chunk in agent.stream(user_message):
                    await websocket.send_text(json.dumps({"type": "chunk", "text": chunk}))
                    assistant_response += chunk
                await websocket.send_text(json.dumps({"type": "done"}))

                # Persist to conversation history (JSON) so /sessions endpoint works
                try:
                    await history_mgr.append(user_message, assistant_response)
                except Exception as e:
                    # Don't break the chat if history save fails, but don't hide it either
                    logger.error(f"Failed to save chat history for user {WEB_USER_ID}: {e}")
            except Exception as e:
                await websocket.send_text(json.dumps({"type": "error", "text": str(e)}))

    except WebSocketDisconnect:
        pass


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("chatty_web_server:app", host="0.0.0.0", port=PORT, reload=False)
