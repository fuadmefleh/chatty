"""Chatty Web Server - FastAPI backend for the Chatty web dashboard.

Port: 8016
Provides REST + WebSocket endpoints for:
- Chat (WebSocket, streams agent responses)
- Notes (CRUD)
- Transcriptions (create/list/delete - staged for automatic memory mining)
- Audio ingestion (raw-body upload -> WhisperX STT -> transcriptions queue)
- Media ingestion (raw-body photo/video upload -> vision/STT -> transcriptions queue)
- Reminders (read + delete)
- Memory viewer (read-only)
- Code browser (read-only)
- System status (skills, pm2)
"""
import asyncio
import base64
import fnmatch
import hmac
import json
import importlib.util
import os
import re
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from datetime import datetime
import contextlib
from collections import defaultdict
from typing import Dict, List, Optional, Tuple
from urllib.parse import unquote

from fastapi import (
    FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, Header,
    Query, Request, BackgroundTasks, UploadFile, File,
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
from src.core.stt import get_stt_provider, TranscriptionResult
from skills.notes.notes_manager import NotesManager
from skills.transcriptions.transcriptions_manager import TranscriptionsManager, render_segments
from skills.speakers.speaker_manager import SpeakerManager
from skills.watchlist.watchlist_manager import WatchlistManager
from src.managers.insights_manager import InsightsManager
from skills.pi_agent.requests_manager import FeatureRequestsManager
from skills.pi_agent import lock as pi_lock
from src.managers.self_upgrade_manager import run_feature_request
from src.managers.trending_manager import TrendingSuggestionsManager, run_trending_scan
from src.managers.webcam_manager import WEBCAM_KINDS, WebcamSourcesManager, WebcamSuggestionsManager
from src.managers.webcam_discovery import run_webcam_discovery_scan
from src.core.token_usage_manager import get_token_usage_manager

logger = get_api_logger()

# ── Config ───────────────────────────────────────────────────────────────────
API_KEY = os.getenv("CHATTY_WEB_API_KEY", "changeme")
WEB_USER_ID = os.getenv("WEB_USER_ID", "")
REMINDERS_DIR = PROJECT_ROOT / "reminders"
MEMORY_DIR = PROJECT_ROOT / "memory"
PORT = int(os.getenv("CHATTY_WEB_PORT", "8016"))

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
speaker_manager = SpeakerManager()
watchlist_manager = WatchlistManager()
insights_manager = InsightsManager()
feature_requests_manager = FeatureRequestsManager()
trending_suggestions_manager = TrendingSuggestionsManager()
webcam_sources_manager = WebcamSourcesManager()
webcam_suggestions_manager = WebcamSuggestionsManager()
token_usage_manager = get_token_usage_manager()
skills_manager: Optional[SkillsManager] = None
_pi_worker_task: Optional[asyncio.Task] = None


class _ChatConnection:
    """An open /api/chatty/chat WebSocket, keyed by X-Device-Id so the audio
    pipeline can push a proactive assistant response onto it. The lock
    serializes sends across the interactive request/response loop and any
    background push, since Starlette WebSockets aren't safe for concurrent
    send_text calls from multiple tasks."""

    __slots__ = ("websocket", "lock")

    def __init__(self, websocket: "WebSocket"):
        self.websocket = websocket
        self.lock = asyncio.Lock()

    async def send_json(self, payload: dict) -> None:
        async with self.lock:
            await self.websocket.send_text(json.dumps(payload))


# device_id -> open chat connection (only devices that sent X-Device-Id on
# the WS handshake are tracked; at most one entry per device).
_active_chat_connections: Dict[str, _ChatConnection] = {}


@app.on_event("startup")
async def startup_event():
    global skills_manager
    skills_manager = SkillsManager()
    await skills_manager.load_skills()
    print(f"[chatty-web] Loaded {len(skills_manager.skills)} skills")
    print(f"[chatty-web] Listening on port {PORT}")


# ── Auth dependency ──────────────────────────────────────────────────────────
# Per-IP lockout to make the API key impractical to brute force: too many
# wrong guesses in a short window locks that IP out for a cooldown period,
# regardless of whether the latest guess was correct.
AUTH_MAX_ATTEMPTS = 5
AUTH_WINDOW_SECONDS = 60
AUTH_LOCKOUT_SECONDS = 300

_auth_failures: Dict[str, List[float]] = defaultdict(list)
_auth_locked_until: Dict[str, float] = {}


def _client_ip(request: Request) -> str:
    # nginx (docker/nginx/default.conf) sets X-Real-IP for every proxied
    # request; request.client.host would otherwise just be the nginx hop.
    return request.headers.get("x-real-ip") or (request.client.host if request.client else "unknown")


def _verify_api_key(provided: str, ip: str) -> None:
    """Shared lockout + constant-time compare, used by both the header-only
    (require_api_key) and header-or-query (require_api_key_flexible) dependencies."""
    now = time.monotonic()

    locked_until = _auth_locked_until.get(ip)
    if locked_until is not None:
        if now < locked_until:
            retry_after = int(locked_until - now) + 1
            raise HTTPException(
                status_code=429,
                detail="Too many invalid API key attempts. Try again later.",
                headers={"Retry-After": str(retry_after)},
            )
        del _auth_locked_until[ip]

    if not hmac.compare_digest(provided, API_KEY):
        attempts = [t for t in _auth_failures[ip] if now - t < AUTH_WINDOW_SECONDS]
        attempts.append(now)
        _auth_failures[ip] = attempts
        if len(attempts) >= AUTH_MAX_ATTEMPTS:
            _auth_locked_until[ip] = now + AUTH_LOCKOUT_SECONDS
            del _auth_failures[ip]
            raise HTTPException(
                status_code=429,
                detail="Too many invalid API key attempts. Try again later.",
                headers={"Retry-After": str(AUTH_LOCKOUT_SECONDS)},
            )
        raise HTTPException(status_code=401, detail="Invalid API key")

    _auth_failures.pop(ip, None)


async def require_api_key(request: Request, x_api_key: str = Header(default="")):
    _verify_api_key(x_api_key, _client_ip(request))


async def require_api_key_flexible(
    request: Request, x_api_key: str = Header(default=""), api_key: str = Query(default=""),
):
    """Same as require_api_key, but also accepts the key as an `api_key` query
    param - needed for chat-media, since plain <img>/<video> tags can't set a
    custom header (mirrors websocket_chat's own `api_key: str = Query(...)` auth)."""
    _verify_api_key(x_api_key or api_key, _client_ip(request))


# ── Health / root ─────────────────────────────────────────────────────────────
@app.get("/")
async def root():
    return {"service": "chatty-web-api", "status": "ok", "version": "1.0.0"}


@app.get("/api/chatty/health")
async def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


# ── Server Health (CPU, RAM, Disk, GPU) ──────────────────────────────────────
def _get_gpu_info() -> list[dict]:
    """Query NVIDIA GPUs via nvidia-smi."""
    try:
        result = subprocess.run(
            ["nvidia-smi",
             "--query-gpu=name,memory.used,memory.total,utilization.gpu,"
             "utilization.memory,temperature.gpu,power.draw,power.limit,"
             "clocks.gr,clocks.mem,driver_version",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return []
        gpus = []
        for line in result.stdout.strip().splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 10:
                gpus.append({
                    "name": parts[0],
                    "memory_used_miB": _parse_int(parts[1]),
                    "memory_total_miB": _parse_int(parts[2]),
                    "gpu_util_percent": _parse_float(parts[3]),
                    "mem_util_percent": _parse_float(parts[4]),
                    "temperature_c": _parse_float(parts[5]),
                    "power_draw_w": _parse_float(parts[6]),
                    "power_limit_w": _parse_float(parts[7]),
                    "clock_gr_mhz": _parse_int(parts[8]),
                    "clock_mem_mhz": _parse_int(parts[9]),
                    "driver_version": parts[10] if len(parts) > 10 else "unknown",
                })
        return gpus
    except Exception:
        return []


def _parse_int(val: str) -> int:
    try:
        return int(val)
    except (ValueError, TypeError):
        return 0


def _parse_float(val: str) -> float:
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0


@app.get("/api/chatty/health/server", dependencies=[Depends(require_api_key)])
async def server_health():
    """Return server resource metrics: CPU, RAM, disk, GPU, load, uptime."""
    import psutil

    # CPU
    cpu_logical = psutil.cpu_count(logical=True)
    cpu_physical = psutil.cpu_count(logical=False)
    cpu_percent = psutil.cpu_percent(interval=0.1)
    per_cpu = psutil.cpu_percent(interval=0.1, percpu=True)
    load_avg = {}  # type: dict[str, float]
    try:
        la = psutil.getloadavg()
        load_avg = {"1m": la[0], "5m": la[1], "15m": la[2]}
    except (OSError, AttributeError):
        pass

    # RAM
    vm = psutil.virtual_memory()
    ram = {
        "total_bytes": vm.total,
        "used_bytes": vm.used,
        "available_bytes": vm.available,
        "percent": vm.percent,
    }

    # Swap
    swap = psutil.swap_memory()
    swap_info = {
        "total_bytes": swap.total,
        "used_bytes": swap.used,
        "percent": swap.percent,
    }

    # Disk partitions (skip squashfs snap mounts - noise, not real filesystems)
    disks = []
    for part in psutil.disk_partitions(all=False):
        if part.fstype == "squashfs" or part.mountpoint.startswith("/snap/"):
            continue
        try:
            usage = psutil.disk_usage(part.mountpoint)
            disks.append({
                "device": part.device,
                "mountpoint": part.mountpoint,
                "fstype": part.fstype,
                "total_bytes": usage.total,
                "used_bytes": usage.used,
                "free_bytes": usage.free,
                "percent": usage.percent,
            })
        except PermissionError:
            pass

    # Network I/O counters (snapshot)
    net = psutil.net_io_counters()
    network = {
        "bytes_sent": net.bytes_sent,
        "bytes_recv": net.bytes_recv,
        "packets_sent": net.packets_sent,
        "packets_recv": net.packets_recv,
    }

    # Uptime
    boot_time = datetime.fromtimestamp(psutil.boot_time())
    uptime_seconds = (datetime.now() - boot_time).total_seconds()

    # GPU
    gpus = _get_gpu_info()

    return {
        "cpu": {
            "logical_cores": cpu_logical,
            "physical_cores": cpu_physical,
            "overall_percent": cpu_percent,
            "per_core_percent": per_cpu,
            "load_average": load_avg,
        },
        "memory": ram,
        "swap": swap_info,
        "disks": disks,
        "network": network,
        "gpus": gpus,
        "boot_time": boot_time.isoformat(),
        "uptime_seconds": uptime_seconds,
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/api/chatty/token-usage/summary", dependencies=[Depends(require_api_key)])
async def token_usage_summary(days: int = 30):
    """Return aggregate LLM token usage: totals, per-model/provider breakdown, daily series."""
    return token_usage_manager.get_summary(days=days)


@app.get("/api/chatty/token-usage/recent", dependencies=[Depends(require_api_key)])
async def token_usage_recent(limit: int = 50):
    """Return the most recent individual LLM requests logged."""
    return token_usage_manager.get_recent(limit=limit)


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


def _find_transcription(transcription_id: str):
    """Look up a transcription by id, pending or archived."""
    for t in transcriptions_manager.get_pending(WEB_USER_ID) + transcriptions_manager.get_archived(WEB_USER_ID):
        if t.id == transcription_id:
            return t
    return None


@app.get("/api/chatty/transcriptions/{transcription_id}/segments", dependencies=[Depends(require_api_key)])
async def get_transcription_segments(transcription_id: str):
    """Structured, time-aligned segments with currently-resolved speaker
    names, for the speaker-labeling page. Fetched lazily per transcript
    (mirrors the audio blob's lazy-load pattern) rather than embedded in the
    main transcriptions list, since most of the list is never expanded."""
    transcription = _find_transcription(transcription_id)
    if transcription is None:
        raise HTTPException(status_code=404, detail="Transcription not found")
    if transcription.segments is None:
        return {"segments": []}

    labels = transcription.speaker_labels or {}
    return {
        "segments": [
            {
                "start": seg.get("start"),
                "end": seg.get("end"),
                "local_speaker": seg.get("local_speaker"),
                "speaker_name": labels.get(seg["local_speaker"]) if seg.get("local_speaker") else None,
                "text": seg.get("text"),
            }
            for seg in transcription.segments
        ]
    }


def _rescan_transcripts_for_speaker(exclude_id: Optional[str] = None) -> int:
    """Re-check every stored transcript's per-file speaker embeddings against
    the roster, staging speaker_labels updates for any newly-matching local
    speakers (never overwriting an existing label). Applied via one batched
    write per file - the "face recognition tags other photos too" moment for
    already-backfilled data.

    Called automatically after each manual label (excluding the transcript
    just labeled, since that one was already updated directly), and also
    exposed as a standalone "rescan unmatched" action a user can trigger any
    time - e.g. after tuning SPEAKER_MATCH_THRESHOLD, or to sweep up anything
    an earlier rescan's threshold missed."""
    updates: dict = {}
    all_transcripts = transcriptions_manager.get_pending(WEB_USER_ID) + transcriptions_manager.get_archived(WEB_USER_ID)
    for t in all_transcripts:
        if t.id == exclude_id or not t.speaker_embeddings:
            continue
        labels = dict(t.speaker_labels or {})
        changed = False
        for local_speaker, embedding in t.speaker_embeddings.items():
            if labels.get(local_speaker):
                continue
            match = speaker_manager.match(WEB_USER_ID, embedding)
            if match:
                labels[local_speaker] = match[0]["name"]
                changed = True
        if changed:
            updates[t.id] = {"speaker_labels": labels}

    if not updates:
        return 0
    return transcriptions_manager.update_transcriptions_batch(WEB_USER_ID, updates)


class SpeakerLabelRequest(BaseModel):
    local_speaker: str
    name: Optional[str] = None
    speaker_id: Optional[str] = None


@app.post("/api/chatty/transcriptions/{transcription_id}/label", dependencies=[Depends(require_api_key)])
async def label_speaker(transcription_id: str, body: SpeakerLabelRequest):
    """Assign a real name to a generic diarization speaker id (e.g.
    "SPEAKER_00") within one transcript, either creating a new roster entry
    or attaching another voice sample to an existing one, then retroactively
    relabels every other stored transcript where that voice already
    appears."""
    transcription = _find_transcription(transcription_id)
    if transcription is None:
        raise HTTPException(status_code=404, detail="Transcription not found")
    if not transcription.speaker_embeddings or body.local_speaker not in transcription.speaker_embeddings:
        raise HTTPException(status_code=400, detail="No voice embedding available for this speaker in this transcript")
    if not body.name and not body.speaker_id:
        raise HTTPException(status_code=400, detail="Provide either name (new speaker) or speaker_id (existing speaker)")

    embedding = transcription.speaker_embeddings[body.local_speaker]

    if body.speaker_id:
        speaker = speaker_manager.get_speaker(WEB_USER_ID, body.speaker_id)
        if speaker is None:
            raise HTTPException(status_code=404, detail="Speaker not found")
        speaker_manager.add_sample(WEB_USER_ID, speaker["id"], embedding, transcription_id=transcription_id)
    else:
        speaker = speaker_manager.create_speaker(WEB_USER_ID, body.name, embedding, transcription_id=transcription_id)

    new_labels = dict(transcription.speaker_labels or {})
    new_labels[body.local_speaker] = speaker["name"]
    transcriptions_manager.update_transcription(WEB_USER_ID, transcription_id, speaker_labels=new_labels)

    also_updated = _rescan_transcripts_for_speaker(exclude_id=transcription_id)

    return {"speaker": speaker_manager.to_public(speaker), "also_updated_count": also_updated}


# ── Speakers (named voice roster) ────────────────────────────────────────────
class SpeakerRename(BaseModel):
    name: str


@app.get("/api/chatty/speakers", dependencies=[Depends(require_api_key)])
async def get_speakers():
    return speaker_manager.list_speakers(WEB_USER_ID)


@app.put("/api/chatty/speakers/{speaker_id}", dependencies=[Depends(require_api_key)])
async def rename_speaker(speaker_id: str, body: SpeakerRename):
    speaker = speaker_manager.rename_speaker(WEB_USER_ID, speaker_id, body.name)
    if speaker is None:
        raise HTTPException(status_code=404, detail="Speaker not found")
    return speaker_manager.to_public(speaker)


@app.delete("/api/chatty/speakers/{speaker_id}", dependencies=[Depends(require_api_key)])
async def delete_speaker(speaker_id: str):
    """Remove a speaker from the roster - does not retroactively strip labels
    already written into transcripts, only stops future matching."""
    ok = speaker_manager.delete_speaker(WEB_USER_ID, speaker_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Speaker not found")
    return {"deleted": True}


@app.post("/api/chatty/speakers/rescan", dependencies=[Depends(require_api_key)])
async def rescan_speakers():
    """Manually sweep every transcript's unmatched speaker embeddings against
    the full roster right now, rather than waiting for the next manual label
    action to trigger it as a side effect. Useful after tuning
    SPEAKER_MATCH_THRESHOLD, or just to force a fresh pass over anything an
    earlier rescan missed."""
    updated_count = _rescan_transcripts_for_speaker()
    return {"updated_count": updated_count}


# ── Audio ingestion (iOS app) ────────────────────────────────────────────────
# Raw-body (not multipart) audio chunk upload. Transcribed via the WhisperX
# STT engine already running on this host, then fed into the same
# TranscriptionsManager pending queue as text transcriptions - the existing
# heartbeat mining step (HeartbeatManager._process_transcription_mining)
# picks it up from there unchanged.
def _normalize_segments(result: TranscriptionResult) -> Optional[List[dict]]:
    """Convert STT engine segments ({speaker, start, end, text}) into our
    stored shape ({local_speaker, start, end, text}). Returns None when the
    STT engine returned no segments at all, so callers can fall back to
    plain `text` instead of storing an empty segments list."""
    raw_segments = result.segments or []
    if not raw_segments:
        return None
    return [
        {
            "start": seg.get("start"),
            "end": seg.get("end"),
            "local_speaker": seg.get("speaker"),
            "text": (seg.get("text") or "").strip(),
        }
        for seg in raw_segments
    ]


# ── Assistant mode (wake-word push over the chat WebSocket) ─────────────────
_WAKE_WORD_RE = re.compile(r"\bchatty\b", re.IGNORECASE)
_ASSISTANT_FALLBACK_PROMPT = (
    "The user just said your name (\"Chatty\") in this audio chunk with nothing "
    "obvious following it. Check recent conversation context for what they might "
    "want; if nothing fits, just give a brief, natural acknowledgment like "
    "\"Yeah?\" or \"What's up?\" inviting them to continue."
)


def _extract_assistant_query(transcript: str) -> Optional[str]:
    """Return the text after the first "chatty" mention (trimmed), or None if
    "chatty" doesn't appear at all. An empty string (as opposed to None) means
    "chatty" was said with nothing following it - callers should treat that as
    a contentless wake word, not "no wake word", and fall back accordingly."""
    match = _WAKE_WORD_RE.search(transcript)
    if not match:
        return None
    return transcript[match.end():].strip()


async def _push_assistant_response(device_id: str, query: str) -> None:
    """Generate a response via the same agent/memory stack as the chat
    WebSocket and stream it over that device's open connection, if any. Silently
    drops the response (no error) when the device has no open connection, e.g.
    the app is backgrounded."""
    connection = _active_chat_connections.get(device_id)
    if connection is None:
        logger.info(f"No open chat WebSocket for device {device_id}; dropping assistant push")
        return

    from src.agents.web_chat_agent import WebChatAgent
    from src.core.memory import MemoryManager

    memory_manager = MemoryManager(WEB_USER_ID)
    agent = WebChatAgent(skills_manager=skills_manager, memory_manager=memory_manager)

    try:
        async for chunk in agent.stream(query):
            await connection.send_json({"type": "chunk", "content": chunk})
        await connection.send_json({"type": "done"})
    except Exception as e:
        logger.error(f"Failed to push assistant response to device {device_id}: {e}")


async def _transcribe_and_store_audio(
    audio_bytes: bytes, device_id: str, chunk_start: str, chunk_duration: str, source: str,
    assistant_mode: bool = False,
) -> None:
    try:
        result = await get_stt_provider().transcribe(audio_bytes, filename_hint="chunk.m4a")

        segments = _normalize_segments(result)
        speaker_embeddings = result.speaker_embeddings or {}

        # Auto-label any local speaker whose voice already matches a known
        # roster entry - the "face recognition recognizes you automatically"
        # step for brand-new recordings.
        speaker_labels = {}
        for local_speaker, embedding in speaker_embeddings.items():
            match = speaker_manager.match(WEB_USER_ID, embedding)
            if match:
                speaker_labels[local_speaker] = match[0]["name"]

        transcript = render_segments(segments, speaker_labels) if segments else result.text
        if not transcript:
            logger.info(f"Audio chunk from device {device_id} at {chunk_start} had no speech, skipping")
            return

        if assistant_mode:
            query = _extract_assistant_query(transcript)
            if query is not None:
                # Wake word detected: handle as a proactive assistant query
                # instead of a regular transcript segment, so it's never also
                # mined into long-term memory (the exchange itself still lands
                # in memory via WebChatAgent.stream's own add_interaction call).
                logger.info(f"Assistant wake word detected from device {device_id} at {chunk_start}")
                await _push_assistant_response(device_id, query or _ASSISTANT_FALLBACK_PROMPT)
                return

        audio_filename = transcriptions_manager.save_audio(audio_bytes)
        header = f"[{chunk_start}] (device {device_id}, {chunk_duration}s audio)"
        content = f"{header} {transcript}"
        transcriptions_manager.add_transcription(
            WEB_USER_ID, content, source=source, audio_filename=audio_filename,
            segments=segments, speaker_embeddings=speaker_embeddings or None,
            speaker_labels=speaker_labels or None, header=header,
        )
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
    x_mode: str = Header(default=""),
):
    audio_bytes = await request.body()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio body")

    background_tasks.add_task(
        _transcribe_and_store_audio, audio_bytes, x_device_id, x_chunk_start, x_chunk_duration, x_source,
        x_mode.strip().lower() == "assistant",
    )
    return {"accepted": True}


# ── Media ingestion (iOS app) ────────────────────────────────────────────────
# Raw-body (not multipart) single-file photo/video upload. Vision-describes
# images and summarizes videos (keyframes + audio track STT), then feeds the
# resulting text into the same TranscriptionsManager pending queue as audio/
# text transcriptions - the heartbeat's mining step picks it up unchanged.
# Never surfaced in Notes.
MEDIA_MAX_BYTES = 200 * 1024 * 1024  # videos arrive pre-compressed to 720p, so this is generous
MEDIA_IMAGE_FORMATS = {"image/jpeg": "jpg", "image/heic": "heic", "image/png": "png", "image/webp": "webp"}
MEDIA_VIDEO_FORMATS = {"video/quicktime": "mov", "video/mp4": "mp4", "video/webm": "webm"}
MEDIA_VIDEO_KEYFRAME_COUNT = 3


def _decode_caption(raw: str) -> Optional[str]:
    if not raw:
        return None
    try:
        decoded = unquote(raw, encoding="utf-8", errors="strict")
    except Exception:
        decoded = raw
    return decoded.strip() or None


async def _describe_image(jpeg_b64: str, prompt: str) -> str:
    """Vision-describe a single JPEG image, falling back to a one-off OpenAI
    vision call if the configured chat provider doesn't support vision -
    same fallback src.main's Telegram photo handler uses."""
    from src.core import config
    from src.core.llm.factory import get_llm_provider
    from src.core.llm.openai_provider import OpenAIProvider

    provider = get_llm_provider()
    if provider.supports_vision:
        return await provider.complete_vision(prompt, image_b64=jpeg_b64, max_tokens=500)
    if config.OPENAI_API_KEY:
        fallback = OpenAIProvider(
            api_key=config.OPENAI_API_KEY, base_url=None, model="gpt-4o", supports_vision=True,
        )
        return await fallback.complete_vision(prompt, image_b64=jpeg_b64, max_tokens=500)
    raise RuntimeError("No vision-capable LLM provider configured (set OPENAI_API_KEY, or CHAT_PROVIDER=anthropic)")


async def _summarize_video_notes(raw_notes: str) -> str:
    from src.core.llm.factory import get_llm_provider

    prompt = (
        "Summarize this video into a short paragraph, combining what happens "
        "visually across the sampled frames with anything said in the audio "
        "transcript (if present). Focus on facts worth remembering: people, "
        "places, events, plans.\n\n" + raw_notes
    )
    response = await get_llm_provider().complete([{"role": "user", "content": prompt}])
    return response.content


def _convert_image_to_jpeg_b64(image_bytes: bytes, image_format: str) -> str:
    """Normalize any supported image format (jpeg/heic/png) to real JPEG
    bytes via ImageMagick (auto-orienting per EXIF), since the vision
    providers' complete_vision() hardcodes an image/jpeg mime type in the
    request payload - HEIC in particular isn't understood by either vision
    API directly."""
    result = subprocess.run(
        ["convert", f"{image_format}:-", "-auto-orient", "jpeg:-"],
        input=image_bytes, capture_output=True, timeout=30, check=True,
    )
    return base64.b64encode(result.stdout).decode("ascii")


def _ffprobe_duration(path: str) -> Optional[float]:
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
            capture_output=True, text=True, timeout=15, check=True,
        )
        return float(result.stdout.strip())
    except Exception:
        return None


def _extract_frame_at(path: str, timestamp: float) -> Optional[bytes]:
    try:
        result = subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-ss", str(timestamp), "-i", path,
             "-frames:v", "1", "-f", "image2pipe", "-vcodec", "mjpeg", "-"],
            capture_output=True, timeout=30, check=True,
        )
        return result.stdout or None
    except Exception:
        return None


def _extract_audio_track(path: str) -> Optional[bytes]:
    """Extract the audio track as an mp4/m4a file. Written to a real temp
    file rather than piped to stdout - the mp4 muxer needs a seekable
    output to write its header, unlike the mjpeg frame grabs above."""
    with tempfile.NamedTemporaryFile(suffix=".m4a") as tmp_out:
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-v", "error", "-i", path, "-vn", "-acodec", "aac", "-f", "mp4", tmp_out.name],
                capture_output=True, timeout=60, check=True,
            )
        except Exception:
            return None
        data = tmp_out.read()
        return data or None


