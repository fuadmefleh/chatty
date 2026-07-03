"""Source-specific checkers for World Watch topics.

Each check_* function takes a topic's stored state (dedup markers) and
returns a normalized result HeartbeatManager._process_world_watch can act on
without needing to know the details of any particular source. "Markers" are
opaque strings used for dedup (news result URLs, "release:<tag>",
"commit:<sha>") - WatchTopic.seen_urls stores whichever kind its own source
produces.
"""
from typing import Any, Dict, List, Optional

import httpx

from src.core import config
from src.core.logging_config import get_heartbeat_logger

logger = get_heartbeat_logger()

GITHUB_API_BASE = "https://api.github.com"
GITHUB_HEADERS = {"Accept": "application/vnd.github+json", "User-Agent": "chatty-world-watch"}


async def check_news(topic: str, seen_markers: List[str]) -> Optional[Dict[str, Any]]:
    """Search for fresh news on a free-text topic via SearXNG.

    Returns a dict with `new_markers` (URLs) and `new_items` (title/link/
    snippet), or None if the search failed outright (topic stays "checked"
    either way via the caller - only a hard failure returns None so the
    caller can decide whether to skip advancing last_run_at).
    """
    from skills.web_search.searxng_client import get_search_client

    client = get_search_client()
    result = await client.search_news(topic, num_results=8)

    if not result.get("success"):
        logger.warning(f"World watch news search failed for '{topic}': {result.get('error')}")
        return None

    all_markers = [r["link"] for r in result["results"]]
    new_items = [r for r in result["results"] if r["link"] not in seen_markers]

    return {"all_markers": all_markers, "new_items": new_items}


async def check_stock(symbol: str, threshold_percent: float) -> Optional[Dict[str, Any]]:
    """Check a ticker for a day move beyond threshold_percent (either direction).

    Stock watches don't need a dedup marker - each check just asks "is
    today's move notable right now", so there's nothing to persist beyond
    last_run_at (used purely for the check-interval gate).
    """
    from skills.stocks.yahoo_client import get_ticker_info

    info = await get_ticker_info(symbol)
    if not info.get("success"):
        logger.warning(f"World watch stock lookup failed for '{symbol}': {info.get('error')}")
        return None

    pct = info.get("day_change_percent") or 0
    if abs(pct) < threshold_percent:
        return {"notable": False}

    direction = "up" if pct > 0 else "down"
    summary = (
        f"{info.get('name', symbol)} ({symbol}) is {direction} {abs(pct):.2f}% today, "
        f"now trading at ${info.get('price')} ({'+' if info.get('day_change', 0) >= 0 else ''}{info.get('day_change')})."
    )
    return {
        "notable": True,
        "summary": summary,
        "sources": [{"title": f"{symbol} on Yahoo Finance", "url": f"https://finance.yahoo.com/quote/{symbol}"}],
    }


async def check_github(repo: str, seen_markers: List[str]) -> Optional[Dict[str, Any]]:
    """Check a "owner/repo" string for a new release or new default-branch commit.

    Uses GitHub's unauthenticated public API (fine for a handful of repos at
    a low check frequency; rate limit is 60 req/hr per IP).
    """
    repo = repo.strip().strip("/")
    if "/" not in repo:
        logger.warning(f"World watch github topic '{repo}' is not in 'owner/repo' form")
        return None

    try:
        async with httpx.AsyncClient(timeout=15.0, headers=GITHUB_HEADERS) as client:
            new_markers: List[str] = []
            notable_items = []

            release_resp = await client.get(f"{GITHUB_API_BASE}/repos/{repo}/releases/latest")
            if release_resp.status_code == 200:
                release = release_resp.json()
                tag = release.get("tag_name", "")
                marker = f"release:{tag}"
                if tag and marker not in seen_markers:
                    new_markers.append(marker)
                    notable_items.append({
                        "title": f"New release {tag} for {repo}",
                        "url": release.get("html_url", f"https://github.com/{repo}/releases"),
                        "snippet": (release.get("body") or "")[:300],
                    })

            commits_resp = await client.get(f"{GITHUB_API_BASE}/repos/{repo}/commits", params={"per_page": 1})
            if commits_resp.status_code == 200:
                commits = commits_resp.json()
                if commits:
                    sha = commits[0].get("sha", "")[:12]
                    marker = f"commit:{sha}"
                    if sha and marker not in seen_markers:
                        new_markers.append(marker)
                        message = (commits[0].get("commit", {}).get("message") or "").splitlines()[0]
                        notable_items.append({
                            "title": f"Latest commit on {repo}: {message}",
                            "url": commits[0].get("html_url", f"https://github.com/{repo}/commits"),
                            "snippet": message,
                        })

            if release_resp.status_code not in (200, 404) or commits_resp.status_code not in (200, 404):
                logger.warning(
                    f"World watch github check for '{repo}' got unexpected status "
                    f"(release={release_resp.status_code}, commits={commits_resp.status_code})"
                )
                return None

            return {"new_markers": new_markers, "new_items": notable_items}

    except Exception as e:
        logger.error(f"World watch github check failed for '{repo}': {e}", exc_info=True)
        return None
