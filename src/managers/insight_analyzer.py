"""LLM analysis for World Watch insights.

Turns raw per-source findings (news results, a stock move, GitHub release
notes) into a structured, graded Analysis. This is deliberately separate from
HeartbeatManager: the heartbeat orchestrates (fetch -> analyze -> store ->
notify) and this module owns everything about *how* an insight gets its
depth, so neither file has to grow the other's concerns.

The significance score replaces the old binary NOTHING_NOTABLE gate. Instead
of discarding anything that isn't clearly notable, the model grades 1-5 and
the caller decides what to store and what to push - see
config.INSIGHT_MIN_SIGNIFICANCE_STORE / INSIGHT_PUSH_MIN_SIGNIFICANCE.

analyze() returns a LIST because a topic's fresh findings usually contain
several unrelated stories. Collapsing them into one insight (the original
behaviour) meant a broad topic like "ai" produced a single vague card per
scan no matter how much was going on; clustering into storylines is what
makes the feed reflect the actual volume of news.
"""
import asyncio
import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.core import config
from src.core.logging_config import get_heartbeat_logger

logger = get_heartbeat_logger()

VALID_RELATIONS = {"follows_up", "contradicts", "escalates"}

# Significance assigned when the model returns text we can't parse as JSON.
# Low enough to stay out of push notifications, high enough to still be
# stored - a degraded insight beats a silently dropped one.
FALLBACK_SIGNIFICANCE = 2


@dataclass
class Analysis:
    """A graded, structured insight ready to be persisted."""

    headline: str
    what_happened: str
    significance: int
    why_it_matters: str = ""
    what_to_watch: List[str] = field(default_factory=list)
    entities: List[str] = field(default_factory=list)
    connection: Optional[Dict[str, str]] = None
    # The subset of the scan's findings this particular storyline came from,
    # so each card links only its own articles instead of all of them.
    source_urls: List[str] = field(default_factory=list)

    def to_summary(self) -> str:
        """Flatten to the plain-text `summary` field.

        Kept because the daily briefing and the outgoing chat message both
        consume a single string, and because legacy insights only have this.
        """
        parts = [self.headline, "", self.what_happened]

        if self.why_it_matters:
            parts += ["", f"Why it matters: {self.why_it_matters}"]

        if self.connection and self.connection.get("note"):
            parts += ["", f"Context: {self.connection['note']}"]

        if self.what_to_watch:
            parts += ["", "What to watch:"] + [f"• {w}" for w in self.what_to_watch]

        return "\n".join(parts).strip()


def _format_prior(prior_insights: List[Dict[str, Any]]) -> str:
    if not prior_insights:
        return "(no earlier insights on this topic)"

    lines = []
    for p in prior_insights:
        entities = ", ".join(p.get("entities") or [])
        line = f"- id={p['id']} ({p.get('created_at', '')[:10]}): {p.get('headline') or p.get('summary', '')[:120]}"
        if entities:
            line += f" [entities: {entities}]"
        lines.append(line)
    return "\n".join(lines)


def _format_items(items: List[Dict[str, Any]]) -> str:
    """Render findings for the prompt.

    Sources normalize to title/snippet/url dicts, but a plain string is
    accepted too - a stock move is a single prewritten sentence with no URL
    of its own.
    """
    lines = []
    for i in items:
        if not isinstance(i, dict):
            lines.append(f"- {i}")
            continue

        line = f"- {i.get('title', '')}"
        snippet = (i.get("snippet") or "").strip()
        if snippet:
            line += f": {snippet}"
        url = i.get("link") or i.get("url") or ""
        if url:
            line += f" ({url})"
        lines.append(line)
    return "\n".join(lines)


_KIND_FRAMING = {
    "news": (
        "new search results about a topic the user follows",
        "Focus on what genuinely changed and what a well-informed follower of this "
        "topic would want to know that they wouldn't already assume.",
    ),
    "stock": (
        "a notable single-day price move for a ticker the user follows, plus recent "
        "news that may explain it",
        "Explain WHY the stock moved if the news supports a explanation, and say so "
        "plainly if it doesn't. Do not invent a cause.",
    ),
    "github": (
        "new releases and commits on a repository the user follows",
        "Say what actually changed for someone who uses this repo - breaking changes, "
        "new capabilities, notable fixes. Ignore routine chore/CI commits.",
    ),
}


def _build_cluster_prompt(topic: str, items: List[Dict[str, Any]]) -> str:
    """Phase 1: group findings into storylines. Deliberately cheap.

    Asks only for a label and the URLs in each group - no analysis - so the
    output stays short and this call stays fast.
    """
    return f"""Below are fresh findings about the topic "{topic}".

FINDINGS:
{_format_items(items)}

Group them into DISTINCT STORYLINES. Findings about the same development
belong in one group; unrelated developments must go in separate groups. Use
at most {config.INSIGHT_MAX_PER_SCAN} groups, most newsworthy first. Ignore
findings that are spam, off-topic, or content-free rather than forcing them
into a group. If everything really is one story, return one group.

Respond with ONLY this JSON, no prose and no code fences:

{{
  "storylines": [
    {{
      "label": "a few words naming this storyline",
      "source_urls": ["the exact URLs from FINDINGS in this group"]
    }}
  ]
}}"""