def _extract_video_parts(video_bytes: bytes, video_format: str) -> Tuple[List[bytes], Optional[bytes]]:
    with tempfile.NamedTemporaryFile(suffix=f".{video_format}") as tmp_in:
        tmp_in.write(video_bytes)
        tmp_in.flush()

        duration = _ffprobe_duration(tmp_in.name)
        fractions = [0.1, 0.5, 0.9] if duration else [0.0]
        keyframes = []
        for frac in fractions[:MEDIA_VIDEO_KEYFRAME_COUNT]:
            timestamp = duration * frac if duration else 0.0
            frame = _extract_frame_at(tmp_in.name, timestamp)
            if frame:
                keyframes.append(frame)

        audio_bytes = _extract_audio_track(tmp_in.name)

    return keyframes, audio_bytes


async def _process_image_media(
    media_bytes: bytes, image_format: str, device_id: str, caption: Optional[str],
    captured_at: str, source: str, filename: str,
) -> None:
    try:
        jpeg_b64 = await asyncio.to_thread(_convert_image_to_jpeg_b64, media_bytes, image_format)
    except Exception as e:
        logger.error(f"Failed to normalize image from device {device_id}: {e}")
        return

    prompt = (
        "Describe this photo in a few concise sentences: setting, people, "
        "objects, and anything notable. This description will be scanned "
        "for personal facts worth remembering, so include names, places, or "
        f"details mentioned in the caption if given.\n\nUser's caption: {caption or '(none)'}"
    )
    try:
        description = await _describe_image(jpeg_b64, prompt)
    except Exception as e:
        logger.error(f"Vision analysis failed for image from device {device_id}: {e}")
        return

    header = f"[{captured_at or datetime.utcnow().isoformat()}] (device {device_id}, image)"
    parts = [header, description.strip()]
    if caption:
        parts.append(f"Caption: {caption}")
    content = "\n".join(parts)

    transcriptions_manager.add_transcription(WEB_USER_ID, content, source=source, header=header)
    logger.info(f"Processed image media '{filename or '(unnamed)'}' from device {device_id}, queued for memory mining")


