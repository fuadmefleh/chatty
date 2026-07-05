"""Simple cross-process file locking for JSON-file-backed managers.

TranscriptionsManager/SpeakerManager do read-modify-write on whole JSON
files with no locking. That's fine for a single writer, but this feature
adds concurrent writers touching the same per-user files (live audio
ingestion, the speaker-labeling endpoint's retroactive rescan, the backfill
script, and the existing heartbeat archive step) - a plain flock keeps those
from clobbering each other.
"""
import fcntl
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def locked(path: Path):
    """Hold an exclusive lock on a sidecar `<path>.lock` file for the
    duration of the `with` block. Blocks until the lock is available."""
    lock_path = path.with_suffix(path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_path, "w") as lock_file:
        fcntl.flock(lock_file, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file, fcntl.LOCK_UN)
