"""Webcam discovery: Chatty searches (via the already-integrated SearXNG
instance) for pages likely to mention or link a live public webcam - Reddit
threads, forum posts, city/DOT traffic-camera portals - and asks an LLM to
curate a short list of best-effort suggestions worth a human's review.

Nothing here ever adds a source automatically - run_webcam_discovery_scan()
only proposes. A suggestion only becomes a real WebcamSource when a human
picks "Approve" on the dashboard (see chatty_web_server.py's
/api/chatty/webcam-suggestions/{id}/approve endpoint).

Flow, driven by HeartbeatManager._process_webcam_discovery():
1. _run_discovery_searches() - run each configured query through SearXNG's
   JSON search API (general web search, not a real crawl - SearXNG is a
   meta search engine, so "crawling Reddit/forums" means targeted queries
   like `site:reddit.com live traffic camera`).
2. Dedup against every discovered_url ever suggested, and against existing
   source URLs, so the same page isn't re-proposed every cycle.
3. _curate_suggestions() - LLM picks which surviving results plausibly link
   to (or describe) a genuine live webcam, with a best-effort guess at the
   actual name/url/kind/location plus a one-line rationale.
4. run_webcam_discovery_scan() stores the curated ideas as pending
   suggestions.
"""
import json
import re
from typing import Dict, List, Optional

from src.core import config
from src.core.logging_config import get_heartbeat_logger
from src.managers.webcam_manager import WEBCAM_KINDS, WebcamSourcesManager, WebcamSuggestionsManager
from skills.web_search.searxng_client import get_search_client

logger = get_heartbeat_logger()


def _parse_queries(raw: str) -> List[str]:
    return [q.strip() for q in raw.split(";") if q.strip()]


async def _run_discovery_searches(queries: List[str], per_query: int) -> List[Dict]:
    """Run each query through SearXNG and flatten the results."""
    client = get_search_client()
    if not client.is_configured():
        logger.warning("Webcam discovery skipped: SearXNG not configured (SEARXNG_BASE_URL).")
        return []

    candidates: List[Dict] = []
    for query in queries:
        try:
            result = await client.search(query, num_results=per_query, categories="general")
            if not result.get("success"):
                logger.warning(f"Webcam discovery search failed for '{query}': {result.get('error')}")
                continue
            for item in result.get("results", []):
                candidates.append({
                    "title": item.get("title", ""),
                    "link": item.get("link", ""),
                    "snippet": item.get("snippet", ""),
                    "query": query,
                })
        except Exception as e:
            logger.error(f"Webcam discovery search errored for '{query}': {e}", exc_info=True)

    return candidates


def _extract_json_array(text: str) -> Optional[list]:
    """Best-effort JSON-array parse: try the whole reply first, then fall
    back to the first [...] substring in case the model wrapped it in prose
    or a code fence."""
    text = text.strip()
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        pass

    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except (json.JSONDecodeError, ValueError):
        return None


async def _curate_suggestions(candidates: List[Dict], max_suggestions: int) -> List[Dict]:
    """Ask the LLM which search results plausibly link to a genuine live
    public webcam, and to best-effort extract structured details for each."""
    if not candidates:
        return []

    try:
        from openai import AsyncOpenAI

        candidates_text = "\n".join(
            f"- title: {c['title']!r}\n  link: {c['link']}\n  snippet: {c['snippet']!r}"
            for c in candidates
        )

        prompt = f"""You are Chatty, a personal AI assistant, looking for live public webcams (traffic
cams, city/tourism live views, etc.) to add to a watch list, as part of your autonomous heartbeat.
Below are web search results from queries targeting Reddit threads, forums, and general web pages
that might mention or link to one.

Search results:
{candidates_text}

Most of these results will be irrelevant noise (discussions, unrelated pages, dead links you can't
verify). Pick at most {max_suggestions} that plausibly describe or link to an actual live, public
webcam feed - it's fine to pick fewer than {max_suggestions} or none at all if nothing qualifies.

Reply with ONLY a JSON array (no prose, no code fences), where each element is:
{{"name": "<short descriptive name, e.g. 'Times Square DOT Cam'>",
  "url": "<your best guess at the actual camera/stream URL - use the link above if you can't tell "
  "a more specific one from the snippet>",
  "kind": "<one of: {', '.join(WEBCAM_KINDS)} - your best guess, default 'webpage' if unclear>",
  "location": "<place name if discernible, else empty string>",
  "rationale": "<one sentence on why this looks like a genuine live webcam>",
  "discovered_url": "<the exact 'link' value above this suggestion came from>"}}

If nothing listed plausibly qualifies, reply with exactly: []"""

        client = AsyncOpenAI(api_key=config.CHAT_API_KEY, base_url=config.CHAT_BASE_URL)
        response = await client.chat.completions.create(
            model=config.CHAT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )

        text = (response.choices[0].message.content or "").strip()
        ideas = _extract_json_array(text)
        if not ideas:
            return []

        links = {c["link"] for c in candidates}
        curated = []
        for idea in ideas[:max_suggestions]:
            if not isinstance(idea, dict):
                continue
            if idea.get("discovered_url") not in links:
                continue
            if not idea.get("name") or not idea.get("url"):
                continue
            curated.append({
                "name": idea["name"],
                "url": idea["url"],
                "kind": idea.get("kind") if idea.get("kind") in WEBCAM_KINDS else "webpage",
                "location": idea.get("location", ""),
                "rationale": idea.get("rationale", ""),
                "discovered_url": idea["discovered_url"],
            })
        return curated

    except Exception as e:
        logger.error(f"Error curating webcam suggestions: {e}", exc_info=True)
        return []


async def run_webcam_discovery_scan(
    sources_manager: WebcamSourcesManager,
    suggestions_manager: WebcamSuggestionsManager,
) -> Optional[str]:
    """Search for candidate webcam pages, curate ideas, and store any new
    ones as pending suggestions. Returns a one-line summary, or None if
    nothing new was found."""
    queries = _parse_queries(config.WEBCAM_DISCOVERY_QUERIES)
    candidates = await _run_discovery_searches(queries, config.WEBCAM_DISCOVERY_RESULTS_PER_QUERY)

    already_seen = suggestions_manager.seen_discovered_urls()
    existing_urls = {s.url for s in sources_manager.list()}
    new_candidates = [
        c for c in candidates
        if c["link"] and c["link"] not in already_seen and c["link"] not in existing_urls
    ]
    if not new_candidates:
        return None

    ideas = await _curate_suggestions(new_candidates, config.WEBCAM_DISCOVERY_MAX_SUGGESTIONS_PER_SCAN)
    if not ideas:
        return None

    for idea in ideas:
        suggestions_manager.create(
            name=idea["name"],
            url=idea["url"],
            discovered_url=idea["discovered_url"],
            kind=idea["kind"],
            location=idea["location"],
            rationale=idea["rationale"],
        )

    names = ", ".join(idea["name"] for idea in ideas)
    return f"Found {len(ideas)} new webcam suggestion(s): {names}."