async def _process_video_media(
    media_bytes: bytes, video_format: str, device_id: str, caption: Optional[str],
    captured_at: str, source: str, filename: str,
) -> None:
    try:
        keyframes, audio_bytes = await asyncio.to_thread(_extract_video_parts, media_bytes, video_format)
    except Exception as e:
        logger.error(f"Failed to extract frames/audio from video from device {device_id}: {e}")
        return

    frame_descriptions = []
    for i, frame_bytes in enumerate(keyframes):
        frame_b64 = base64.b64encode(frame_bytes).decode("ascii")
        prompt = (
            f"This is frame {i + 1} of {len(keyframes)} sampled from a video, in "
            "chronological order. Describe what's happening in one or two sentences."
        )
        try:
            frame_descriptions.append((await _describe_image(frame_b64, prompt)).strip())
        except Exception as e:
            logger.error(f"Vision analysis failed for video frame {i} from device {device_id}: {e}")

    transcript = None
    if audio_bytes:
        try:
            result = await get_stt_provider().transcribe(audio_bytes, filename_hint="video_audio.m4a")
            transcript = (result.text or "").strip() or None
        except Exception as e:
            logger.error(f"STT failed for video audio from device {device_id}: {e}")

    if not frame_descriptions and not transcript:
        logger.info(f"Video from device {device_id} yielded no frame descriptions or transcript, skipping")
        return

    notes = "\n".join(f"Frame {i + 1}: {d}" for i, d in enumerate(frame_descriptions))
    if transcript:
        notes += f"\n\nAudio transcript: {transcript}"
    if caption:
        notes += f"\n\nUser's caption: {caption}"

    try:
        summary = (await _summarize_video_notes(notes)).strip()
    except Exception as e:
        logger.error(f"Failed to summarize video from device {device_id}: {e}")
        summary = notes  # fall back to the raw frame/transcript notes rather than dropping them

    header = f"[{captured_at or datetime.utcnow().isoformat()}] (device {device_id}, video)"
    content = f"{header} {summary}"

    transcriptions_manager.add_transcription(WEB_USER_ID, content, source=source, header=header)
    logger.info(f"Processed video media '{filename or '(unnamed)'}' from device {device_id}, queued for memory mining")


