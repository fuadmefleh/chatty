"""Video production jobs manager — persistent JSON-backed store for the
webapp's video generation history.

Jobs track the lifecycle: submitted -> generating -> completed/failed.
The actual OpenMontage API call is triggered by the web server endpoint
(see ``chatty_web_server.py``) which calls ``video_api.generate_video()``;
this manager only tracks the job records.
"""
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from src.core.file_lock import locked

# Where job records live
_JOBS_DIR = Path(__file__).parent.parent.parent / "data" / "video_jobs"
_JOBS_FILE = _JOBS_DIR / "jobs.json"


def _ensure_dir() -> None:
    _JOBS_DIR.mkdir(parents=True, exist_ok=True)


def _load_jobs() -> List[dict]:
    _ensure_dir()
    if not _JOBS_FILE.exists():
        return []
    try:
        with open(_JOBS_FILE) as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        return []
    except (json.JSONDecodeError, OSError):
        return []


def _save_jobs(jobs: List[dict]) -> None:
    _ensure_dir()
    with locked(_JOBS_FILE):
        with open(_JOBS_FILE, "w") as f:
            json.dump(jobs, f, indent=2, default=str)


def create_job(prompt: str, duration_seconds: int = 4, resolution: str = "auto") -> dict:
    """Create a new video generation job record (status: submitted)."""
    job: Dict[str, Optional[str]] = {
        "id": uuid.uuid4().hex[:12],
        "prompt": prompt,
        "duration_seconds": duration_seconds,
        "resolution": resolution,
        "status": "submitted",
        "url": None,
        "error": None,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }
    jobs = _load_jobs()
    jobs.insert(0, job)
    _save_jobs(jobs)
    return dict(job)


def get_job(job_id: str) -> Optional[dict]:
    """Retrieve a single job by ID."""
    jobs = _load_jobs()
    for job in jobs:
        if job["id"] == job_id:
            return dict(job)
    return None


def update_job(job_id: str, **kwargs) -> Optional[dict]:
    """Update fields on an existing job. Returns updated job or None if not found."""
    jobs = _load_jobs()
    for idx, job in enumerate(jobs):
        if job["id"] == job_id:
            job.update(kwargs)
            job["updated_at"] = datetime.now().isoformat()
            jobs[idx] = job
            _save_jobs(jobs)
            return dict(job)
    return None


def delete_job(job_id: str) -> bool:
    """Delete a job record. Returns True if deleted, False if not found."""
    jobs = _load_jobs()
    new_jobs = [j for j in jobs if j["id"] != job_id]
    if len(new_jobs) == len(jobs):
        return False
    _save_jobs(new_jobs)
    return True


def list_jobs(limit: int = 50) -> List[dict]:
    """List all jobs, most recent first (up to *limit*)."""
    jobs = _load_jobs()
    return jobs[:limit]



