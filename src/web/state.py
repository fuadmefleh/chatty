"""Process-lifetime singletons shared by the web API's routers.

Routers must import this module and read `state.X` at call time (e.g.
`state.transcriptions_manager.list(...)`), never `from src.web.state import
transcriptions_manager` - the latter copies the reference at import time and
would go stale if the attribute is later reassigned (relevant for
`skills_manager`, set in the app's lifespan, and `_pi_worker_task`, reassigned
per feature-request queue run).
"""
import asyncio
import json
from collections import defaultdict
from typing import Dict, List, Optional

from src.core.logging_config import get_api_logger
from src.core.skills_manager import SkillsManager
from src.managers.insights_manager import InsightsManager
from src.managers.scan_jobs import ScanJobRegistry
from src.managers.trending_manager import TrendingSuggestionsManager
from src.managers.webcam_manager import WebcamSourcesManager, WebcamSuggestionsManager
from src.core.token_usage_manager import get_token_usage_manager
from skills.notes.notes_manager import NotesManager
from skills.transcriptions.transcriptions_manager import TranscriptionsManager
from skills.speakers.speaker_manager import SpeakerManager
from skills.watchlist.watchlist_manager import WatchlistManager
from skills.pi_agent.requests_manager import FeatureRequestsManager

logger = get_api_logger()

notes_manager = NotesManager()
transcriptions_manager = TranscriptionsManager()
speaker_manager = SpeakerManager()
watchlist_manager = WatchlistManager()
insights_manager = InsightsManager()
# On-demand insight scans in flight. In-memory by design - see scan_jobs.py.
scan_jobs = ScanJobRegistry()
feature_requests_manager = FeatureRequestsManager()
trending_suggestions_manager = TrendingSuggestionsManager()
webcam_sources_manager = WebcamSourcesManager()
webcam_suggestions_manager = WebcamSuggestionsManager()
token_usage_manager = get_token_usage_manager()

# Set by the app's lifespan startup handler (src/web/app.py).
skills_manager: Optional[SkillsManager] = None

# Reassigned by requests.py's _ensure_pi_worker_running/_process_pi_queue.
_pi_worker_task: Optional[asyncio.Task] = None


class _ChatConnection:
    """An open /api/chatty/chat WebSocket, keyed by X-Device-Id so the audio
    pipeline can push a proactive assistant response onto it. The lock
    serializes sends across the interactive request/response loop and any
    background push, since Starlette WebSockets aren't safe for concurrent
    send_text calls from multiple tasks."""

    __slots__ = ("websocket", "lock")

    def __init__(self, websocket):
        self.websocket = websocket
        self.lock = asyncio.Lock()

    async def send_json(self, payload: dict) -> None:
        async with self.lock:
            await self.websocket.send_text(json.dumps(payload))


# device_id -> open chat connection (only devices that sent X-Device-Id on
# the WS handshake are tracked; at most one entry per device).
_active_chat_connections: Dict[str, "_ChatConnection"] = {}

# Per-IP auth-lockout state (see src/web/auth.py).
_auth_failures: Dict[str, List[float]] = defaultdict(list)
_auth_locked_until: Dict[str, float] = {}