@app.post("/api/chatty/media", dependencies=[Depends(require_api_key)], status_code=202)
async def receive_media(
    request: Request,
    background_tasks: BackgroundTasks,
    x_device_id: str = Header(default=""),
    x_media_kind: str = Header(default=""),
    x_source: str = Header(default="ios_app"),
    x_captured_at: str = Header(default=""),
    x_caption: str = Header(default=""),
    x_filename: str = Header(default=""),
):
    content_type = (request.headers.get("content-type") or "").split(";")[0].strip().lower()
    if content_type in MEDIA_IMAGE_FORMATS:
        kind, media_format = "image", MEDIA_IMAGE_FORMATS[content_type]
    elif content_type in MEDIA_VIDEO_FORMATS:
        kind, media_format = "video", MEDIA_VIDEO_FORMATS[content_type]
    else:
        raise HTTPException(status_code=415, detail=f"Unsupported content type: {content_type or '(none)'}")

    if x_media_kind and x_media_kind != kind:
        logger.warning(
            f"X-Media-Kind ({x_media_kind}) doesn't match Content-Type ({content_type}) "
            f"from device {x_device_id}; trusting Content-Type"
        )

    content_length = request.headers.get("content-length")
    if content_length and content_length.isdigit() and int(content_length) > MEDIA_MAX_BYTES:
        raise HTTPException(status_code=413, detail=f"Media exceeds {MEDIA_MAX_BYTES:,} byte limit")

    media_bytes = await request.body()
    if not media_bytes:
        raise HTTPException(status_code=400, detail="Empty media body")
    if len(media_bytes) > MEDIA_MAX_BYTES:
        raise HTTPException(status_code=413, detail=f"Media exceeds {MEDIA_MAX_BYTES:,} byte limit")

    caption = _decode_caption(x_caption)

    if kind == "image":
        background_tasks.add_task(
            _process_image_media, media_bytes, media_format, x_device_id, caption, x_captured_at, x_source, x_filename
        )
    else:
        background_tasks.add_task(
            _process_video_media, media_bytes, media_format, x_device_id, caption, x_captured_at, x_source, x_filename
        )
    return {"accepted": True}


