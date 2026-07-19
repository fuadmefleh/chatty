"""UI Taste Auditor fix-job state — persistent JSON-backed store tracking the
apply-fixes workflow's progress so the frontend can poll for live status
(current file, how many done of how many) instead of blocking on one request
with no feedback. See src/web/routers/taste_audit.py.

Unlike wiki reorganization (src/managers/wiki_reorganize_manager.py) this
isn't scoped per-user: the taste audit scans the one shared frontend source
tree, so there's a single global job. A second /fix request while one is
already running just returns the in-flight state instead of starting another.
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from src.core.file_lock import locked

_STATE_PATH = Path(__file__).parent.parent.parent / "data" / "taste_audit_fix" / "state.json"

_IDLE_STATE: Dict[str, Any] = {
    "status": "idle",  # idle | running | done | error
    "total": 0,
    "completed": 0,
    "current_file": None,
    "applied": [],
    "errors": [],
    "summary": None,
    "updated_at": None,
}


def _load() -> dict:
    if not _STATE_PATH.exists():
        return dict(_IDLE_STATE)
    try:
        with open(_STATE_PATH) as f:
            data = json.load(f)
        if isinstance(data, dict):
            return {**_IDLE_STATE, **data}
    except (json.JSONDecodeError, OSError):
        pass
    return dict(_IDLE_STATE)


def _save(state: dict) -> dict:
    _STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    state = {**state, "updated_at": datetime.now().isoformat()}
    with locked(_STATE_PATH):
        with open(_STATE_PATH, "w") as f:
            json.dump(state, f, indent=2, default=str)
    return state


def get_state() -> dict:
    return _load()


def start(total_files: int) -> dict:
    return _save({
        **_IDLE_STATE,
        "status": "running",
        "total": total_files,
    })


def set_current_file(file_path: str) -> dict:
    current = _load()
    return _save({**current, "current_file": file_path})


def record_file_result(file_path: str, applied: List[Dict], errors: List[Dict]) -> dict:
    current = _load()
    return _save({
        **current,
        "completed": current["completed"] + 1,
        "current_file": file_path,
        "applied": current["applied"] + applied,
        "errors": current["errors"] + errors,
    })


def finish(summary: str) -> dict:
    current = _load()
    return _save({**current, "status": "done", "current_file": None, "summary": summary})


def fail(error: str) -> dict:
    current = _load()
    return _save({**current, "status": "error", "current_file": None, "summary": error})
