"""Chatty Web Server - FastAPI backend for the Chatty web dashboard.

Port: 8016
Provides REST + WebSocket endpoints for:
- Chat (WebSocket, streams agent responses)
- Notes (CRUD)
- Reminders (read + delete)
- Memory viewer (read-only)
- System status (skills, pm2)
"""
import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv

# Load env
load_dotenv()

# ── Ensure project root is on sys.path so src/ imports work ─────────────────
PROJECT_ROOT = Path(__file__).parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core import config
from src.core.skills_manager import SkillsManager
from skills.notes.notes_manager import NotesManager
from skills.pi_agent.requests_manager import FeatureRequestsManager
from skills.pi_agent.runner import run_pi_agent

# ── Config ───────────────────────────────────────────────────────────────────
API_KEY = os.getenv("CHATTY_WEB_API_KEY", "changeme")
WEB_USER_ID = os.getenv("WEB_USER_ID", "")
REMINDERS_DIR = PROJECT_ROOT / "reminders"
MEMORY_DIR = PROJECT_ROOT / "memory"
PORT = int(os.getenv("CHATTY_WEB_PORT", "8016"))

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


# ── WebSocket Chat ────────────────────────────────────────────────────────────
@app.websocket("/api/chatty/chat")
async def websocket_chat(websocket: WebSocket, api_key: str = Query(default="")):
    if api_key != API_KEY:
        await websocket.close(code=4401)
        return

    await websocket.accept()

    # Import here to avoid circular deps at module load
    from src.agents.web_chat_agent import WebChatAgent
    from src.core.memory import MemoryManager

    memory_manager = MemoryManager(WEB_USER_ID)
    agent = WebChatAgent(skills_manager=skills_manager, memory_manager=memory_manager)

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

            # Stream agent response
            try:
                async for chunk in agent.stream(user_message):
                    await websocket.send_text(json.dumps({"type": "chunk", "text": chunk}))
                await websocket.send_text(json.dumps({"type": "done"}))
            except Exception as e:
                await websocket.send_text(json.dumps({"type": "error", "text": str(e)}))

    except WebSocketDisconnect:
        pass


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("chatty_web_server:app", host="0.0.0.0", port=PORT, reload=False)
