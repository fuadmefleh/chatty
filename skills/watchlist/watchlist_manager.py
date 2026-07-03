"""Watchlist Manager - handles persistent storage of user-defined watch topics.

Watch topics are picked up by HeartbeatManager._process_world_watch(), which
periodically checks each topic's source (news search, stock price, GitHub
activity - see src/managers/watch_sources.py) and surfaces notable updates.
"""
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

# Cap on how many dedup markers we remember per topic, to bound file size.
MAX_SEEN_URLS = 200

# Valid values for WatchTopic.kind - see src/managers/watch_sources.py for
# what each one checks.
WATCH_KINDS = ("news", "stock", "github")


class WatchTopic:
    """Represents a single watched topic."""

    def __init__(
        self,
        topic_id: str,
        topic: str,
        user_id: str,
        created_at: str,
        kind: str = "news",
        last_run_at: Optional[str] = None,
        seen_urls: Optional[List[str]] = None,
    ):
        self.id = topic_id
        self.topic = topic
        self.user_id = user_id
        self.created_at = created_at
        self.kind = kind if kind in WATCH_KINDS else "news"
        self.last_run_at = last_run_at
        self.seen_urls = seen_urls or []

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "topic": self.topic,
            "user_id": self.user_id,
            "created_at": self.created_at,
            "kind": self.kind,
            "last_run_at": self.last_run_at,
            "seen_urls": self.seen_urls,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "WatchTopic":
        return cls(
            topic_id=data["id"],
            topic=data["topic"],
            user_id=data["user_id"],
            created_at=data["created_at"],
            kind=data.get("kind", "news"),
            last_run_at=data.get("last_run_at"),
            seen_urls=data.get("seen_urls", []),
        )


class WatchlistManager:
    """Manages per-user watch topics with persistent JSON storage."""

    def __init__(self, data_dir: Optional[str] = None):
        if data_dir is None:
            from src.core import config
            data_dir = str(config.BASE_DIR / "data" / "watchlist")
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def _get_user_file(self, user_id: str) -> Path:
        return self.data_dir / f"{user_id}.json"

    def _load_topics(self, user_id: str) -> List[WatchTopic]:
        file_path = self._get_user_file(user_id)

        if not file_path.exists():
            return []

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return [WatchTopic.from_dict(t) for t in data]
        except Exception as e:
            print(f"Error loading watchlist for user {user_id}: {e}")
            return []

    def _save_topics(self, user_id: str, topics: List[WatchTopic]) -> None:
        file_path = self._get_user_file(user_id)

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump([t.to_dict() for t in topics], f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving watchlist for user {user_id}: {e}")
            raise

    def add_topic(self, user_id: str, topic: str, kind: str = "news") -> WatchTopic:
        """Add a new topic to watch for a user.

        Args:
            topic: For kind="news", a free-text search query. For
                kind="stock", a ticker symbol (e.g. "AAPL"). For
                kind="github", an "owner/repo" string.
            kind: One of WATCH_KINDS - defaults to "news".
        """
        topics = self._load_topics(user_id)

        new_topic = WatchTopic(
            topic_id=str(uuid.uuid4()),
            topic=topic,
            user_id=user_id,
            created_at=datetime.now().isoformat(),
            kind=kind,
        )

        topics.append(new_topic)
        self._save_topics(user_id, topics)

        return new_topic

    def get_topics(self, user_id: str) -> List[WatchTopic]:
        """Get all watched topics for a user, sorted by creation date (newest first)."""
        topics = self._load_topics(user_id)
        return sorted(topics, key=lambda t: t.created_at, reverse=True)

    def get_topic_by_id(self, user_id: str, topic_id: str) -> Optional[WatchTopic]:
        """Get a specific watched topic by ID."""
        for topic in self._load_topics(user_id):
            if topic.id == topic_id:
                return topic
        return None

    def find_topic(self, user_id: str, topic_or_id: str) -> Optional[WatchTopic]:
        """Resolve a topic by exact ID, or failing that, by a case-insensitive
        substring match against its text. Used so chat requests like "stop
        watching bitcoin" work without the caller knowing the raw topic ID.
        """
        topics = self._load_topics(user_id)

        for topic in topics:
            if topic.id == topic_or_id:
                return topic

        needle = topic_or_id.lower()
        matches = [t for t in topics if needle in t.topic.lower()]
        if len(matches) == 1:
            return matches[0]
        return None

    def remove_topic(self, user_id: str, topic_id: str) -> bool:
        """Remove a watched topic by ID."""
        topics = self._load_topics(user_id)
        original_count = len(topics)
        topics = [t for t in topics if t.id != topic_id]

        if len(topics) < original_count:
            self._save_topics(user_id, topics)
            return True
        return False

    def mark_run(self, user_id: str, topic_id: str, new_seen_urls: List[str], run_at: str) -> None:
        """Record that a topic was checked, updating its dedup state.

        Called once per topic per heartbeat tick that actually performs a
        search, regardless of whether anything new was found - this is what
        keeps _process_world_watch from re-searching a topic before its
        WORLD_WATCH_INTERVAL_HOURS window is up.
        """
        topics = self._load_topics(user_id)

        for topic in topics:
            if topic.id == topic_id:
                merged = topic.seen_urls + [u for u in new_seen_urls if u not in topic.seen_urls]
                topic.seen_urls = merged[-MAX_SEEN_URLS:]
                topic.last_run_at = run_at
                self._save_topics(user_id, topics)
                return

    # ── Memory-driven suggestion state ──────────────────────────────────────
    # Separate from the topics themselves: tracks what HeartbeatManager's
    # _process_memory_watch_suggestions() has already proposed, so it doesn't
    # nag about the same candidate topic on every run.

    def _get_suggestion_file(self, user_id: str) -> Path:
        return self.data_dir / f"{user_id}.suggestions.json"

    def _load_suggestion_state(self, user_id: str) -> Dict:
        file_path = self._get_suggestion_file(user_id)
        if not file_path.exists():
            return {"last_run_at": None, "suggested": []}
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading suggestion state for user {user_id}: {e}")
            return {"last_run_at": None, "suggested": []}

    def get_last_suggestion_run(self, user_id: str) -> Optional[str]:
        return self._load_suggestion_state(user_id).get("last_run_at")

    def get_suggested_topics(self, user_id: str) -> List[str]:
        """Topics already proposed to the user (accepted or not) - never re-suggest these."""
        return self._load_suggestion_state(user_id).get("suggested", [])

    def record_suggestions(self, user_id: str, new_topics: List[str], run_at: str) -> None:
        state = self._load_suggestion_state(user_id)
        state["last_run_at"] = run_at
        state["suggested"] = state.get("suggested", []) + new_topics
        try:
            with open(self._get_suggestion_file(user_id), "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving suggestion state for user {user_id}: {e}")
            raise