# ── Interactive chat media ───────────────────────────────────────────────────
# Images/videos the user attaches to a live chat message (see websocket_chat
# below), and images Chatty generates (skills/image_generation/). Distinct
# from the passive ingestion endpoint above: these are part of a live turn
# and get served straight back to the browser rather than mined into memory.
CHAT_ATTACHMENT_MAX_BYTES = 50 * 1024 * 1024
_CHAT_MEDIA_FILENAME_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.(jpg|jpeg|png|webp|heic|mp4|mov|webm)$"
)
_CHAT_MEDIA_EXT_TO_MIME = {
    "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
    "webp": "image/webp", "heic": "image/heic",
    "mp4": "video/mp4", "mov": "video/quicktime", "webm": "video/webm",
}
_CHAT_MEDIA_VIDEO_EXTS = {"mp4", "mov", "webm"}


def _chat_uploads_dir() -> Path:
    d = MEMORY_DIR / WEB_USER_ID / "uploads" / "chat"
    d.mkdir(parents=True, exist_ok=True)
    return d


@app.get("/api/chatty/chat-media/{filename}", dependencies=[Depends(require_api_key_flexible)])
async def get_chat_media(filename: str):
    if not _CHAT_MEDIA_FILENAME_RE.match(filename):
        raise HTTPException(status_code=400, detail="Invalid filename")

    uploads_dir = _chat_uploads_dir().resolve()
    path = (uploads_dir / filename).resolve()
    if uploads_dir not in path.parents or not path.is_file():
        raise HTTPException(status_code=404, detail="Not found")

    ext = filename.rsplit(".", 1)[-1]
    return FileResponse(path, media_type=_CHAT_MEDIA_EXT_TO_MIME.get(ext, "application/octet-stream"))


@app.post("/api/chatty/chat/attachments", dependencies=[Depends(require_api_key)], status_code=201)
async def upload_chat_attachment(file: UploadFile = File(...)):
    content_type = (file.content_type or "").split(";")[0].strip().lower()
    if content_type in MEDIA_IMAGE_FORMATS:
        kind, ext = "image", MEDIA_IMAGE_FORMATS[content_type]
    elif content_type in MEDIA_VIDEO_FORMATS:
        kind, ext = "video", MEDIA_VIDEO_FORMATS[content_type]
    else:
        raise HTTPException(status_code=415, detail=f"Unsupported content type: {content_type or '(none)'}")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(data) > CHAT_ATTACHMENT_MAX_BYTES:
        raise HTTPException(status_code=413, detail=f"Attachment exceeds {CHAT_ATTACHMENT_MAX_BYTES:,} byte limit")

    filename = f"{uuid.uuid4()}.{ext}"
    await asyncio.to_thread((_chat_uploads_dir() / filename).write_bytes, data)

    return {"id": filename, "kind": kind, "url": f"/api/chatty/chat-media/{filename}"}


async def _build_attachment_context(media_bytes: bytes, ext: str, kind: str, caption: Optional[str]) -> str:
    """Describe an image/video attached to a live chat message, for use as
    ephemeral LLM context (WebChatAgent.stream's attachment_context). Reuses
    the same vision/STT helpers as the passive media-ingestion pipeline above,
    but skips that pipeline's final video-summarization pass (needed there for
    memory-log framing) since here the chat model synthesizes its own reply
    from the raw per-frame notes."""
    if kind == "image":
        jpeg_b64 = await asyncio.to_thread(_convert_image_to_jpeg_b64, media_bytes, ext)
        prompt = (
            "Describe this image in detail so you (an AI assistant) can discuss it with the "
            "user: setting, people, objects, text, and anything notable."
        )
        if caption:
            prompt += f"\n\nThe user's message accompanying it: {caption}"
        return await _describe_image(jpeg_b64, prompt)

    keyframes, audio_bytes = await asyncio.to_thread(_extract_video_parts, media_bytes, ext)
    frame_descriptions = []
    for i, frame_bytes in enumerate(keyframes):
        frame_b64 = base64.b64encode(frame_bytes).decode("ascii")
        prompt = (
            f"This is frame {i + 1} of {len(keyframes)} sampled from a video the user just "
            "attached to a chat message, in chronological order. Describe what's happening "
            "in one or two sentences."
        )
        try:
            frame_descriptions.append((await _describe_image(frame_b64, prompt)).strip())
        except Exception as e:
            logger.error(f"Vision analysis failed for chat video frame {i}: {e}")

    transcript = None
    if audio_bytes:
        try:
            result = await get_stt_provider().transcribe(audio_bytes, filename_hint="video_audio.m4a")
            transcript = (result.text or "").strip() or None
        except Exception as e:
            logger.error(f"STT failed for chat video audio: {e}")

    if not frame_descriptions and not transcript:
        return "(The video couldn't be analyzed - no usable frames or audio.)"

    parts = [f"Frame {i + 1}: {d}" for i, d in enumerate(frame_descriptions)]
    if transcript:
        parts.append(f"Audio transcript: {transcript}")
    if caption:
        parts.append(f"User's message: {caption}")
    return "\n".join(parts)


