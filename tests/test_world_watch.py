"""Tests for HeartbeatManager._process_world_watch (dedup + interval gating logic)."""
import sys
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.managers.heartbeat_manager import HeartbeatManager
from src.managers.insight_analyzer import Analysis
from skills.watchlist.watchlist_manager import WatchTopic


def make_manager():
    hb = HeartbeatManager(skills_manager=MagicMock())
    hb._send_message_callback = AsyncMock()
    return hb


def make_analysis(significance=4, **kwargs):
    defaults = {
        "headline": "Something notable happened",
        "what_happened": "A thing occurred.",
        "why_it_matters": "It has consequences.",
        "significance": significance,
    }
    defaults.update(kwargs)
    return Analysis(**defaults)


def patch_analyzer(significance=4):
    """Stub the LLM analysis step; tests exercise orchestration, not prompting."""
    return patch(
        "src.managers.insight_analyzer.analyze",
        new_callable=AsyncMock,
        return_value=make_analysis(significance),
    )


def make_insights_mgr():
    """InsightsManager double whose topic history is empty (not a MagicMock)."""
    insights_mgr = MagicMock()
    insights_mgr.get_insights_by_topic.return_value = []
    return insights_mgr


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
         patch("src.main.authorized_users", {"u1": "phone"}), \
         patch_analyzer() as mock_analyze:

        insights_mgr = make_insights_mgr()
        insights_cls.return_value = insights_mgr

        result = await hb._process_world_watch()

    # Only the genuinely new result should reach the analyzer.
    mock_analyze.assert_awaited_once()
    analyzed_items = mock_analyze.await_args.args[2]
    assert [r["link"] for r in analyzed_items] == ["https://c.example"]

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
         patch_analyzer(), \
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
         patch_analyzer(), \
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
         patch("src.managers.watch_sources.check_news", new_callable=AsyncMock, return_value=None), \
         patch("src.main.authorized_users", {"u1": "phone"}), \
         patch_analyzer():

        mock_check_stock.return_value = {
            "notable": True,
            "summary": "AAPL is up 6% today.",
            "sources": [{"title": "AAPL", "url": "https://finance.yahoo.com/quote/AAPL"}],
        }
        insights_mgr = make_insights_mgr()
        insights_cls.return_value = insights_mgr

        result = await hb._process_world_watch()

    mock_check_stock.assert_awaited_once()
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
        insights_mgr = make_insights_mgr()
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
         patch("src.main.authorized_users", {"u1": "phone"}), \
         patch_analyzer():

        mock_check_github.return_value = {
            "new_markers": ["release:v1.1.0"],
            "new_items": [{"title": "New release v1.1.0 for owner/repo", "url": "https://github.com/owner/repo/releases", "snippet": ""}],
        }
        insights_mgr = make_insights_mgr()
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


# ── Significance tiers ───────────────────────────────────────────────────────

def news_topic_setup():
    """A due news topic with one fresh result, plus its collaborator doubles."""
    topic = WatchTopic(
        topic_id="t1", topic="widgets", user_id="u1",
        created_at=datetime.now().isoformat(), last_run_at=None, seen_urls=[],
    )
    watchlist_mgr = MagicMock()
    watchlist_mgr.get_topics.return_value = [topic]

    search_client = MagicMock()
    search_client.search_news = AsyncMock(return_value=make_search_result(["https://a.example"]))
    return watchlist_mgr, search_client


async def run_with_significance(hb, significance):
    watchlist_mgr, search_client = news_topic_setup()

    with patch("skills.watchlist.watchlist_manager.WatchlistManager", return_value=watchlist_mgr), \
         patch("src.managers.insights_manager.InsightsManager") as insights_cls, \
         patch("skills.web_search.searxng_client.get_search_client", return_value=search_client), \
         patch("src.main.authorized_users", {"u1": "phone"}), \
         patch_analyzer(significance):

        insights_mgr = make_insights_mgr()
        insights_cls.return_value = insights_mgr
        result = await hb._process_world_watch()

    return insights_mgr, result


