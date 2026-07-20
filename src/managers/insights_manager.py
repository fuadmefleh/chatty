"""Insights Manager - handles persistent storage of proactively-surfaced insights.

Insights are system-generated only, by HeartbeatManager._process_world_watch()
(see skills/watchlist/ for the topics that drive it). There's no LLM tool to
create one directly - this is a read-mostly store consumed by the web
dashboard's Insights page.
"""
import fcntl
import json
import os
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

# Records with no `schema_version` predate structured insights and have only
# a flat `summary`; the frontend falls back to the old layout for these.
LEGACY_SCHEMA_VERSION = 1
STRUCTURED_SCHEMA_VERSION = 2


class Insight:
    """Represents a single surfaced insight about a watched topic.

    Records written before the structured-insight change only have `summary`
    (a flat paragraph). Every structured field defaults, so those legacy
    records still load; `schema_version` is what tells the frontend which
    layout to render.
    """

    def __init__(
        self,
        insight_id: str,
        topic: str,
        summary: str,
        sources: List[Dict[str, str]],
        created_at: str,
        user_id: str,
        kind: str = "news",
        significance: int = 3,
        headline: str = "",
        what_happened: str = "",
        why_it_matters: str = "",
        what_to_watch: Optional[List[str]] = None,
        entities: Optional[List[str]] = None,
        connection: Optional[Dict[str, str]] = None,
        schema_version: int = LEGACY_SCHEMA_VERSION,
        ad_hoc: bool = False,
    ):
        self.id = insight_id
        self.topic = topic
        self.summary = summary
        self.sources = sources
        self.created_at = created_at
        self.user_id = user_id
        self.kind = kind
        self.significance = significance
        self.headline = headline
        self.what_happened = what_happened
        self.why_it_matters = why_it_matters
        self.what_to_watch = what_to_watch or []
        self.entities = entities or []
        self.connection = connection
        self.schema_version = schema_version
        self.ad_hoc = ad_hoc

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "topic": self.topic,
            "summary": self.summary,
            "sources": self.sources,
            "created_at": self.created_at,
            "user_id": self.user_id,
            "kind": self.kind,
            "significance": self.significance,
            "headline": self.headline,
            "what_happened": self.what_happened,
            "why_it_matters": self.why_it_matters,
            "what_to_watch": self.what_to_watch,
            "entities": self.entities,
            "connection": self.connection,
            "schema_version": self.schema_version,
            "ad_hoc": self.ad_hoc,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "Insight":
        return cls(
            insight_id=data["id"],
            topic=data["topic"],
            summary=data["summary"],
            sources=data.get("sources", []),
            created_at=data["created_at"],
            user_id=data["user_id"],
            kind=data.get("kind", "news"),
            significance=data.get("significance", 3),
            headline=data.get("headline", ""),
            what_happened=data.get("what_happened", ""),
            why_it_matters=data.get("why_it_matters", ""),
            what_to_watch=data.get("what_to_watch", []),
            entities=data.get("entities", []),
            connection=data.get("connection"),
            schema_version=data.get("schema_version", LEGACY_SCHEMA_VERSION),
            ad_hoc=data.get("ad_hoc", False),
        )


