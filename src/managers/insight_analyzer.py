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
"""
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


def _build_prompt(kind: str, topic: str, items: List[Dict[str, Any]], prior_insights: List[Dict[str, Any]]) -> str:
    subject, guidance = _KIND_FRAMING.get(kind, _KIND_FRAMING["news"])

    return f"""You are analyzing {subject}.

TOPIC: {topic}

NEW FINDINGS:
{_format_items(items)}

EARLIER INSIGHTS YOU ALREADY SURFACED ON THIS TOPIC (most recent first):
{_format_prior(prior_insights)}

{guidance}

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

If (and only if) these findings genuinely relate to one of the earlier
insights listed above, set "connection" to:
  {{"prior_insight_id": "<the exact id>", "relation": "follows_up|contradicts|escalates", "note": "one sentence on the link"}}
Otherwise leave "connection" as null. Do not invent a connection to fill the field."""


def _extract_json(text: str) -> Optional[Dict[str, Any]]:
    """Pull a JSON object out of a model response, tolerating code fences."""
    text = text.strip()

    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    else:
        braced = re.search(r"\{.*\}", text, re.DOTALL)
        if braced:
            text = braced.group(0)

    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
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


def _build_analysis(parsed: Dict[str, Any], topic: str, prior_insights: List[Dict[str, Any]]) -> Analysis:
    try:
        significance = int(parsed.get("significance", FALLBACK_SIGNIFICANCE))
    except (TypeError, ValueError):
        significance = FALLBACK_SIGNIFICANCE
    significance = max(1, min(5, significance))

    what_happened = str(parsed.get("what_happened") or "").strip()
    headline = str(parsed.get("headline") or "").strip() or (what_happened[:90] or topic)

    return Analysis(
        headline=headline,
        what_happened=what_happened,
        why_it_matters=str(parsed.get("why_it_matters") or "").strip(),
        what_to_watch=_coerce_str_list(parsed.get("what_to_watch"), limit=5),
        entities=_coerce_str_list(parsed.get("entities"), limit=10),
        significance=significance,
        connection=_validate_connection(parsed.get("connection"), prior_insights),
    )


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


async def analyze(
    kind: str,
    topic: str,
    items: List[Dict[str, Any]],
    prior_insights: Optional[List[Dict[str, Any]]] = None,
) -> Optional[Analysis]:
    """Produce a structured, graded Analysis for one watch topic's findings.

    Returns None only when there is nothing usable at all (no items, or the
    LLM call failed outright). Low-value findings come back as a low
    significance score instead - it's the caller's job to decide the cutoff.
    """
    prior_insights = prior_insights or []

    if not items:
        return None

    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=config.CHAT_API_KEY, base_url=config.CHAT_BASE_URL)

        response = await client.chat.completions.create(
            model=config.CHAT_MODEL,
            messages=[{"role": "user", "content": _build_prompt(kind, topic, items, prior_insights)}],
            temperature=0.3,
        )

        content = (response.choices[0].message.content or "").strip()
        if not content:
            return None

        parsed = _extract_json(content)
        if parsed is None:
            return _degraded(content, topic)

        return _build_analysis(parsed, topic, prior_insights)

    except Exception as e:
        logger.error(f"Insight analysis failed for '{topic}' ({kind}): {e}", exc_info=True)
        return None