async def _load_chat_attachment_context(
    attachment_id: str, caption: Optional[str],
) -> Tuple[Optional[str], Optional[Dict]]:
    """Load a previously-uploaded chat attachment (see upload_chat_attachment)
    and describe it. Returns (attachment_context_for_the_llm, metadata_for_history)."""
    if not _CHAT_MEDIA_FILENAME_RE.match(attachment_id):
        return "(The attachment reference was invalid.)", None

    path = _chat_uploads_dir() / attachment_id
    if not path.is_file():
        return "(The attachment could not be found - it may have expired.)", None

    ext = attachment_id.rsplit(".", 1)[-1]
    kind = "video" if ext in _CHAT_MEDIA_VIDEO_EXTS else "image"
    meta = {"kind": kind, "url": f"/api/chatty/chat-media/{attachment_id}"}

    try:
        media_bytes = await asyncio.to_thread(path.read_bytes)
        description = await _build_attachment_context(media_bytes, ext, kind, caption)
    except Exception as e:
        logger.error(f"Failed to analyze chat attachment {attachment_id}: {e}")
        description = f"(The user attached a {kind}, but it couldn't be analyzed.)"

    # Grafted onto the user's own message by WebChatAgent._build_messages
    # (attachment_context), not sent as a separate system note - live-tested
    # against this deployment's local model and found that a system-level
    # "here's what the image shows, don't say you can't see images" note
    # reliably got overridden by the model's trained "I can't view images"
    # refusal once real memory context padded the conversation. Folding the
    # description into what the user is literally saying doesn't trigger that.
    return f"[Attached {kind} - here's what it shows: {description}]", meta


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
    """Drain queued feature requests one at a time through the Pi agent.

    Each request runs inside an isolated git worktree via
    src.managers.self_upgrade_manager.run_feature_request - the same
    pattern the heartbeat's self-upgrade pipeline uses - so Pi can never
    edit the live checkout mid-turn, and never restarts the very server
    it's running under as its own verification step (that used to kill the
    `pi` subprocess before it could report back; see
    skills/pi_agent/runner.py's PM2_SELF_APP_NAME handling for the narrower
    fix covering requests made before this existed).
    """
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
                await run_feature_request(req.id, req.prompt, feature_requests_manager)
            except Exception as e:
                feature_requests_manager.update(req.id, status="error", summary=str(e))
            finally:
                pi_lock.release("web_queue")

            # Safety net: if run_feature_request ended without setting a terminal status
            latest = feature_requests_manager.get(req.id)
            if latest and latest.status in ("running", "testing"):
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


# ── Video Production (OpenMontage AI video generation) ──────────────────────
from skills.video_production import video_manager as _video_mgr

# Import video_api via importlib to mirror the skill's own pattern
_video_api_path = PROJECT_ROOT / "skills" / "video_production" / "video_api.py"
_video_api_spec = importlib.util.spec_from_file_location("video_production_webapi", _video_api_path)
_video_api = importlib.util.module_from_spec(_video_api_spec)
_video_api_spec.loader.exec_module(_video_api)

_VALID_DURATIONS = [2, 4, 6, 8, 10, 15]
_VALID_RESOLUTIONS = ["480p", "720p", "1080p", "auto"]


class VideoJobCreate(BaseModel):
    prompt: str
    duration_seconds: int = 4
    resolution: str = "auto"


@app.get("/api/chatty/video-jobs", dependencies=[Depends(require_api_key)])
async def get_video_jobs(limit: int = Query(default=50, ge=1, le=200)):
    return _video_mgr.list_jobs(limit=limit)


@app.post("/api/chatty/video-jobs", dependencies=[Depends(require_api_key)], status_code=201)
async def create_video_job(body: VideoJobCreate, background_tasks: BackgroundTasks):
    prompt = body.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt is required")
    if body.duration_seconds not in _VALID_DURATIONS:
        raise HTTPException(status_code=400, detail=f"duration_seconds must be one of: {_VALID_DURATIONS}")
    if body.resolution not in _VALID_RESOLUTIONS:
        raise HTTPException(status_code=400, detail=f"resolution must be one of: {_VALID_RESOLUTIONS}")

    # Create the job record
    job = _video_mgr.create_job(
        prompt=prompt,
        duration_seconds=body.duration_seconds,
        resolution=body.resolution,
    )

    # Kick off actual video generation in the background
    async def _run_generation(job_id: str):
        _video_mgr.update_job(job_id, status="generating")
        try:
            result = await _video_api.generate_video(
                prompt,
                duration_seconds=body.duration_seconds,
                resolution=body.resolution,
            )
            if result.get("success"):
                _video_mgr.update_job(job_id, status="completed", url=result.get("url"))
            else:
                _video_mgr.update_job(job_id, status="failed", error=result.get("error", "unknown error"))
        except Exception as e:
            _video_mgr.update_job(job_id, status="failed", error=str(e))

    background_tasks.add_task(_run_generation, job["id"])
    return job


@app.get("/api/chatty/video-jobs/{job_id}", dependencies=[Depends(require_api_key)])
async def get_video_job(job_id: str):
    job = _video_mgr.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.delete("/api/chatty/video-jobs/{job_id}", dependencies=[Depends(require_api_key)])
async def delete_video_job(job_id: str):
    ok = _video_mgr.delete_job(job_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"deleted": True}


# ── Trending Suggestions (GitHub-trending ideas curated by the heartbeat; ────
# never implemented automatically - the user picks from the menu here) ───────
@app.get("/api/chatty/trending-suggestions", dependencies=[Depends(require_api_key)])
async def get_trending_suggestions():
    return [s.to_dict() for s in trending_suggestions_manager.list()]


@app.post("/api/chatty/trending-suggestions/scan", dependencies=[Depends(require_api_key)])
async def scan_trending_suggestions():
    """Manual "scan now" trigger - bypasses the heartbeat's interval gate."""
    await run_trending_scan(skills_manager, trending_suggestions_manager)
    return [s.to_dict() for s in trending_suggestions_manager.list()]


@app.post("/api/chatty/trending-suggestions/{suggestion_id}/implement", dependencies=[Depends(require_api_key)])
async def implement_trending_suggestion(suggestion_id: str):
    suggestion = trending_suggestions_manager.get(suggestion_id)
    if suggestion is None:
        raise HTTPException(status_code=404, detail="Suggestion not found")
    if suggestion.status != "pending":
        raise HTTPException(status_code=409, detail=f"Suggestion is already {suggestion.status}")

    req = feature_requests_manager.create(suggestion.integration_prompt, source="github_trending")
    _ensure_pi_worker_running()
    updated = trending_suggestions_manager.update(suggestion_id, status="implemented", request_id=req.id)
    return updated.to_dict()


@app.post("/api/chatty/trending-suggestions/{suggestion_id}/dismiss", dependencies=[Depends(require_api_key)])
async def dismiss_trending_suggestion(suggestion_id: str):
    suggestion = trending_suggestions_manager.get(suggestion_id)
    if suggestion is None:
        raise HTTPException(status_code=404, detail="Suggestion not found")
    if suggestion.status != "pending":
        raise HTTPException(status_code=409, detail=f"Suggestion is already {suggestion.status}")

    updated = trending_suggestions_manager.update(suggestion_id, status="dismissed")
    return updated.to_dict()


