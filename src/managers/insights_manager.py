"""Insights Manager - handles persistent storage of proactively-surfaced insights.

Insights are system-generated only, by HeartbeatManager._process_world_watch()
(see skills/watchlist/ for the topics that drive it). There's no LLM tool to
create one directly - this is a read-mostly store consumed by the web
dashboard's Insights page.
"""
import json
import uuid
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
        file_path = self._get_user_file(user_id)

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump([i.to_dict() for i in insights], f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving insights for user {user_id}: {e}")
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
    ) -> Insight:
        """Persist a newly surfaced insight for a user.

        Only `summary` is required beyond the identifiers - callers that
        don't produce structured analysis still write a valid record.
        """
        insights = self._load_insights(user_id)

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
        )

        insights.append(new_insight)
        self._save_insights(user_id, insights)

        return new_insight

    def get_insights(self, user_id: str, limit: int = 50, min_significance: int = 1) -> List[Insight]:
        """Get insights for a user, sorted by creation date (newest first)."""
        insights = [i for i in self._load_insights(user_id) if i.significance >= min_significance]
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
        insights = self._load_insights(user_id)
        original_count = len(insights)
        insights = [i for i in insights if i.id != insight_id]

        if len(insights) < original_count:
            self._save_insights(user_id, insights)
            return True
        return False
