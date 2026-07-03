"""Tests for HeartbeatManager._process_memory_watch_suggestions (interval gating + exclusion)."""
import sys
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.managers.heartbeat_manager import HeartbeatManager


def make_manager():
    hb = HeartbeatManager(skills_manager=MagicMock())
    hb._send_message_callback = AsyncMock()
    return hb


@pytest.mark.asyncio
async def test_within_interval_is_skipped():
    """A user whose last suggestion run was recent should not be re-mined."""
    hb = make_manager()
    hb._suggest_watch_topics_from_memory = AsyncMock(return_value=["some topic"])

    watchlist_mgr = MagicMock()
    watchlist_mgr.get_last_suggestion_run.return_value = datetime.now().isoformat()

    with patch("skills.watchlist.watchlist_manager.WatchlistManager", return_value=watchlist_mgr), \
         patch("src.main.authorized_users", {"u1": "phone"}), \
         patch("src.core.config.MEMORY_SUGGESTION_INTERVAL_HOURS", 168):

        result = await hb._process_memory_watch_suggestions()

    hb._suggest_watch_topics_from_memory.assert_not_called()
    hb._send_message_callback.assert_not_awaited()
    assert result is None


@pytest.mark.asyncio
async def test_past_interval_suggests_and_excludes_active_and_previous():
    """Past the interval, mines memory and excludes already-watched/suggested topics."""
    hb = make_manager()
    hb._suggest_watch_topics_from_memory = AsyncMock(return_value=["new candidate topic"])

    active_topic = MagicMock()
    active_topic.topic = "already watched thing"

    watchlist_mgr = MagicMock()
    watchlist_mgr.get_last_suggestion_run.return_value = (datetime.now() - timedelta(hours=200)).isoformat()
    watchlist_mgr.get_topics.return_value = [active_topic]
    watchlist_mgr.get_suggested_topics.return_value = ["previously suggested thing"]

    memory_manager = MagicMock()
    memory_manager.get_long_term_memory = AsyncMock(return_value="User loves rockets and open source software.")

    with patch("skills.watchlist.watchlist_manager.WatchlistManager", return_value=watchlist_mgr), \
         patch("src.core.memory.MemoryManager", return_value=memory_manager), \
         patch("src.main.authorized_users", {"u1": "phone"}), \
         patch("src.core.config.MEMORY_SUGGESTION_INTERVAL_HOURS", 168):

        result = await hb._process_memory_watch_suggestions()

    hb._suggest_watch_topics_from_memory.assert_awaited_once()
    _, exclude_arg = hb._suggest_watch_topics_from_memory.await_args.args
    assert "already watched thing" in exclude_arg
    assert "previously suggested thing" in exclude_arg

    hb._send_message_callback.assert_awaited_once()
    watchlist_mgr.record_suggestions.assert_called_once()
    recorded_args = watchlist_mgr.record_suggestions.call_args.args
    assert recorded_args[1] == ["new candidate topic"]
    assert result is not None and "1 new topic" in result


@pytest.mark.asyncio
async def test_no_candidates_records_empty_run_without_messaging():
    hb = make_manager()
    hb._suggest_watch_topics_from_memory = AsyncMock(return_value=[])

    watchlist_mgr = MagicMock()
    watchlist_mgr.get_last_suggestion_run.return_value = None
    watchlist_mgr.get_topics.return_value = []
    watchlist_mgr.get_suggested_topics.return_value = []

    memory_manager = MagicMock()
    memory_manager.get_long_term_memory = AsyncMock(return_value="Some memory content.")

    with patch("skills.watchlist.watchlist_manager.WatchlistManager", return_value=watchlist_mgr), \
         patch("src.core.memory.MemoryManager", return_value=memory_manager), \
         patch("src.main.authorized_users", {"u1": "phone"}), \
         patch("src.core.config.MEMORY_SUGGESTION_INTERVAL_HOURS", 168):

        result = await hb._process_memory_watch_suggestions()

    hb._send_message_callback.assert_not_awaited()
    watchlist_mgr.record_suggestions.assert_called_once_with("u1", [], watchlist_mgr.record_suggestions.call_args.args[2])
    assert result is None


@pytest.mark.asyncio
async def test_no_authorized_users_short_circuits():
    hb = make_manager()

    with patch("src.main.authorized_users", {}):
        result = await hb._process_memory_watch_suggestions()

    assert result is None
    hb._send_message_callback.assert_not_awaited()