@app.delete("/api/chatty/trending-suggestions/{suggestion_id}", dependencies=[Depends(require_api_key)])
async def delete_trending_suggestion(suggestion_id: str):
    if trending_suggestions_manager.get(suggestion_id) is None:
        raise HTTPException(status_code=404, detail="Suggestion not found")
    trending_suggestions_manager.delete(suggestion_id)
    return {"deleted": True}


# ── Webcam Sources & Discovery (SearXNG-curated suggestions the user reviews ──
# on the dashboard; approving one adds it to the source list) ────────────────
class WebcamSourceCreate(BaseModel):
    name: str
    url: str
    kind: str = "webpage"
    location: str = ""
    enabled: bool = True


class WebcamSourceUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    kind: Optional[str] = None
    location: Optional[str] = None
    enabled: Optional[bool] = None


@app.get("/api/chatty/webcam-sources", dependencies=[Depends(require_api_key)])
async def get_webcam_sources():
    return [s.to_dict() for s in webcam_sources_manager.list()]


@app.post("/api/chatty/webcam-sources", dependencies=[Depends(require_api_key)], status_code=201)
async def create_webcam_source(body: WebcamSourceCreate):
    name = body.name.strip()
    url = body.url.strip()
    if not name or not url:
        raise HTTPException(status_code=400, detail="name and url are required")
    if body.kind not in WEBCAM_KINDS:
        raise HTTPException(status_code=400, detail=f"kind must be one of: {', '.join(WEBCAM_KINDS)}")
    source = webcam_sources_manager.create(
        name=name, url=url, kind=body.kind, location=body.location.strip(),
        enabled=body.enabled, source="manual",
    )
    return source.to_dict()


@app.put("/api/chatty/webcam-sources/{source_id}", dependencies=[Depends(require_api_key)])
async def update_webcam_source(source_id: str, body: WebcamSourceUpdate):
    if webcam_sources_manager.get(source_id) is None:
        raise HTTPException(status_code=404, detail="Source not found")
    fields = body.model_dump(exclude_unset=True)
    if "kind" in fields and fields["kind"] not in WEBCAM_KINDS:
        raise HTTPException(status_code=400, detail=f"kind must be one of: {', '.join(WEBCAM_KINDS)}")
    updated = webcam_sources_manager.update(source_id, **fields)
    return updated.to_dict()


@app.delete("/api/chatty/webcam-sources/{source_id}", dependencies=[Depends(require_api_key)])
async def delete_webcam_source(source_id: str):
    ok = webcam_sources_manager.delete(source_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Source not found")
    return {"deleted": True}


@app.get("/api/chatty/webcam-suggestions", dependencies=[Depends(require_api_key)])
async def get_webcam_suggestions():
    return [s.to_dict() for s in webcam_suggestions_manager.list()]


@app.post("/api/chatty/webcam-suggestions/scan", dependencies=[Depends(require_api_key)])
async def scan_webcam_suggestions():
    """Manual "scan now" trigger - bypasses the heartbeat's interval gate."""
    await run_webcam_discovery_scan(webcam_sources_manager, webcam_suggestions_manager)
    return [s.to_dict() for s in webcam_suggestions_manager.list()]


@app.post("/api/chatty/webcam-suggestions/{suggestion_id}/approve", dependencies=[Depends(require_api_key)])
async def approve_webcam_suggestion(suggestion_id: str):
    suggestion = webcam_suggestions_manager.get(suggestion_id)
    if suggestion is None:
        raise HTTPException(status_code=404, detail="Suggestion not found")
    if suggestion.status != "pending":
        raise HTTPException(status_code=409, detail=f"Suggestion is already {suggestion.status}")

    new_source = webcam_sources_manager.create(
        name=suggestion.name, url=suggestion.url, kind=suggestion.kind,
        location=suggestion.location, enabled=True, source="suggestion",
        suggestion_id=suggestion.id,
    )
    updated = webcam_suggestions_manager.update(suggestion_id, status="approved", source_id=new_source.id)
    return updated.to_dict()


@app.post("/api/chatty/webcam-suggestions/{suggestion_id}/dismiss", dependencies=[Depends(require_api_key)])
async def dismiss_webcam_suggestion(suggestion_id: str):
    suggestion = webcam_suggestions_manager.get(suggestion_id)
    if suggestion is None:
        raise HTTPException(status_code=404, detail="Suggestion not found")
    if suggestion.status != "pending":
        raise HTTPException(status_code=409, detail=f"Suggestion is already {suggestion.status}")

    updated = webcam_suggestions_manager.update(suggestion_id, status="dismissed")
    return updated.to_dict()


@app.delete("/api/chatty/webcam-suggestions/{suggestion_id}", dependencies=[Depends(require_api_key)])
async def delete_webcam_suggestion(suggestion_id: str):
    if webcam_suggestions_manager.get(suggestion_id) is None:
        raise HTTPException(status_code=404, detail="Suggestion not found")
    webcam_suggestions_manager.delete(suggestion_id)
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


@app.get("/api/chatty/memory/search", dependencies=[Depends(require_api_key)])
async def search_memory(q: str = Query(min_length=1)):
    from src.core.memory_tools import MemoryTools

    memory_tools = MemoryTools(WEB_USER_ID)
    results = await memory_tools.search_memory_grep(q)
    return {"results": results}


@app.post("/api/chatty/memory/consolidate", dependencies=[Depends(require_api_key)])
async def consolidate_memory():
    from src.core.memory import MemoryManager
    from src.agents.staged_react_agent import StagedReACTAgent

    memory_manager = MemoryManager(WEB_USER_ID)
    agent = StagedReACTAgent(memory_manager, skills_manager)
    result = await memory_manager.consolidate_memories(agent)
    return {"result": result}


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
class SessionRename(BaseModel):
    title: str


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
            "title": s["title"],
        })
    return result


@app.get("/api/chatty/sessions/{session_id}", dependencies=[Depends(require_api_key)])
async def get_session_messages(session_id: int):
    """Return messages for a specific session."""
    from src.core.memory import ConversationHistoryManager
    mgr = ConversationHistoryManager(WEB_USER_ID)
    messages = await mgr.get_session(session_id)
    return messages


@app.put("/api/chatty/sessions/{session_id}", dependencies=[Depends(require_api_key)])
async def rename_session(session_id: int, body: SessionRename):
    """Set a custom title for a session (stored separately from its auto-computed summary)."""
    from src.core.memory import ConversationHistoryManager
    mgr = ConversationHistoryManager(WEB_USER_ID)
    sessions = await mgr.get_sessions()
    if not (0 <= session_id < len(sessions)):
        raise HTTPException(status_code=404, detail="Session not found")
    await mgr.set_session_title(sessions[session_id]["first_ts"], body.title)
    return {"id": session_id, "title": body.title}


@app.delete("/api/chatty/sessions/{session_id}", dependencies=[Depends(require_api_key)])
async def delete_session(session_id: int):
    """Delete a session."""
    from src.core.memory import ConversationHistoryManager
    mgr = ConversationHistoryManager(WEB_USER_ID)
    ok = await mgr.delete_session(session_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"deleted": True}