class InsightsManager:
    """Manages per-user surfaced insights with persistent JSON storage."""

    def __init__(self, data_dir: Optional[str] = None):
        if data_dir is None:
            from src.core import config
            data_dir = str(config.BASE_DIR / "data" / "insights")
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def _get_user_file(self, user_id: str) -> Path:
        return self.data_dir / f"{user_id}.json"

    @contextmanager
    def _user_lock(self, user_id: str):
        """Serialize a read-modify-write across processes.

        Insights are written by chatty-bot (the heartbeat) and
        chatty-web-server (on-demand scans) - two separate processes over one
        file. add_insight/delete_insight rewrite the whole file, so without
        this an interleaved pair silently drops one of the two writes.

        The lock is a sidecar file rather than the data file itself, so the
        atomic replace in _save_insights can't swap the inode out from under
        a held lock.
        """
        lock_path = self.data_dir / f"{user_id}.lock"
        with open(lock_path, "w", encoding="utf-8") as lock_file:
            fcntl.flock(lock_file, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_file, fcntl.LOCK_UN)

    def _load_insights(self, user_id: str) -> List[Insight]:
        file_path = self._get_user_file(user_id)

        if not file_path.exists():
            return []

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return [Insight.from_dict(i) for i in data]
        except Exception as e:
            print(f"Error loading insights for user {user_id}: {e}")
            return []

    def _save_insights(self, user_id: str, insights: List[Insight]) -> None:
        """Write the file atomically.

        A plain truncate-and-write leaves the file torn for the duration of
        the dump, and a concurrent reader in the other process sees invalid
        JSON. Writing a temp file and renaming makes the swap atomic, so
        readers see either the old contents or the new ones.
        """
        file_path = self._get_user_file(user_id)
        tmp_path = file_path.with_suffix(".json.tmp")

        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump([i.to_dict() for i in insights], f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, file_path)
        except Exception as e:
            print(f"Error saving insights for user {user_id}: {e}")
            tmp_path.unlink(missing_ok=True)
            raise

    def add_insight(
        self,
        user_id: str,
        topic: str,
        summary: str,
        sources: List[Dict[str, str]],
        kind: str = "news",
        significance: int = 3,
        headline: str = "",
        what_happened: str = "",
        why_it_matters: str = "",
        what_to_watch: Optional[List[str]] = None,
        entities: Optional[List[str]] = None,
        connection: Optional[Dict[str, str]] = None,
        ad_hoc: bool = False,
    ) -> Insight:
        """Persist a newly surfaced insight for a user.

        Only `summary` is required beyond the identifiers - callers that
        don't produce structured analysis still write a valid record.

        `ad_hoc` marks a user-initiated one-off search rather than a
        scheduled watchlist finding; those are kept out of the default feed.
        """
        new_insight = Insight(
            insight_id=str(uuid.uuid4()),
            topic=topic,
            summary=summary,
            sources=sources,
            created_at=datetime.now().isoformat(),
            user_id=user_id,
            kind=kind,
            significance=significance,
            headline=headline,
            what_happened=what_happened,
            why_it_matters=why_it_matters,
            what_to_watch=what_to_watch,
            entities=entities,
            connection=connection,
            schema_version=STRUCTURED_SCHEMA_VERSION if headline else LEGACY_SCHEMA_VERSION,
            ad_hoc=ad_hoc,
        )

        with self._user_lock(user_id):
            insights = self._load_insights(user_id)
            insights.append(new_insight)
            self._save_insights(user_id, insights)

        return new_insight

    def get_insights(
        self,
        user_id: str,
        limit: int = 50,
        min_significance: int = 1,
        include_ad_hoc: bool = False,
    ) -> List[Insight]:
        """Get insights for a user, sorted by creation date (newest first).

        Ad-hoc search results are excluded unless asked for, so a throwaway
        one-off search doesn't permanently clutter the curated feed.
        """
        insights = [
            i for i in self._load_insights(user_id)
            if i.significance >= min_significance and (include_ad_hoc or not i.ad_hoc)
        ]
        insights.sort(key=lambda i: i.created_at, reverse=True)
        return insights[:limit]

    def get_insights_by_topic(self, user_id: str, topic: str, limit: int = 5) -> List[Insight]:
        """Recent insights for one topic, newest first.

        Feeds the analyzer the history it needs to link a new finding back to
        what was already surfaced.
        """
        insights = [i for i in self._load_insights(user_id) if i.topic == topic]
        insights.sort(key=lambda i: i.created_at, reverse=True)
        return insights[:limit]

    def delete_insight(self, user_id: str, insight_id: str) -> bool:
        """Delete a specific insight."""
        with self._user_lock(user_id):
            insights = self._load_insights(user_id)
            original_count = len(insights)
            insights = [i for i in insights if i.id != insight_id]

            if len(insights) < original_count:
                self._save_insights(user_id, insights)
                return True
            return False
