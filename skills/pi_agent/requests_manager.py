"""Feature Requests Manager - stores web-submitted feature requests routed
to the Pi coding agent, along with their live status/log.

Mirrors skills/notes/notes_manager.py's whole-file load/save pattern.
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import uuid

MAX_LOG_LINES = 200


class FeatureRequest:
    """Represents a single feature request routed to the Pi coding agent."""

    def __init__(
        self,
        request_id: str,
        prompt: str,
        status: str,
        created_at: str,
        updated_at: str,
        files_changed: Optional[List[str]] = None,
        log: Optional[List[str]] = None,
        summary: str = "",
    ):
        self.id = request_id
        self.prompt = prompt
        self.status = status  # queued | running | completed | error
        self.created_at = created_at
        self.updated_at = updated_at
        self.files_changed = files_changed or []
        self.log = log or []
        self.summary = summary

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "prompt": self.prompt,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "files_changed": self.files_changed,
            "log": self.log,
            "summary": self.summary,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "FeatureRequest":
        return cls(
            request_id=data["id"],
            prompt=data["prompt"],
            status=data["status"],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            files_changed=data.get("files_changed", []),
            log=data.get("log", []),
            summary=data.get("summary", ""),
        )


class FeatureRequestsManager:
    """Manages feature requests with persistent JSON storage."""

    def __init__(self, data_dir: str = "/home/edgeworks-server/chatty/data/feature_requests"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._file = self.data_dir / "requests.json"

    def _load(self) -> List[FeatureRequest]:
        if not self._file.exists():
            return []
        try:
            with open(self._file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return [FeatureRequest.from_dict(r) for r in data]
        except Exception as e:
            print(f"Error loading feature requests: {e}")
            return []

    def _save(self, requests: List[FeatureRequest]) -> None:
        try:
            with open(self._file, "w", encoding="utf-8") as f:
                json.dump([r.to_dict() for r in requests], f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving feature requests: {e}")
            raise

    def create(self, prompt: str) -> FeatureRequest:
        requests = self._load()
        now = datetime.now().isoformat()
        new_request = FeatureRequest(
            request_id=str(uuid.uuid4()),
            prompt=prompt,
            status="queued",
            created_at=now,
            updated_at=now,
        )
        requests.append(new_request)
        self._save(requests)
        return new_request

    def list(self) -> List[FeatureRequest]:
        """All requests, newest first."""
        requests = self._load()
        return sorted(requests, key=lambda r: r.created_at, reverse=True)

    def get(self, request_id: str) -> Optional[FeatureRequest]:
        for r in self._load():
            if r.id == request_id:
                return r
        return None

    def next_queued(self) -> Optional[FeatureRequest]:
        """Oldest request still in the 'queued' state, if any."""
        queued = [r for r in self._load() if r.status == "queued"]
        return sorted(queued, key=lambda r: r.created_at)[0] if queued else None

    def update(self, request_id: str, **fields) -> Optional[FeatureRequest]:
        requests = self._load()
        for r in requests:
            if r.id == request_id:
                for key, value in fields.items():
                    setattr(r, key, value)
                r.updated_at = datetime.now().isoformat()
                self._save(requests)
                return r
        return None

    def append_log(self, request_id: str, line: str) -> None:
        requests = self._load()
        for r in requests:
            if r.id == request_id:
                r.log.append(line)
                if len(r.log) > MAX_LOG_LINES:
                    r.log = r.log[-MAX_LOG_LINES:]
                r.updated_at = datetime.now().isoformat()
                self._save(requests)
                return

    def add_file_changed(self, request_id: str, filepath: str) -> None:
        requests = self._load()
        for r in requests:
            if r.id == request_id:
                if filepath not in r.files_changed:
                    r.files_changed.append(filepath)
                r.updated_at = datetime.now().isoformat()
                self._save(requests)
                return

    def delete(self, request_id: str) -> bool:
        requests = self._load()
        original_count = len(requests)
        requests = [r for r in requests if r.id != request_id]
        if len(requests) < original_count:
            self._save(requests)
            return True
        return False