# ── WebSocket Chat ────────────────────────────────────────────────────────────
# Protocol (client -> server): {"type": "message", "text": ..., "attachment_id": ...}
#                               {"type": "stop"}
#                               {"type": "regenerate"}
#                               {"type": "edit_resend", "text": ...}
# `attachment_id` (optional, "message" only) references a file already
# uploaded via POST /api/chatty/chat/attachments.
# Protocol (server -> client): {"type": "session_loaded", ...}
#                               {"type": "chunk", "text": ...}
#                               {"type": "done"}
#                               {"type": "stopped"}
#                               {"type": "error", "text": ...}
# Proactive push (assistant mode, unprompted - see _push_assistant_response):
#                               {"type": "chunk", "content": ...}
#                               {"type": "done"}
_WS_DISCONNECT = object()  # queue sentinel: the websocket has disconnected


@app.websocket("/api/chatty/chat")
async def websocket_chat(websocket: WebSocket, api_key: str = Query(default=""), session_id: str = Query(default="")):
    if api_key != API_KEY:
        await websocket.close(code=4401)
        return

    await websocket.accept()

    # Register this connection so the audio pipeline can push a proactive
    # assistant response onto it (assistant mode, wake-word detection). Only
    # devices that send X-Device-Id on the WS handshake are reachable that way.
    device_id = websocket.headers.get("x-device-id") or None
    connection = _ChatConnection(websocket) if device_id else None
    if connection is not None:
        _active_chat_connections[device_id] = connection

    async def send_json(payload: dict) -> None:
        if connection is not None:
            await connection.send_json(payload)
        else:
            await websocket.send_text(json.dumps(payload))

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
    await send_json({
        "type": "session_loaded",
        "session_id": active_session_id,
        "message_count": len(agent._history) if active_session_id is not None else 0,
    })

    # A dedicated receiver task decouples "read the next frame" from "consume a
    # streaming response", so a control frame (e.g. "stop") can be observed while
    # a generation is in flight. Frames are handed off through a queue; a sentinel
    # marks disconnection so it can flow through the same queue as normal frames.
    queue: "asyncio.Queue" = asyncio.Queue()

    async def receiver():
        try:
            while True:
                raw = await websocket.receive_text()
                await queue.put(raw)
        except WebSocketDisconnect:
            pass
        except Exception as e:
            logger.error(f"WS receiver error for user {WEB_USER_ID}: {e}")
        finally:
            await queue.put(_WS_DISCONNECT)

    receiver_task = asyncio.create_task(receiver())
    stream_task: Optional[asyncio.Task] = None

    async def run_agent_stream(gen, holder: Dict[str, str]):
        """Forward chunks and accumulate full text. Never sends done/error/stopped itself."""
        async for chunk in gen:
            holder["text"] += chunk
            try:
                await send_json({"type": "chunk", "text": chunk})
            except Exception:
                # Client socket may already be dead; keep generating so the full
                # response still gets persisted even if the client never sees it.
                pass

    async def finalize_stream(
        mode: str, user_text: Optional[str], task: asyncio.Task, holder: Dict[str, str],
        attachment_meta: Optional[Dict] = None,
    ):
        """Await a finished/cancelled/errored stream task, persist, and send exactly
        one control frame. This is the single place that does either, to avoid
        concurrent send_text calls on the same socket."""
        status = "done"
        error_text = None
        try:
            await task
        except asyncio.CancelledError:
            status = "stopped"
        except Exception as e:
            status = "error"
            error_text = str(e)

        response_text = holder["text"]
        try:
            if mode == "message":
                await history_mgr.append(user_text, response_text, attachment=attachment_meta)
            elif mode == "regenerate":
                await history_mgr.replace_last_assistant(response_text)
            elif mode == "edit_resend":
                await history_mgr.replace_last_pair(user_text, response_text)
        except Exception as e:
            logger.error(f"Failed to persist chat history for user {WEB_USER_ID}: {e}")

        try:
            if status == "error":
                await send_json({"type": "error", "text": error_text})
            elif status == "stopped":
                await send_json({"type": "stopped"})
            else:
                await send_json({"type": "done"})
        except Exception:
            pass

    def start_stream(mode: str, text: Optional[str], attachment_context: Optional[str] = None):
        holder = {"text": ""}
        if mode == "message":
            gen = agent.stream(text, attachment_context=attachment_context)
        elif mode == "regenerate":
            gen = agent.regenerate()
        elif mode == "edit_resend":
            gen = agent.edit_last_user_message(text)
        else:
            return None, None
        return asyncio.create_task(run_agent_stream(gen, holder)), holder

    try:
        while True:
            raw = await queue.get()
            if raw is _WS_DISCONNECT:
                break

            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                with contextlib.suppress(Exception):
                    await send_json({"type": "error", "text": "Invalid JSON"})
                continue

            msg_type = data.get("type")
            stream_mode: Optional[str] = None
            stream_user_text: Optional[str] = None
            attachment_context: Optional[str] = None
            attachment_meta: Optional[Dict] = None

            if msg_type == "message":
                text = data.get("text", "").strip()
                attachment_id = (data.get("attachment_id") or "").strip()
                if not text and not attachment_id:
                    continue
                if attachment_id:
                    attachment_context, attachment_meta = await _load_chat_attachment_context(
                        attachment_id, text or None
                    )
                stream_mode, stream_user_text = "message", text or "(sent an attachment)"
            elif msg_type == "regenerate":
                stream_mode, stream_user_text = "regenerate", None
            elif msg_type == "edit_resend":
                text = data.get("text", "").strip()
                if not text:
                    continue
                stream_mode, stream_user_text = "edit_resend", text
            else:
                # "stop" (or anything unrecognized) while idle: nothing to stop, ignore.
                continue

            stream_task, stream_holder = start_stream(stream_mode, stream_user_text, attachment_context)
            if stream_task is None:
                continue

            # Keep consuming frames while this generation is in flight, so a
            # "stop" (or disconnect) can be observed without blocking on the stream.
            while stream_task is not None:
                getter = asyncio.create_task(queue.get())
                done, _pending = await asyncio.wait(
                    {stream_task, getter}, return_when=asyncio.FIRST_COMPLETED
                )

                incoming = None
                if getter in done:
                    incoming = getter.result()
                else:
                    getter.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await getter

                if stream_task in done:
                    # Finalize the completed stream before dispatching whatever
                    # frame just arrived, so a "stop" racing natural completion
                    # becomes a no-op against an idle connection instead of a
                    # lost or misapplied frame.
                    await finalize_stream(stream_mode, stream_user_text, stream_task, stream_holder, attachment_meta)
                    stream_task = None
                    if incoming is not None:
                        await queue.put(incoming)
                    break

                if incoming is _WS_DISCONNECT:
                    stream_task.cancel()
                    await finalize_stream(stream_mode, stream_user_text, stream_task, stream_holder, attachment_meta)
                    stream_task = None
                    await queue.put(_WS_DISCONNECT)
                    break
                elif incoming is not None:
                    try:
                        incoming_data = json.loads(incoming)
                    except json.JSONDecodeError:
                        incoming_data = {}
                    if incoming_data.get("type") == "stop":
                        stream_task.cancel()
                        await finalize_stream(stream_mode, stream_user_text, stream_task, stream_holder, attachment_meta)
                        stream_task = None
                        break
                    # Any other frame type while busy is ignored (not requeued —
                    # requeuing here would busy-loop against the still-running stream).

    except WebSocketDisconnect:
        pass
    finally:
        if device_id and _active_chat_connections.get(device_id) is connection:
            del _active_chat_connections[device_id]
        receiver_task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await receiver_task
        if stream_task is not None and not stream_task.done():
            stream_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await stream_task


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("chatty_web_server:app", host="0.0.0.0", port=PORT, reload=False)
