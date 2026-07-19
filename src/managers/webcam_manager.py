"""Webcam sources: a user-managed list of live public webcam feeds (traffic
cams, city/tourism live views, etc.) plus a queue of auto-discovered
candidates awaiting review.

Two related stores live here because approving a suggestion writes to both:
- WebcamSourcesManager - the actual list Chatty knows about (data/webcam_sources/sources.json).
- WebcamSuggestionsManager - candidates found by src/managers/webcam_discovery.py's
  SearXNG-driven scan, reviewed via the dashboard's /webcams page
  (data/webcam_sources/suggestions.json).

This module only tracks where to look; the actual fetch/verify-playability
checks live in src/managers/webcam_verifier.py, whose results are stored here
in each row's verify_status/verify_detail/last_verified_at.
"""
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# Valid values for WebcamSource.kind / WebcamSuggestion.kind - describes how
# the URL should eventually be consumed (a later feature's concern; for now
# this just informs the dashboard's display and the discovery LLM's guesses).
WEBCAM_KINDS = ("snapshot", "mjpeg", "hls", "youtube", "webpage")

# Result of src/managers/webcam_verifier.py's verify_webcam(): "ok" means the
# feed was actually fetched and looks playable, "broken" means it failed
# (dead link, wrong content-type, etc.), "unchecked" is the pre-verification
# default for rows written before this field existed.
VERIFY_STATUSES = ("ok", "broken", "unchecked")


class WebcamSource:
    """A single webcam Chatty knows about."""

    def __init__(
        self,
        source_id: str,
        name: str,
        url: str,
        created_at: str,
        updated_at: str,
        kind: str = "webpage",
        location: str = "",
        enabled: bool = True,
        source: str = "manual",
        suggestion_id: Optional[str] = None,
        verify_status: str = "unchecked",
        verify_detail: str = "",
        last_verified_at: Optional[str] = None,
    ):
        self.id = source_id
        self.name = name
        self.url = url
        self.kind = kind if kind in WEBCAM_KINDS else "webpage"
        self.location = location
        self.enabled = enabled
        self.source = source if source in ("manual", "suggestion") else "manual"
        self.suggestion_id = suggestion_id
        self.verify_status = verify_status if verify_status in VERIFY_STATUSES else "unchecked"
        self.verify_detail = verify_detail
        self.last_verified_at = last_verified_at
        self.created_at = created_at
        self.updated_at = updated_at

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "url": self.url,
            "kind": self.kind,
            "location": self.location,
            "enabled": self.enabled,
            "source": self.source,
            "suggestion_id": self.suggestion_id,
            "verify_status": self.verify_status,
            "verify_detail": self.verify_detail,
            "last_verified_at": self.last_verified_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "WebcamSource":
        return cls(
            source_id=data["id"],
            name=data["name"],
            url=data["url"],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            kind=data.get("kind", "webpage"),
            location=data.get("location", ""),
            enabled=data.get("enabled", True),
            source=data.get("source", "manual"),
            suggestion_id=data.get("suggestion_id"),
            verify_status=data.get("verify_status", "unchecked"),
            verify_detail=data.get("verify_detail", ""),
            last_verified_at=data.get("last_verified_at"),
        )


