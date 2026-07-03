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


class Insight:
    """Represents a single surfaced insight about a watched topic."""

    def __init__(
        self,
        insight_id: str,
        topic: str,
        summary: str,
        sources: List[Dict[str, str]],
        created_at: str,
        user_id: str,
    ):
        self.id = insight_id
        self.topic = topic
        self.summary = summary
        self.sources = sources
        self.created_at = created_at
        self.user_id = user_id

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "topic": self.topic,
            "summary": self.summary,
            "sources": self.sources,
            "created_at": self.created_at,
            "user_id": self.user_id,
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

    def add_insight(self, user_id: str, topic: str, summary: str, sources: List[Dict[str, str]]) -> Insight:
        """Persist a newly surfaced insight for a user."""
        insights = self._load_insights(user_id)

        new_insight = Insight(
            insight_id=str(uuid.uuid4()),
            topic=topic,
            summary=summary,
            sources=sources,
            created_at=datetime.now().isoformat(),
            user_id=user_id,
        )

        insights.append(new_insight)
        self._save_insights(user_id, insights)

        return new_insight

    def get_insights(self, user_id: str, limit: int = 50) -> List[Insight]:
        """Get insights for a user, sorted by creation date (newest first)."""
        insights = self._load_insights(user_id)
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