def _build_prompt(kind: str, topic: str, items: List[Dict[str, Any]], prior_insights: List[Dict[str, Any]]) -> str:
    """Phase 2: full structured analysis of ONE storyline.

    Handles a single story per call. A previous version asked for all five
    insights in one response, which on a local model meant a slow ~2500-token
    generation whose quality drifted toward the end.
    """
    subject, guidance = _KIND_FRAMING.get(kind, _KIND_FRAMING["news"])

    return f"""You are analyzing {subject}.

TOPIC: {topic}

THE FINDINGS FOR THIS STORY:
{_format_items(items)}

EARLIER INSIGHTS YOU ALREADY SURFACED ON THIS TOPIC (most recent first):
{_format_prior(prior_insights)}

{guidance}

These findings are about ONE story. Write ONE insight covering it.

Respond with ONLY a JSON object, no prose and no code fences:

{{
  "headline": "one specific sentence, under 90 characters, no hype",
  "what_happened": "2-4 sentences of concrete fact",
  "why_it_matters": "2-4 sentences of analysis - implications, second-order effects, who is affected",
  "what_to_watch": ["1-3 short forward-looking items"],
  "entities": ["key companies, people, products or repos named"],
  "significance": 1-5,
  "connection": null
}}

SIGNIFICANCE SCALE - be honest, most things are not a 5:
  1 = spam, recycled/old content, or irrelevant to the topic
  2 = minor, only worth a glance
  3 = solid, real development
  4 = notable, the user should know about this soon
  5 = major, changes the picture for this topic

If (and only if) this story genuinely relates to one of the earlier insights
listed above, set "connection" to:
  {{"prior_insight_id": "<the exact id>", "relation": "follows_up|contradicts|escalates", "note": "one sentence on the link"}}
Otherwise leave "connection" as null. Do not invent a connection to fill the field."""


def _extract_json(text: str) -> Optional[Any]:
    """Pull JSON out of a model response, tolerating code fences.

    Accepts an array as well as an object - the prompt asks for a wrapper
    object, but models routinely answer a list-shaped request with a bare
    list, and that content is perfectly usable.
    """
    text = text.strip()

    fenced = re.search(r"```(?:json)?\s*([\{\[].*?[\}\]])\s*```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    else:
        braced = re.search(r"[\{\[].*[\}\]]", text, re.DOTALL)
        if braced:
            text = braced.group(0)

    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, (dict, list)) else None
    except (json.JSONDecodeError, ValueError):
        return None


def _coerce_str_list(value: Any, limit: int) -> List[str]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    return [str(v).strip() for v in value if str(v).strip()][:limit]


def _validate_connection(raw: Any, prior_insights: List[Dict[str, Any]]) -> Optional[Dict[str, str]]:
    """Keep a connection only if it points at a real prior insight.

    The model is asked for a nullable field, so a hallucinated id means the
    link is fabricated - dropping it is safer than rendering a dead
    reference in the UI.
    """
    if not isinstance(raw, dict):
        return None

    prior_id = str(raw.get("prior_insight_id") or "")
    if not prior_id or prior_id not in {p["id"] for p in prior_insights}:
        return None

    relation = str(raw.get("relation") or "follows_up")
    if relation not in VALID_RELATIONS:
        relation = "follows_up"

    return {
        "prior_insight_id": prior_id,
        "relation": relation,
        "note": str(raw.get("note") or "").strip(),
    }


def _known_urls(items: List[Dict[str, Any]]) -> set:
    urls = set()
    for i in items:
        if isinstance(i, dict):
            url = i.get("link") or i.get("url")
            if url:
                urls.add(url)
    return urls


def _build_analysis(
    parsed: Dict[str, Any],
    topic: str,
    prior_insights: List[Dict[str, Any]],
    known_urls: set,
) -> Analysis:
    try:
        significance = int(parsed.get("significance", FALLBACK_SIGNIFICANCE))
    except (TypeError, ValueError):
        significance = FALLBACK_SIGNIFICANCE
    significance = max(1, min(5, significance))

    what_happened = str(parsed.get("what_happened") or "").strip()
    headline = str(parsed.get("headline") or "").strip() or (what_happened[:90] or topic)

    # Keep only URLs that were actually in the findings - a paraphrased or
    # invented link would render as a dead source on the card.
    source_urls = [u for u in _coerce_str_list(parsed.get("source_urls"), limit=10) if u in known_urls]

    return Analysis(
        headline=headline,
        what_happened=what_happened,
        why_it_matters=str(parsed.get("why_it_matters") or "").strip(),
        what_to_watch=_coerce_str_list(parsed.get("what_to_watch"), limit=5),
        entities=_coerce_str_list(parsed.get("entities"), limit=10),
        significance=significance,
        connection=_validate_connection(parsed.get("connection"), prior_insights),
        source_urls=source_urls,
    )


