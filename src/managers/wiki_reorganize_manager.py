"""Wiki reorganization job state — persistent JSON-backed store tracking the
propose/apply workflow's progress so it can run in the background.

Both propose_reorganization() and apply_reorganization() (src/core/memory.py)
are single, potentially slow LLM calls with no natural progress callback -
the web server kicks them off via FastAPI BackgroundTasks (see
src/web/routers/memory_wiki.py) and records state here so a client can
disconnect and poll back in later rather than blocking on the request.

One job per user (not a list): a second propose/apply request while one is
already running just returns the in-flight state instead of starting another.
`target_pages` always holds the full latest proposal - applying a subset of
it doesn't discard the rest, so the user can come back and apply the
remaining pages later. `applied_keys` accumulates "type/slug" for pages
successfully applied so far, reset only when a fresh proposal is generated.
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from src.core.file_lock import locked

_STATE_DIR = Path(__file__).parent.parent.parent / "data" / "wiki_reorganize"

_IDLE_STATE = {
    "status": "idle",
    "target_pages": None,
    "applied_keys": [],
    "error": None,
    "apply_result": None,
    "updated_at": None,
}


def _state_path(user_id: str) -> Path:
    return _STATE_DIR / f"{user_id}.json"


def _load(user_id: str) -> dict:
    path = _state_path(user_id)
    if not path.exists():
        return dict(_IDLE_STATE)
    try:
        with open(path) as f:
            data = json.load(f)
        if isinstance(data, dict):
            return {**_IDLE_STATE, **data}
    except (json.JSONDecodeError, OSError):
        pass
    return dict(_IDLE_STATE)


def _save(user_id: str, state: dict) -> dict:
    _STATE_DIR.mkdir(parents=True, exist_ok=True)
    path = _state_path(user_id)
    state = {**state, "updated_at": datetime.now().isoformat()}
    with locked(path):
        with open(path, "w") as f:
            json.dump(state, f, indent=2, default=str)
    return state


def get_state(user_id: str) -> dict:
    return _load(user_id)


def start_proposing(user_id: str) -> dict:
    return _save(user_id, {
        "status": "proposing", "target_pages": None, "applied_keys": [],
        "error": None, "apply_result": None,
    })


def set_proposed(user_id: str, target_pages: List[Dict]) -> dict:
    return _save(user_id, {
        "status": "proposed", "target_pages": target_pages, "applied_keys": [],
        "error": None, "apply_result": None,
    })


def set_propose_error(user_id: str, error: str) -> dict:
    return _save(user_id, {
        "status": "propose_error", "target_pages": None, "applied_keys": [],
        "error": error, "apply_result": None,
    })


def start_applying(user_id: str) -> dict:
    current = _load(user_id)
    return _save(user_id, {**current, "status": "applying", "error": None, "apply_result": None})


def set_applied(user_id: str, applied_keys: List[str], result: str) -> dict:
    current = _load(user_id)
    merged_keys = sorted(set(current.get("applied_keys") or []) | set(applied_keys))
    return _save(user_id, {
        **current, "status": "applied", "applied_keys": merged_keys,
        "error": None, "apply_result": result,
    })


def set_apply_error(user_id: str, error: str) -> dict:
    current = _load(user_id)
    return _save(user_id, {**current, "status": "apply_error", "error": error, "apply_result": None})
