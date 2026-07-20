"""Tests for src/managers/world_watch.scan_topic - the per-topic pipeline.

scan_topic is the shared unit behind all three triggers: the heartbeat's
scheduled run, the dashboard's "scan now", and ad-hoc search. It owns
fetch -> analyze -> store for ONE topic and deliberately does not decide
when to run or whether to notify - those belong to its callers.
"""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.managers import world_watch
from src.managers.insight_analyzer import Analysis


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
    return patch(
        "src.managers.insight_analyzer.analyze",
        new_callable=AsyncMock,
        return_value=make_analysis(significance),
    )


def make_managers():
    watchlist_mgr = MagicMock()
    insights_mgr = MagicMock()
    insights_mgr.get_insights_by_topic.return_value = []
    return watchlist_mgr, insights_mgr


async def scan_news(watchlist_mgr, insights_mgr, *, new_items=None, ad_hoc=False, significance=4):
    """Run a news scan with check_news stubbed to return `new_items`."""
    if new_items is None:
        new_items = [{"title": "Fresh", "link": "https://c.example", "snippet": "s"}]

    with patch(
        "src.managers.watch_sources.check_news",
        new_callable=AsyncMock,
        return_value={"new_items": new_items, "all_markers": [r["link"] for r in new_items]},
    ), patch_analyzer(significance):
        return await world_watch.scan_topic(
            "u1", "news", "widgets",
            topic_id="t1", seen_markers=[],
            watchlist_mgr=watchlist_mgr, insights_mgr=insights_mgr,
            ad_hoc=ad_hoc,
        )


# ── Happy paths, one per kind ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_news_scan_stores_insight():
    watchlist_mgr, insights_mgr = make_managers()

    result = await scan_news(watchlist_mgr, insights_mgr)

    assert result.state == "stored"
    insights_mgr.add_insight.assert_called_once()
    assert insights_mgr.add_insight.call_args.kwargs["kind"] == "news"


@pytest.mark.asyncio
async def test_stock_scan_dispatches_to_check_stock():
    watchlist_mgr, insights_mgr = make_managers()

    with patch("src.managers.watch_sources.check_stock", new_callable=AsyncMock) as check_stock, \
         patch("src.managers.watch_sources.check_news", new_callable=AsyncMock, return_value=None), \
         patch_analyzer():
        check_stock.return_value = {
            "notable": True,
            "summary": "AAPL is up 6% today.",
            "sources": [{"title": "AAPL", "url": "https://finance.yahoo.com/quote/AAPL"}],
        }
        result = await world_watch.scan_topic(
            "u1", "stock", "AAPL",
            topic_id="t1", seen_markers=[],
            watchlist_mgr=watchlist_mgr, insights_mgr=insights_mgr,
        )

    check_stock.assert_awaited_once()
    assert result.state == "stored"
    insights_mgr.add_insight.assert_called_once()


@pytest.mark.asyncio
async def test_github_scan_passes_new_markers_to_mark_run():
    watchlist_mgr, insights_mgr = make_managers()

    with patch("src.managers.watch_sources.check_github", new_callable=AsyncMock) as check_github, \
         patch_analyzer():
        check_github.return_value = {
            "new_markers": ["release:v1.1.0"],
            "new_items": [{"title": "v1.1.0", "url": "https://github.com/o/r/releases", "snippet": ""}],
        }
        result = await world_watch.scan_topic(
            "u1", "github", "owner/repo",
            topic_id="t1", seen_markers=["release:v1.0.0"],
            watchlist_mgr=watchlist_mgr, insights_mgr=insights_mgr,
        )

    check_github.assert_awaited_once_with("owner/repo", ["release:v1.0.0"])
    assert watchlist_mgr.mark_run.call_args.args[2] == ["release:v1.1.0"]
    assert result.state == "stored"


# ── Non-storing outcomes ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fetch_failure_does_not_advance_last_run_at():
    """A failed lookup must be retried next tick, not marked as run."""
    watchlist_mgr, insights_mgr = make_managers()

    with patch("src.managers.watch_sources.check_news", new_callable=AsyncMock, return_value=None):
        result = await world_watch.scan_topic(
            "u1", "news", "widgets",
            topic_id="t1", seen_markers=[],
            watchlist_mgr=watchlist_mgr, insights_mgr=insights_mgr,
        )

    assert result.state == "fetch_failed"
    watchlist_mgr.mark_run.assert_not_called()
    insights_mgr.add_insight.assert_not_called()