def _storyline_dicts(parsed: Any) -> List[Dict[str, Any]]:
    """Pull the storyline groups out of whatever shape the model returned."""
    if isinstance(parsed, dict):
        raw = parsed.get("storylines")
        if isinstance(raw, list):
            return [s for s in raw if isinstance(s, dict)]
        return []
    if isinstance(parsed, list):
        return [s for s in parsed if isinstance(s, dict)]
    return []


def _degraded(text: str, topic: str) -> Optional[Analysis]:
    """Wrap unparseable model output rather than losing the insight."""
    text = text.strip()
    if not text:
        return None

    logger.warning(f"Insight analysis for '{topic}' returned unparseable JSON; storing degraded insight")
    return Analysis(
        headline=text.split("\n")[0][:90] or topic,
        what_happened=text,
        significance=FALLBACK_SIGNIFICANCE,
    )


async def _complete(prompt: str) -> Optional[str]:
    """One chat completion. Returns None if the call failed or came back empty."""
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=config.CHAT_API_KEY, base_url=config.CHAT_BASE_URL)

    response = await client.chat.completions.create(
        model=config.CHAT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )
    return (response.choices[0].message.content or "").strip() or None


async def _cluster(topic: str, items: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
    """Phase 1: split findings into per-storyline groups of items.

    Falls back to a single group covering everything whenever grouping fails
    or produces nothing usable - a scan that yields one insight is a far
    better outcome than one that yields none.
    """
    if len(items) <= 1:
        return [items]

    try:
        content = await _complete(_build_cluster_prompt(topic, items))
        if content is None:
            return [items]

        groups = _storyline_dicts(_extract_json(content))
        if not groups:
            logger.warning(f"Clustering for '{topic}' returned no storylines; treating findings as one story")
            return [items]

        by_url = {}
        for i in items:
            url = i.get("link") or i.get("url")
            if url:
                by_url[url] = i

        clustered = []
        for group in groups[:config.INSIGHT_MAX_PER_SCAN]:
            members = [by_url[u] for u in _coerce_str_list(group.get("source_urls"), limit=25) if u in by_url]
            if members:
                clustered.append(members)

        return clustered or [items]

    except Exception as e:
        logger.error(f"Clustering failed for '{topic}': {e}", exc_info=True)
        return [items]


async def _analyze_one(
    kind: str,
    topic: str,
    items: List[Dict[str, Any]],
    prior_insights: List[Dict[str, Any]],
) -> Optional[Analysis]:
    """Phase 2: one focused LLM call producing one insight."""
    try:
        content = await _complete(_build_prompt(kind, topic, items, prior_insights))
        if content is None:
            return None

        parsed = _extract_json(content)
        if not isinstance(parsed, dict):
            return _degraded(content, topic)

        analysis = _build_analysis(parsed, topic, prior_insights, _known_urls(items))
        if not (analysis.what_happened or analysis.headline):
            return None

        # Attribution comes from the clustering step, not the model's word -
        # these are exactly the findings this call was given.
        analysis.source_urls = [u for u in (i.get("link") or i.get("url") for i in items) if u]
        return analysis

    except Exception as e:
        logger.error(f"Insight analysis failed for '{topic}' ({kind}): {e}", exc_info=True)
        return None


async def analyze(
    kind: str,
    topic: str,
    items: List[Dict[str, Any]],
    prior_insights: Optional[List[Dict[str, Any]]] = None,
) -> List[Analysis]:
    """Cluster one topic's findings into graded, structured storylines.

    Two phases, deliberately kept as separate LLM calls:

      1. one cheap call groups the findings into storylines
      2. one focused call per storyline writes that insight

    Asking a single call for all N insights meant a slow, long generation
    whose quality drifted toward the end. Per-storyline calls each stay small,
    and INSIGHT_ANALYSIS_CONCURRENCY of them run at a time.

    Returns a list because a scan's findings usually span several unrelated
    developments; each one becomes its own insight card. Empty only when
    there's nothing usable at all (no items, or every call failed).
    Low-value findings come back as a low significance score instead - it's
    the caller's job to decide the cutoff.
    """
    prior_insights = prior_insights or []

    if not items:
        return []

    groups = await _cluster(topic, items)

    # A failed storyline shouldn't take the others down, so gather with
    # return_exceptions and drop the casualties.
    semaphore = asyncio.Semaphore(max(1, config.INSIGHT_ANALYSIS_CONCURRENCY))

    async def run(group):
        async with semaphore:
            return await _analyze_one(kind, topic, group, prior_insights)

    results = await asyncio.gather(*(run(g) for g in groups), return_exceptions=True)

    analyses = []
    for r in results:
        if isinstance(r, Exception):
            logger.error(f"Storyline analysis raised for '{topic}': {r}")
        elif r is not None:
            analyses.append(r)

    analyses.sort(key=lambda a: a.significance, reverse=True)
    return analyses
