"""Tests for conversation session detection and continuation."""
import asyncio
import json
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.memory import ConversationHistoryManager, SESSION_GAP_SECONDS


def _ts(dt: datetime) -> str:
    return dt.now().isoformat()


class TestSessionDetection:
    """Test session grouping logic."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()

    def _make_mgr(self):
        mgr = ConversationHistoryManager.__new__(ConversationHistoryManager)
        mgr.user_id = "test_user"
        history_dir = Path(self.tmpdir) / "conversations"
        history_dir.mkdir(parents=True, exist_ok=True)
        mgr._path = history_dir / "history.json"
        return mgr

    def _write_history(self, messages: list):
        with open(self._make_mgr()._path, "w") as f:
            json.dump(messages, f)

    def test_empty_history_returns_no_sessions(self):
        mgr = self._make_mgr()
        sessions = asyncio.get_event_loop().run_until_complete(mgr.get_sessions())
        assert sessions == []

    def test_single_session(self):
        now = datetime(2025, 1, 1, 12, 0, 0)
        msgs = [
            {"role": "user", "content": "Hello!", "ts": (now + timedelta(minutes=i)).isoformat()}
            for i in range(10)
        ]
        self._write_history(msgs)
        mgr = self._make_mgr()
        sessions = asyncio.get_event_loop().run_until_complete(mgr.get_sessions())
        assert len(sessions) == 1
        assert sessions[0]["message_count"] == len(msgs)

    def test_two_sessions_with_gap(self):
        now = datetime(2025, 1, 1, 12, 0, 0)
        # Session 1: 12:00-12:05
        msgs = [
            {"role": "user", "content": "Hello!", "ts": (now + timedelta(minutes=i)).isoformat()}
            for i in range(6)
        ]
        # Session 2: 13:30-13:35 (gap > 1 hour)
        later = now + timedelta(hours=2)
        msgs += [
            {"role": "assistant", "content": "Hi again!", "ts": (later + timedelta(minutes=i)).isoformat()}
            for i in range(5)
        ]
        self._write_history(msgs)
        mgr = self._make_mgr()
        sessions = asyncio.get_event_loop().run_until_complete(mgr.get_sessions())
        assert len(sessions) == 2
        # Newest first
        assert sessions[0]["message_count"] == 5
        assert sessions[1]["message_count"] == 6

    def test_get_session_returns_messages_without_ts(self):
        now = datetime(2025, 1, 1, 12, 0, 0)
        msgs = [
            {"role": "user", "content": "A", "ts": now.isoformat()},
            {"role": "assistant", "content": "B", "ts": (now + timedelta(minutes=1)).isoformat()},
        ]
        self._write_history(msgs)
        mgr = self._make_mgr()
        session_msgs = asyncio.get_event_loop().run_until_complete(mgr.get_session(0))
        assert len(session_msgs) == 2
        for m in session_msgs:
            assert "ts" not in m
            assert "role" in m
            assert "content" in m

    def test_session_summary_is_first_user_message(self):
        now = datetime(2025, 1, 1, 12, 0, 0)
        msgs = [
            {"role": "assistant", "content": "Bot greeting", "ts": now.isoformat()},
            {"role": "user", "content": "What is the capital of France?", "ts": (now + timedelta(seconds=1)).isoformat()},
        ]
        self._write_history(msgs)
        mgr = self._make_mgr()
        sessions = asyncio.get_event_loop().run_until_complete(mgr.get_sessions())
        assert sessions[0]["summary"] == "What is the capital of France?"

    def test_session_summary_truncated(self):
        now = datetime(2025, 1, 1, 12, 0, 0)
        long_msg = "x" * 200
        msgs = [
            {"role": "user", "content": long_msg, "ts": now.isoformat()},
        ]
        self._write_history(msgs)
        mgr = self._make_mgr()
        sessions = asyncio.get_event_loop().run_until_complete(mgr.get_sessions())
        assert sessions[0]["summary"] == long_msg[:100] + "..."

    def test_get_session_out_of_range(self):
        msgs = []
        self._write_history(msgs)
        mgr = self._make_mgr()
        result = asyncio.get_event_loop().run_until_complete(mgr.get_session(99))
        assert result == []
