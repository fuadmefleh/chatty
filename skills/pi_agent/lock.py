"""Cross-process lock guarding the Pi coding agent.

The web dashboard's feature-request queue (chatty_web_server.py) and the
heartbeat's self-upgrade pipeline (src/managers/self_upgrade_manager.py) run
in two separate OS processes (chatty-web-server vs chatty-bot), so
runner.py's in-memory `is_running()` check can't see across them. Both must
acquire this file-based lock before invoking `pi`, so they never run it
concurrently against the same repo.

Not rigorously race-free (check-then-write, not atomic) - acceptable for a
single personal server with at most two callers, not a multi-tenant system.
"""
import json
import os
import time
from typing import Optional

from src.core import config

LOCK_FILE = config.BASE_DIR / "data" / "pi_agent.lock"

# A lock older than this is assumed to belong to a crashed/killed process
# rather than a genuinely long-running one, and can be reclaimed.
STALE_SECONDS = 30 * 60


def _read() -> Optional[dict]:
    if not LOCK_FILE.exists():
        return None
    try:
        return json.loads(LOCK_FILE.read_text())
    except Exception:
        return None


def is_locked() -> bool:
    data = _read()
    if data is None:
        return False
    return (time.time() - data.get("acquired_at", 0)) < STALE_SECONDS


def acquire(owner: str) -> bool:
    """Try to acquire the lock for `owner`. Returns True if acquired."""
    if is_locked():
        return False
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    LOCK_FILE.write_text(json.dumps({
        "owner": owner,
        "pid": os.getpid(),
        "acquired_at": time.time(),
    }))
    return True


def release(owner: str) -> None:
    """Release the lock, but only if still held by `owner` (avoids a stale
    caller clobbering someone else's lock acquired after a reclaim)."""
    data = _read()
    if data is not None and data.get("owner") != owner:
        return
    try:
        LOCK_FILE.unlink(missing_ok=True)
    except Exception:
        pass
