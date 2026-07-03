"""Tests for HeartbeatManager._process_world_watch (dedup + interval gating logic)."""
import sys
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.managers.heartbeat_manager import HeartbeatManager
from skills.watchlist.watchlist_manager import WatchTopic


def make_manager():
    hb = HeartbeatManager(skills_manager=MagicMock())
    hb._send_message_callback = AsyncMock()
    # Avoid real LLM calls - tests only exercise dedup/interval logic.
    hb._summarize_world_watch_results = AsyncMock(return_value="Something notable happened.")
    return hb


def make_search_result(urls):
    return {
        "success": True,
        "results": [
            {"title": f"Title {u}", "link": u, "snippet": "snippet", "display_link": "example.com"}
            for u in urls
        ],
    }


@pytest.mark.asyncio
async def test_dedup_only_summarizes_new_urls():
    """Results already in seen_urls should be excluded from the summarized set."""
    hb = make_manager()

    topic = WatchTopic(
        topic_id="t1", topic="widgets", user_id="u1",
        created_at=datetime.now().isoformat(), last_run_at=None,
        seen_urls=["https://a.example", "https://b.example"],
    )
    watchlist_mgr = MagicMock()
    watchlist_mgr.get_topics.return_value = [topic]

    search_client = MagicMock()
    search_client.search_news = AsyncMock(
        return_value=make_search_result(["https://a.example", "https://b.example", "https://c.example"])
    )

    with patch("skills.watchlist.watchlist_manager.WatchlistManager", return_value=watchlist_mgr), \
         patch("src.managers.insights_manager.InsightsManager") as insights_cls, \
         patch("skills.web_search.searxng_client.get_search_client", return_value=search_client), \
         patch("src.main.authorized_users", {"u1": "phone"}):

        insights_mgr = MagicMock()
        insights_cls.return_value = insights_mgr

        result = await hb._process_world_watch()

    # Only the genuinely new result should reach the summarizer.
    hb._summarize_world_watch_results.assert_awaited_once()
    _, summarized_results = hb._summarize_world_watch_results.await_args.args
    assert [r["link"] for r in summarized_results] == ["https://c.example"]

    insights_mgr.add_insight.assert_called_once()
    hb._send_message_callback.assert_awaited_once()
    assert result is not None and "1 new insight" in result


@pytest.mark.asyncio
async def test_topic_within_interval_is_skipped():
    """A topic checked recently should not be searched again before the interval elapses."""
    hb = make_manager()

    topic = WatchTopic(
        topic_id="t1", topic="widgets", user_id="u1",
        created_at=datetime.now().isoformat(),
        last_run_at=datetime.now().isoformat(),  # just checked
        seen_urls=[],
    )
    watchlist_mgr = MagicMock()
    watchlist_mgr.get_topics.return_value = [topic]

    search_client = MagicMock()
    search_client.search_news = AsyncMock(return_value=make_search_result(["https://a.example"]))

    with patch("skills.watchlist.watchlist_manager.WatchlistManager", return_value=watchlist_mgr), \
         patch("src.managers.insights_manager.InsightsManager"), \
         patch("skills.web_search.searxng_client.get_search_client", return_value=search_client), \
         patch("src.main.authorized_users", {"u1": "phone"}), \
         patch("src.core.config.WORLD_WATCH_INTERVAL_HOURS", 24):

        result = await hb._process_world_watch()

    search_client.search_news.assert_not_called()
    assert result is None


@pytest.mark.asyncio
async def test_topic_past_interval_is_checked():
    """A topic last checked over WORLD_WATCH_INTERVAL_HOURS ago should be searched again."""
    hb = make_manager()

    topic = WatchTopic(
        topic_id="t1", topic="widgets", user_id="u1",
        created_at=datetime.now().isoformat(),
        last_run_at=(datetime.now() - timedelta(hours=25)).isoformat(),
        seen_urls=[],
    )
    watchlist_mgr = MagicMock()
    watchlist_mgr.get_topics.return_value = [topic]

    search_client = MagicMock()
    search_client.search_news = AsyncMock(return_value=make_search_result(["https://a.example"]))

    with patch("skills.watchlist.watchlist_manager.WatchlistManager", return_value=watchlist_mgr), \
         patch("src.managers.insights_manager.InsightsManager"), \
         patch("skills.web_search.searxng_client.get_search_client", return_value=search_client), \
         patch("src.main.authorized_users", {"u1": "phone"}), \
         patch("src.core.config.WORLD_WATCH_INTERVAL_HOURS", 24):

        await hb._process_world_watch()

    search_client.search_news.assert_awaited_once()


