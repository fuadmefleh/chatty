"""In-memory registry for on-demand insight scans.

A scan is a background job so the HTTP request can return immediately and the
dashboard can show per-topic progress while the pipeline runs.

Deliberately in-memory: jobs live in the chatty-web-server process and die
with it. A scan interrupted by a restart is lost, and the frontend treats a
404 on poll as "job vanished - refetch the feed and stop polling" rather than
an error, since the insight may well have been written before the restart.
Losing one costs the user a re-click, not data - the insight itself is
already on disk by the time the job goes terminal.

A measured single-topic news scan takes ~90s end to end (SearXNG aggregation
dominates, not the LLM call), which is why this is a background job rather
than a blocking request.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import uuid

# Per-user retention. Bounds memory without a TTL sweeper - a user has to run
# 20 scans before the oldest becomes unpollable.
MAX_JOBS_PER_USER = 20

# Terminal statuses - the frontend stops polling on these.
TERMINAL_STATUSES = ("done", "failed")


@dataclass
class ScanTarget:
    """One topic within a job. `state` mirrors world_watch.SCAN_STATES once run."""
    topic: str
    kind: str
    state: str = "pending"
    insight_id: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "topic": self.topic,
            "kind": self.kind,
            "state": self.state,
            "insight_id": self.insight_id,
            "error": self.error,
        }


@dataclass
class ScanJob:
    id: str
    user_id: str
    mode: str
    created_at: str
    targets: List[ScanTarget] = field(default_factory=list)
    status: str = "pending"
    finished_at: Optional[str] = None
    error: Optional[str] = None

    @property
    def is_active(self) -> bool:
        return self.status not in TERMINAL_STATUSES

    def start(self) -> None:
        self.status = "running"

    def finish(self) -> None:
        """Complete the job.

        Always "done", even if every target failed. A dead source is a normal
        outcome recorded on the target; only the run machinery itself failing
        is a failed job. Callers read per-target state for the detail.
        """
        self.status = "done"
        self.finished_at = datetime.now().isoformat()

    def fail(self, error: str) -> None:
        self.status = "failed"
        self.error = error
        self.finished_at = datetime.now().isoformat()

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "mode": self.mode,
            "status": self.status,
            "created_at": self.created_at,
            "finished_at": self.finished_at,
            "error": self.error,
            "targets": [t.to_dict() for t in self.targets],
        }


class ScanJobRegistry:
    """Tracks scan jobs per user, newest last."""

    def __init__(self):
        self._by_user: Dict[str, List[ScanJob]] = {}

    def create(self, user_id: str, mode: str, targets: List[Tuple[str, str]]) -> ScanJob:
        """Register a pending job. `targets` is a list of (topic, kind)."""
        job = ScanJob(
            id=str(uuid.uuid4()),
            user_id=user_id,
            mode=mode,
            created_at=datetime.now().isoformat(),
            targets=[ScanTarget(topic=t, kind=k) for t, k in targets],
        )

        jobs = self._by_user.setdefault(user_id, [])
        jobs.append(job)
        # Eviction is per-user so a busy user can't push out someone else's.
        del jobs[:-MAX_JOBS_PER_USER]

        return job

    def get(self, job_id: str) -> Optional[ScanJob]:
        for jobs in self._by_user.values():
            for job in jobs:
                if job.id == job_id:
                    return job
        return None

    def active_for_user(self, user_id: str) -> Optional[ScanJob]:
        """The user's in-flight job, if any.

        Callers use this to reject a second concurrent scan, so an impatient
        double-click can't fire duplicate LLM calls.
        """
        for job in self._by_user.get(user_id, []):
            if job.is_active:
                return job
        return None
