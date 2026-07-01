"""Queue manager for VS Code bridge requests.

Manages a JSON file queue that both the Chatty bot and VS Code extension
read/write to coordinate code change requests.
"""
import json
import uuid
import fcntl
from datetime import datetime
from pathlib import Path
from typing import List, Optional


QUEUE_FILE = Path(__file__).parent.parent.parent / "data" / "vscode_requests.json"


class VSCodeRequestQueue:
    """File-based queue for code change requests between Chatty and VS Code."""

    def __init__(self, queue_file: Path = QUEUE_FILE):
        self.queue_file = queue_file
        self._ensure_file()

    def _ensure_file(self):
        self.queue_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.queue_file.exists():
            self._write_queue({"requests": []})

    def _read_queue(self) -> dict:
        with open(self.queue_file, 'r') as f:
            fcntl.flock(f, fcntl.LOCK_SH)
            try:
                return json.load(f)
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)

    def _write_queue(self, data: dict):
        with open(self.queue_file, 'w') as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                json.dump(data, f, indent=2)
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)

    def add_request(self, message: str, user_id: str) -> dict:
        """Add a new code change request to the queue."""
        queue = self._read_queue()
        request = {
            "id": str(uuid.uuid4()),
            "message": message,
            "user_id": user_id,
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "result": None,
            "updates": [],
            "last_update_seen": 0
        }
        queue["requests"].append(request)
        self._write_queue(queue)
        return request

    def get_requests(self, status: Optional[str] = None, limit: int = 50) -> List[dict]:
        """Get requests, optionally filtered by status."""
        queue = self._read_queue()
        requests = queue["requests"]
        if status:
            requests = [r for r in requests if r["status"] == status]
        return requests[-limit:]

    def get_request(self, request_id: str) -> Optional[dict]:
        """Get a single request by ID."""
        queue = self._read_queue()
        for req in queue["requests"]:
            if req["id"] == request_id:
                return req
        return None

    def update_request(self, request_id: str, status: str, result: Optional[str] = None) -> Optional[dict]:
        """Update a request's status and optional result."""
        queue = self._read_queue()
        for req in queue["requests"]:
            if req["id"] == request_id:
                req["status"] = status
                req["updated_at"] = datetime.now().isoformat()
                if result is not None:
                    req["result"] = result
                # Ensure updates field exists for older requests
                if "updates" not in req:
                    req["updates"] = []
                    req["last_update_seen"] = 0
                self._write_queue(queue)
                return req
        return None

    def add_update(self, request_id: str, update_type: str, content: str) -> Optional[dict]:
        """Add a progress update to a request."""
        queue = self._read_queue()
        for req in queue["requests"]:
            if req["id"] == request_id:
                if "updates" not in req:
                    req["updates"] = []
                    req["last_update_seen"] = 0
                req["updates"].append({
                    "type": update_type,
                    "content": content,
                    "timestamp": datetime.now().isoformat()
                })
                req["updated_at"] = datetime.now().isoformat()
                self._write_queue(queue)
                return req
        return None

    def get_unseen_updates(self, request_id: str) -> tuple:
        """Get updates not yet seen and mark them seen. Returns (updates, request)."""
        queue = self._read_queue()
        for req in queue["requests"]:
            if req["id"] == request_id:
                if "updates" not in req:
                    return [], req
                last_seen = req.get("last_update_seen", 0)
                unseen = req["updates"][last_seen:]
                req["last_update_seen"] = len(req["updates"])
                self._write_queue(queue)
                return unseen, req
        return [], None

    def get_active_requests(self) -> List[dict]:
        """Get requests that are pending or in_progress."""
        queue = self._read_queue()
        return [r for r in queue["requests"] if r["status"] in ("pending", "in_progress")]

    def delete_request(self, request_id: str) -> bool:
        """Remove a request from the queue."""
        queue = self._read_queue()
        original_len = len(queue["requests"])
        queue["requests"] = [r for r in queue["requests"] if r["id"] != request_id]
        if len(queue["requests"]) < original_len:
            self._write_queue(queue)
            return True
        return False

    def get_pending_count(self) -> int:
        """Get count of pending requests."""
        return len(self.get_requests(status="pending"))