@pytest.mark.asyncio
async def test_no_authorized_users_short_circuits():
    """Should never fall back to scanning memory/* directories - only authorized_users."""
    hb = make_manager()

    with patch("src.main.authorized_users", {}):
        result = await hb._process_world_watch()

    assert result is None
    hb._send_message_callback.assert_not_awaited()


@pytest.mark.asyncio
async def test_stock_topic_dispatches_to_check_stock_and_uses_its_own_interval():
    """A kind='stock' topic should use check_stock (not SearXNG) and STOCK_WATCH_INTERVAL_HOURS."""
    hb = make_manager()

    topic = WatchTopic(
        topic_id="t1", topic="AAPL", user_id="u1", kind="stock",
        created_at=datetime.now().isoformat(), last_run_at=None,
    )
    watchlist_mgr = MagicMock()
    watchlist_mgr.get_topics.return_value = [topic]

    with patch("skills.watchlist.watchlist_manager.WatchlistManager", return_value=watchlist_mgr), \
         patch("src.managers.insights_manager.InsightsManager") as insights_cls, \
         patch("src.managers.watch_sources.check_stock", new_callable=AsyncMock) as mock_check_stock, \
         patch("src.main.authorized_users", {"u1": "phone"}):

        mock_check_stock.return_value = {
            "notable": True,
            "summary": "AAPL is up 6% today.",
            "sources": [{"title": "AAPL", "url": "https://finance.yahoo.com/quote/AAPL"}],
        }
        insights_mgr = MagicMock()
        insights_cls.return_value = insights_mgr

        result = await hb._process_world_watch()

    mock_check_stock.assert_awaited_once()
    hb._summarize_world_watch_results.assert_not_awaited()  # stock summaries are deterministic, no LLM call
    insights_mgr.add_insight.assert_called_once()
    hb._send_message_callback.assert_awaited_once()
    assert result is not None and "1 new insight" in result


@pytest.mark.asyncio
async def test_stock_topic_not_notable_sends_nothing():
    """A stock move below threshold should still mark_run but not surface an insight."""
    hb = make_manager()

    topic = WatchTopic(
        topic_id="t1", topic="AAPL", user_id="u1", kind="stock",
        created_at=datetime.now().isoformat(), last_run_at=None,
    )
    watchlist_mgr = MagicMock()
    watchlist_mgr.get_topics.return_value = [topic]

    with patch("skills.watchlist.watchlist_manager.WatchlistManager", return_value=watchlist_mgr), \
         patch("src.managers.insights_manager.InsightsManager") as insights_cls, \
         patch("src.managers.watch_sources.check_stock", new_callable=AsyncMock) as mock_check_stock, \
         patch("src.main.authorized_users", {"u1": "phone"}):

        mock_check_stock.return_value = {"notable": False}
        insights_mgr = MagicMock()
        insights_cls.return_value = insights_mgr

        result = await hb._process_world_watch()

    watchlist_mgr.mark_run.assert_called_once()
    insights_mgr.add_insight.assert_not_called()
    hb._send_message_callback.assert_not_awaited()
    assert result is None


@pytest.mark.asyncio
async def test_github_topic_dispatches_to_check_github_and_persists_markers():
    """A kind='github' topic should use check_github and pass through new markers to mark_run."""
    hb = make_manager()

    topic = WatchTopic(
        topic_id="t1", topic="owner/repo", user_id="u1", kind="github",
        created_at=datetime.now().isoformat(), last_run_at=None,
        seen_urls=["release:v1.0.0"],
    )
    watchlist_mgr = MagicMock()
    watchlist_mgr.get_topics.return_value = [topic]

    with patch("skills.watchlist.watchlist_manager.WatchlistManager", return_value=watchlist_mgr), \
         patch("src.managers.insights_manager.InsightsManager") as insights_cls, \
         patch("src.managers.watch_sources.check_github", new_callable=AsyncMock) as mock_check_github, \
         patch("src.main.authorized_users", {"u1": "phone"}):

        mock_check_github.return_value = {
            "new_markers": ["release:v1.1.0"],
            "new_items": [{"title": "New release v1.1.0 for owner/repo", "url": "https://github.com/owner/repo/releases", "snippet": ""}],
        }
        insights_mgr = MagicMock()
        insights_cls.return_value = insights_mgr

        result = await hb._process_world_watch()

    mock_check_github.assert_awaited_once_with("owner/repo", ["release:v1.0.0"])
    watchlist_mgr.mark_run.assert_called_once()
    mark_run_args = watchlist_mgr.mark_run.call_args.args
    assert mark_run_args[0] == "u1"
    assert mark_run_args[1] == "t1"
    assert mark_run_args[2] == ["release:v1.1.0"]
    insights_mgr.add_insight.assert_called_once()
    hb._send_message_callback.assert_awaited_once()
    assert result is not None and "1 new insight" in result