@pytest.mark.asyncio
async def test_no_new_items_marks_run_but_stores_nothing():
    watchlist_mgr, insights_mgr = make_managers()

    result = await scan_news(watchlist_mgr, insights_mgr, new_items=[])

    assert result.state == "nothing_new"
    watchlist_mgr.mark_run.assert_called_once()
    insights_mgr.add_insight.assert_not_called()


@pytest.mark.asyncio
async def test_analysis_failure_is_reported():
    watchlist_mgr, insights_mgr = make_managers()

    with patch(
        "src.managers.watch_sources.check_news",
        new_callable=AsyncMock,
        return_value={"new_items": [{"title": "x", "link": "https://a.example"}], "all_markers": []},
    ), patch("src.managers.insight_analyzer.analyze", new_callable=AsyncMock, return_value=None):
        result = await world_watch.scan_topic(
            "u1", "news", "widgets",
            topic_id="t1", seen_markers=[],
            watchlist_mgr=watchlist_mgr, insights_mgr=insights_mgr,
        )

    assert result.state == "analysis_failed"
    insights_mgr.add_insight.assert_not_called()


@pytest.mark.asyncio
async def test_below_threshold_significance_is_not_stored():
    watchlist_mgr, insights_mgr = make_managers()

    result = await scan_news(watchlist_mgr, insights_mgr, significance=1)

    assert result.state == "below_threshold"
    insights_mgr.add_insight.assert_not_called()


# ── Ad-hoc semantics ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ad_hoc_never_marks_run():
    """An ad-hoc search must not consume a watchlist topic's schedule state."""
    watchlist_mgr, insights_mgr = make_managers()

    await scan_news(watchlist_mgr, insights_mgr, ad_hoc=True)

    watchlist_mgr.mark_run.assert_not_called()


@pytest.mark.asyncio
async def test_ad_hoc_bypasses_the_significance_gate():
    """An explicit user action always yields a result, even on a quiet day."""
    watchlist_mgr, insights_mgr = make_managers()

    result = await scan_news(watchlist_mgr, insights_mgr, ad_hoc=True, significance=1)

    assert result.state == "stored"
    insights_mgr.add_insight.assert_called_once()


@pytest.mark.asyncio
async def test_ad_hoc_insights_are_flagged():
    watchlist_mgr, insights_mgr = make_managers()

    await scan_news(watchlist_mgr, insights_mgr, ad_hoc=True)

    assert insights_mgr.add_insight.call_args.kwargs["ad_hoc"] is True


@pytest.mark.asyncio
async def test_scheduled_insights_are_not_flagged_ad_hoc():
    watchlist_mgr, insights_mgr = make_managers()

    await scan_news(watchlist_mgr, insights_mgr)

    assert insights_mgr.add_insight.call_args.kwargs["ad_hoc"] is False


@pytest.mark.asyncio
async def test_prior_insights_are_passed_to_analyzer():
    """Continuity works for ad-hoc searches too, not just scheduled runs."""
    watchlist_mgr, insights_mgr = make_managers()
    insights_mgr.get_insights_by_topic.return_value = [
        MagicMock(id="p1", created_at="2026-07-01T00:00:00", headline="Earlier", entities=["Acme"])
    ]

    with patch(
        "src.managers.watch_sources.check_news",
        new_callable=AsyncMock,
        return_value={"new_items": [{"title": "x", "link": "https://a.example"}], "all_markers": []},
    ), patch_analyzer() as analyze:
        await world_watch.scan_topic(
            "u1", "news", "widgets",
            topic_id="t1", seen_markers=[],
            watchlist_mgr=watchlist_mgr, insights_mgr=insights_mgr,
            ad_hoc=True,
        )

    assert analyze.await_args.args[3] == [
        {"id": "p1", "created_at": "2026-07-01T00:00:00", "headline": "Earlier", "entities": ["Acme"]}
    ]