class WebcamSourcesManager:
    """Manages the user's webcam sources with persistent JSON storage."""

    def __init__(self, data_dir: Optional[str] = None):
        if data_dir is None:
            from src.core import config
            data_dir = str(config.BASE_DIR / "data" / "webcam_sources")
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._file = self.data_dir / "sources.json"

    def _load(self) -> List[WebcamSource]:
        if not self._file.exists():
            return []
        try:
            with open(self._file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return [WebcamSource.from_dict(s) for s in data]
        except Exception as e:
            print(f"Error loading webcam sources: {e}")
            return []

    def _save(self, sources: List[WebcamSource]) -> None:
        try:
            with open(self._file, "w", encoding="utf-8") as f:
                json.dump([s.to_dict() for s in sources], f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving webcam sources: {e}")
            raise

    def create(
        self,
        name: str,
        url: str,
        kind: str = "webpage",
        location: str = "",
        enabled: bool = True,
        source: str = "manual",
        suggestion_id: Optional[str] = None,
        verify_status: str = "unchecked",
        verify_detail: str = "",
        last_verified_at: Optional[str] = None,
    ) -> WebcamSource:
        sources = self._load()
        now = datetime.now().isoformat()
        new_source = WebcamSource(
            source_id=str(uuid.uuid4()),
            name=name,
            url=url,
            created_at=now,
            updated_at=now,
            kind=kind,
            location=location,
            enabled=enabled,
            source=source,
            suggestion_id=suggestion_id,
            verify_status=verify_status,
            verify_detail=verify_detail,
            last_verified_at=last_verified_at,
        )
        sources.append(new_source)
        self._save(sources)
        return new_source

    def list(self) -> List[WebcamSource]:
        """All sources, newest first."""
        sources = self._load()
        return sorted(sources, key=lambda s: s.created_at, reverse=True)

    def get(self, source_id: str) -> Optional[WebcamSource]:
        for s in self._load():
            if s.id == source_id:
                return s
        return None

    def update(self, source_id: str, **fields) -> Optional[WebcamSource]:
        sources = self._load()
        for s in sources:
            if s.id == source_id:
                for key, value in fields.items():
                    if key == "kind" and value not in WEBCAM_KINDS:
                        continue
                    setattr(s, key, value)
                s.updated_at = datetime.now().isoformat()
                self._save(sources)
                return s
        return None

    def delete(self, source_id: str) -> bool:
        sources = self._load()
        original_count = len(sources)
        sources = [s for s in sources if s.id != source_id]
        if len(sources) < original_count:
            self._save(sources)
            return True
        return False


class WebcamSuggestion:
    """A single candidate webcam found by a discovery scan, pending review."""

    def __init__(
        self,
        suggestion_id: str,
        name: str,
        url: str,
        discovered_url: str,
        created_at: str,
        updated_at: str,
        kind: str = "webpage",
        location: str = "",
        rationale: str = "",
        status: str = "pending",
        source_id: Optional[str] = None,
        verify_status: str = "unchecked",
        verify_detail: str = "",
        last_verified_at: Optional[str] = None,
    ):
        self.id = suggestion_id
        self.name = name
        self.url = url
        self.discovered_url = discovered_url
        self.kind = kind if kind in WEBCAM_KINDS else "webpage"
        self.location = location
        self.rationale = rationale
        self.status = status  # pending | approved | dismissed
        self.source_id = source_id  # set once "Approve" creates a WebcamSource
        self.verify_status = verify_status if verify_status in VERIFY_STATUSES else "unchecked"
        self.verify_detail = verify_detail
        self.last_verified_at = last_verified_at
        self.created_at = created_at
        self.updated_at = updated_at

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "url": self.url,
            "discovered_url": self.discovered_url,
            "kind": self.kind,
            "location": self.location,
            "rationale": self.rationale,
            "status": self.status,
            "source_id": self.source_id,
            "verify_status": self.verify_status,
            "verify_detail": self.verify_detail,
            "last_verified_at": self.last_verified_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "WebcamSuggestion":
        return cls(
            suggestion_id=data["id"],
            name=data["name"],
            url=data["url"],
            discovered_url=data["discovered_url"],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            kind=data.get("kind", "webpage"),
            location=data.get("location", ""),
            rationale=data.get("rationale", ""),
            status=data.get("status", "pending"),
            source_id=data.get("source_id"),
            verify_status=data.get("verify_status", "unchecked"),
            verify_detail=data.get("verify_detail", ""),
            last_verified_at=data.get("last_verified_at"),
        )


class WebcamSuggestionsManager:
    """Manages discovered webcam suggestions with persistent JSON storage."""

    def __init__(self, data_dir: Optional[str] = None):
        if data_dir is None:
            from src.core import config
            data_dir = str(config.BASE_DIR / "data" / "webcam_sources")
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._file = self.data_dir / "suggestions.json"

    def _load(self) -> List[WebcamSuggestion]:
        if not self._file.exists():
            return []
        try:
            with open(self._file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return [WebcamSuggestion.from_dict(s) for s in data]
        except Exception as e:
            print(f"Error loading webcam suggestions: {e}")
            return []

    def _save(self, suggestions: List[WebcamSuggestion]) -> None:
        try:
            with open(self._file, "w", encoding="utf-8") as f:
                json.dump([s.to_dict() for s in suggestions], f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving webcam suggestions: {e}")
            raise

    def create(
        self,
        name: str,
        url: str,
        discovered_url: str,
        kind: str = "webpage",
        location: str = "",
        rationale: str = "",
        verify_status: str = "unchecked",
        verify_detail: str = "",
        last_verified_at: Optional[str] = None,
    ) -> WebcamSuggestion:
        suggestions = self._load()
        now = datetime.now().isoformat()
        new_suggestion = WebcamSuggestion(
            suggestion_id=str(uuid.uuid4()),
            name=name,
            url=url,
            discovered_url=discovered_url,
            created_at=now,
            updated_at=now,
            kind=kind,
            location=location,
            rationale=rationale,
            status="pending",
            verify_status=verify_status,
            verify_detail=verify_detail,
            last_verified_at=last_verified_at,
        )
        suggestions.append(new_suggestion)
        self._save(suggestions)
        return new_suggestion

    def list(self) -> List[WebcamSuggestion]:
        """All suggestions, newest first."""
        suggestions = self._load()
        return sorted(suggestions, key=lambda s: s.created_at, reverse=True)

    def list_by_status(self, status: str) -> List[WebcamSuggestion]:
        return [s for s in self.list() if s.status == status]

    def get(self, suggestion_id: str) -> Optional[WebcamSuggestion]:
        for s in self._load():
            if s.id == suggestion_id:
                return s
        return None

    def update(self, suggestion_id: str, **fields) -> Optional[WebcamSuggestion]:
        suggestions = self._load()
        for s in suggestions:
            if s.id == suggestion_id:
                for key, value in fields.items():
                    setattr(s, key, value)
                s.updated_at = datetime.now().isoformat()
                self._save(suggestions)
                return s
        return None

    def delete(self, suggestion_id: str) -> bool:
        suggestions = self._load()
        original_count = len(suggestions)
        suggestions = [s for s in suggestions if s.id != suggestion_id]
        if len(suggestions) < original_count:
            self._save(suggestions)
            return True
        return False

    def seen_discovered_urls(self) -> set:
        """Every discovered_url ever suggested, so a scan never re-proposes
        the same page regardless of the suggestion's current status."""
        return {s.discovered_url for s in self._load()}
