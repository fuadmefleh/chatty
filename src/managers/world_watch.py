"""The per-topic world-watch pipeline: fetch -> analyze -> store.

Extracted from HeartbeatManager._process_world_watch so it can be shared by
the three things that trigger it:

  - the heartbeat's scheduled loop (src/managers/heartbeat_manager.py)
  - the dashboard's "scan now" (src/web/routers/insights.py)
  - ad-hoc search (same router, ad_hoc=True)

It lives at module level rather than on HeartbeatManager because chatty-bot
and chatty-web-server are separate processes - the web API has no
HeartbeatManager instance to call into. This mirrors run_trending_scan in
src/managers/trending_manager.py, which exists for the same reason.

scan_topic owns ONE topic's pipeline and nothing else. Deciding *when* to run
(interval gating) and whether to notify (Telegram push) belongs to callers,
which is what lets the heartbeat and the dashboard share this code while
behaving differently.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

from src.core import config
from src.core.logging_config import get_heartbeat_logger

heartbeat_logger = get_heartbeat_logger()

# Outcomes of a single topic scan. Only "stored" produced an insight; the
# rest are the normal, expected ways a scan comes up empty.
SCAN_STATES = (
    "stored",
    "nothing_new",       # fetch succeeded, nothing the user hasn't seen
    "below_threshold",   # analyzed, but too minor to keep (scheduled runs only)
    "fetch_failed",      # source lookup errored - retry next tick
    "analysis_failed",   # the LLM step returned nothing usable
)


@dataclass
class ScanResult:
    """What one topic scan produced.

    A scan yields a LIST of insights: the analyzer clusters the findings into
    distinct storylines and each becomes its own card. `analyses` is exposed
    alongside so the caller can decide about notification - scan_topic
    deliberately doesn't push.
    """
    state: str
    topic: str
    kind: str
    insights: List[object] = field(default_factory=list)
    analyses: List[object] = field(default_factory=list)
    sources: List[Dict] = field(default_factory=list)

    @property
    def stored(self) -> bool:
        return self.state == "stored"


async def _fetch(kind: str, topic: str, seen_markers: List[str]) -> Optional[Dict]:
    """Dispatch to the right source. Returns None if the lookup failed.

    The returned dict is normalized to {items, sources, markers, notable} so
    scan_topic's body doesn't branch on kind a second time.
    """
    from src.managers import watch_sources

    if kind == "stock":
        check = await watch_sources.check_stock(topic, config.STOCK_WATCH_MOVE_THRESHOLD_PERCENT)
        if check is None:
            return None
        if not check.get("notable"):
            # A quiet ticker still counts as a successful check.
            return {"items": [], "sources": [], "markers": [], "notable": False}

        items = [{"title": check["summary"]}]
        sources = check["sources"]
        # The move itself is only half the story - pull recent news on the
        # ticker so the analysis can say WHY.
        items, sources = await _enrich_stock_context(topic, items, sources)
        return {"items": items, "sources": sources, "markers": [], "notable": True}

    if kind == "github":
        check = await watch_sources.check_github(topic, seen_markers)
        if check is None:
            return None
        return {
            "items": check["new_items"],
            "sources": [{"title": i["title"], "url": i["url"]} for i in check["new_items"]],
            "markers": check["new_markers"],
            "notable": bool(check["new_items"]),
        }

    check = await watch_sources.check_news(topic, seen_markers)
    if check is None:
        return None
    return {
        "items": check["new_items"],
        # No cap: each storyline picks its own subset out of this via
        # _sources_for, so truncating here would strip later cards' links.
        "sources": [{"title": r["title"], "url": r["link"]} for r in check["new_items"]],
        "markers": check["all_markers"],
        "notable": bool(check["new_items"]),
    }


async def _enrich_stock_context(
    symbol: str, items: List[Dict], sources: List[Dict]
) -> tuple[List[Dict], List[Dict]]:
    """Attach recent news about a ticker to its price-move finding.

    "AAPL is down 6% today" is a fact, not an insight. Feeding the analyzer
    contemporaneous headlines is what lets it explain the move. Best-effort:
    a failed search degrades the analysis, so it must not cost the insight.
    """
    try:
        from src.managers import watch_sources

        news = await watch_sources.check_news(f"{symbol} stock", [])
        if not news or not news.get("new_items"):
            return items, sources

        fresh = news["new_items"][:5]
        return items + fresh, sources + [{"title": r["title"], "url": r["link"]} for r in fresh[:3]]

    except Exception as e:
        heartbeat_logger.warning(f"Stock news enrichment failed for '{symbol}': {e}")
        return items, sources


def _sources_for(analysis, all_sources: List[Dict]) -> List[Dict]:
    """Narrow a scan's sources to the ones a given storyline drew on.

    Falls back to the full set when the analyzer didn't attribute any URLs -
    showing every source beats showing none, and stock/github findings carry
    a single source anyway.
    """
    if not analysis.source_urls:
        return all_sources

    wanted = set(analysis.source_urls)
    matched = [s for s in all_sources if s.get("url") in wanted]
    return matched or all_sources


async def scan_topic(
    user_id: str,
    kind: str,
    topic: str,
    *,
    topic_id: Optional[str] = None,
    seen_markers: Optional[List[str]] = None,
    watchlist_mgr=None,
    insights_mgr=None,
    ad_hoc: bool = False,
) -> ScanResult:
    """Run the full pipeline for one topic and return what it produced.

    Args:
        topic_id: The watchlist topic being refreshed. Required unless
            ad_hoc - it's what mark_run updates.
        seen_markers: Dedup state. Callers pass [] for ad_hoc so the search
            sees the current state of the world, not just what's new since
            the last scheduled run.
        ad_hoc: A user-initiated one-off rather than a scheduled check. Three
            differences: no mark_run (an ad-hoc search must not consume a
            watchlist topic's schedule state), no significance floor (an
            explicit action should always yield something), and the result is
            flagged ad_hoc so the dashboard can keep it out of the curated
            feed by default.

    Never raises for expected failures - fetch and analysis problems come
    back as a ScanResult state so a caller looping over topics isn't derailed
    by one bad source.
    """
    from src.managers import insight_analyzer

    seen_markers = seen_markers or []

    fetched = await _fetch(kind, topic, seen_markers)
    if fetched is None:
        # Don't advance last_run_at - the check never really happened.
        return ScanResult(state="fetch_failed", topic=topic, kind=kind)

    # The check happened, so record it even when it found nothing. This is
    # what keeps the heartbeat from re-searching before its interval is up.
    if not ad_hoc and topic_id and watchlist_mgr is not None:
        watchlist_mgr.mark_run(user_id, topic_id, fetched["markers"], datetime.now().isoformat())

    if not fetched["notable"]:
        return ScanResult(state="nothing_new", topic=topic, kind=kind)

    prior = insights_mgr.get_insights_by_topic(user_id, topic, config.INSIGHT_PRIOR_CONTEXT_COUNT)
    analyses = await insight_analyzer.analyze(
        kind,
        topic,
        fetched["items"],
        [
            {
                "id": p.id,
                "created_at": p.created_at,
                "headline": p.headline or p.summary[:120],
                "entities": p.entities,
            }
            for p in prior
        ],
    )

    if not analyses:
        return ScanResult(state="analysis_failed", topic=topic, kind=kind)

    # An explicit user action always yields a result; only the scheduled
    # firehose needs a floor to stay signal-dense.
    if not ad_hoc:
        keep = [a for a in analyses if a.significance >= config.INSIGHT_MIN_SIGNIFICANCE_STORE]
        if not keep:
            return ScanResult(state="below_threshold", topic=topic, kind=kind, analyses=analyses)
        analyses = keep

    stored = [
        insights_mgr.add_insight(
            user_id,
            topic,
            analysis.to_summary(),
            _sources_for(analysis, fetched["sources"]),
            kind=kind,
            significance=analysis.significance,
            headline=analysis.headline,
            what_happened=analysis.what_happened,
            why_it_matters=analysis.why_it_matters,
            what_to_watch=analysis.what_to_watch,
            entities=analysis.entities,
            connection=analysis.connection,
            ad_hoc=ad_hoc,
        )
        for analysis in analyses
    ]

    return ScanResult(
        state="stored",
        topic=topic,
        kind=kind,
        insights=stored,
        analyses=analyses,
        sources=fetched["sources"],
    )