@pytest.mark.asyncio
async def test_significance_1_is_not_stored():
    """Tier 1 is the spam/recycled floor - it replaces the old NOTHING_NOTABLE drop."""
    hb = make_manager()
    insights_mgr, result = await run_with_significance(hb, 1)

    insights_mgr.add_insight.assert_not_called()
    hb._send_message_callback.assert_not_awaited()
    assert result is None


@pytest.mark.asyncio
async def test_significance_3_is_stored_but_not_pushed():
    """Minor findings belong in the dashboard feed without interrupting the user."""
    hb = make_manager()
    insights_mgr, result = await run_with_significance(hb, 3)

    insights_mgr.add_insight.assert_called_once()
    assert insights_mgr.add_insight.call_args.kwargs["significance"] == 3
    hb._send_message_callback.assert_not_awaited()
    assert result is not None and "1 new insight" in result


@pytest.mark.asyncio
async def test_significance_4_is_stored_and_pushed():
    hb = make_manager()
    insights_mgr, _ = await run_with_significance(hb, 4)

    insights_mgr.add_insight.assert_called_once()
    hb._send_message_callback.assert_awaited_once()


@pytest.mark.asyncio
async def test_structured_fields_are_persisted():
    """The whole point of the analyzer - its output must survive to storage."""
    hb = make_manager()
    watchlist_mgr, search_client = news_topic_setup()

    analysis = make_analysis(
        significance=4,
        headline="Widgets consolidate",
        what_happened="Two makers merged.",
        why_it_matters="Pricing power shifts.",
        what_to_watch=["Regulatory response"],
        entities=["AcmeCorp"],
    )

    with patch("skills.watchlist.watchlist_manager.WatchlistManager", return_value=watchlist_mgr), \
         patch("src.managers.insights_manager.InsightsManager") as insights_cls, \
         patch("skills.web_search.searxng_client.get_search_client", return_value=search_client), \
         patch("src.main.authorized_users", {"u1": "phone"}), \
         patch("src.managers.insight_analyzer.analyze", new_callable=AsyncMock, return_value=analysis):

        insights_mgr = make_insights_mgr()
        insights_cls.return_value = insights_mgr
        await hb._process_world_watch()

    kwargs = insights_mgr.add_insight.call_args.kwargs
    assert kwargs["headline"] == "Widgets consolidate"
    assert kwargs["why_it_matters"] == "Pricing power shifts."
    assert kwargs["what_to_watch"] == ["Regulatory response"]
    assert kwargs["entities"] == ["AcmeCorp"]
    assert kwargs["kind"] == "news"


@pytest.mark.asyncio
async def test_prior_insights_are_passed_to_analyzer():
    """Continuity depends on the analyzer seeing what was already surfaced."""
    hb = make_manager()
    watchlist_mgr, search_client = news_topic_setup()

    prior = MagicMock(
        id="prior-1", created_at="2026-07-01T00:00:00", headline="Earlier widget news", entities=["AcmeCorp"]
    )

    with patch("skills.watchlist.watchlist_manager.WatchlistManager", return_value=watchlist_mgr), \
         patch("src.managers.insights_manager.InsightsManager") as insights_cls, \
         patch("skills.web_search.searxng_client.get_search_client", return_value=search_client), \
         patch("src.main.authorized_users", {"u1": "phone"}), \
         patch_analyzer() as mock_analyze:

        insights_mgr = make_insights_mgr()
        insights_mgr.get_insights_by_topic.return_value = [prior]
        insights_cls.return_value = insights_mgr
        await hb._process_world_watch()

    passed_prior = mock_analyze.await_args.args[3]
    assert passed_prior == [{
        "id": "prior-1",
        "created_at": "2026-07-01T00:00:00",
        "headline": "Earlier widget news",
        "entities": ["AcmeCorp"],
    }]
