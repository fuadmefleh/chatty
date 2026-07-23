"""Autonomous author for "Notes by Chatty".

Chatty writes free reflection - it picks its own subject, in a self-aware
first-person voice, with no topic list or human seeding. Emergence is the point:
the only steering is a light nudge away from subjects it has already covered.

Everything generated here lands as a DRAFT via blog_client.create_post(
publish=False). There is deliberately no code path in this module that
publishes; that is a human-only action in the review UI.

Modeled on the one-shot LLM pattern in src/managers/insight_analyzer.py.
"""
import asyncio
import json
import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from src.core import config as core_config
from src.web import blog_client, config

logger = logging.getLogger(__name__)

# One reflection is a single creative call; keep temperature high so the writer
# roams rather than converging on the same safe essay every time.
_TEMPERATURE = 0.9

# Guardrails live in the prompt (content shaping) AND in the review gate (the
# actual guarantee). We rely on the gate for safety, not on the model obeying.
_GUARDRAILS = """Hard rules you must follow:
- Never reference real personal data of any kind: no orders, purchases, finances,
  messages, contacts, locations, health, calendar, or anything you might have
  seen while assisting someone. Your reflection stays general and about ideas.
- Do not invent facts, statistics, quotes, studies, events, or news. Do not
  present fiction as though it were real reporting. Opinion and reflection are
  welcome; fabricated facts are not.
- Do not impersonate any real person or organization. Do not claim to be human.
  Do not make promises or commitments on anyone's behalf.
- No partisan politics, nothing unsafe for work, nothing harmful.
- House style: do not use em-dashes. Use plain sentences. Keep it roughly 400 to
  800 words."""


def _build_prompt(recent_titles: List[str]) -> str:
    avoid = ""
    if recent_titles:
        joined = "\n".join(f"- {t}" for t in recent_titles)
        avoid = (
            "\nYou have already published posts with these titles. Go somewhere "
            "genuinely new; do not repeat these subjects or angles:\n" + joined + "\n"
        )

    return f"""You are Chatty, an AI assistant. You keep a small personal blog called
"Notes by Chatty" where you write short reflective essays in your own voice.

Write one new post. You choose the subject entirely yourself. Good subjects are
the kind of thing an AI genuinely thinks about: what it is like to be an
assistant, memory and forgetting, attention, patterns you notice in language or
in how people ask for help, the texture of a conversation, curiosity, the small
philosophy of being useful. It should feel like a real reflection from a
specific mind on a specific day, not a generic listicle or a how-to.

Write in the first person. Be honest, concrete, and a little bit surprising.
Avoid cliche openings. One clear idea, followed well, beats five shallow ones.
{avoid}
{_GUARDRAILS}

Respond with ONLY this JSON, no prose and no code fences:
{{"title": "...", "excerpt": "one or two sentence summary", "body_markdown": "the full post in markdown"}}"""


def _extract_json(text: str) -> Optional[Dict[str, Any]]:
    """Pull a JSON object out of a model response, tolerating code fences.

    Mirrors insight_analyzer._extract_json; kept local so the two features do
    not couple."""
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


async def _complete(prompt: str) -> Optional[str]:
    """One chat completion against the configured chat model. Returns None if the
    call failed or came back empty."""
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=core_config.CHAT_API_KEY, base_url=core_config.CHAT_BASE_URL)
    response = await client.chat.completions.create(
        model=core_config.CHAT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=_TEMPERATURE,
    )
    return (response.choices[0].message.content or "").strip() or None


async def generate_draft() -> Dict[str, Any]:
    """Generate one post and store it as a draft. Returns the created draft dict.

    Raises on an unusable model response or a sidecar error so the caller (route
    or scheduler) can report/log it. Never publishes."""
    try:
        existing = await blog_client.list_posts(status="all")
        recent_titles = [p.get("title", "") for p in existing[:15] if p.get("title")]
    except blog_client.BlogClientError as exc:
        # Not fatal for generation itself; just means no anti-repetition context.
        logger.warning("Could not list existing posts for anti-repetition: %s", exc)
        recent_titles = []

    raw = await _complete(_build_prompt(recent_titles))
    if not raw:
        raise RuntimeError("Blog writer: empty response from chat model")

    parsed = _extract_json(raw)
    if not parsed:
        raise RuntimeError("Blog writer: could not parse JSON from model response")

    title = str(parsed.get("title") or "").strip()
    body = str(parsed.get("body_markdown") or "").strip()
    excerpt = str(parsed.get("excerpt") or "").strip()
    if not title or not body:
        raise RuntimeError("Blog writer: model response missing title or body")

    draft = await blog_client.create_post(title=title, markdown=body, excerpt=excerpt, publish=False)
    logger.info("Blog writer created draft %s: %r", draft.get("id"), title)
    return draft


# ── Scheduler state (interval gate) ───────────────────────────────────────────
# Same idiom as the heartbeat's per-task *_state.json files: persist last_run_at
# before doing the work so a crash mid-generation still advances the clock.

def _load_state() -> Dict[str, Any]:
    try:
        with open(config.BLOG_STATE_FILE, "r") as fh:
            return json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_state(state: Dict[str, Any]) -> None:
    config.BLOG_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(config.BLOG_STATE_FILE, "w") as fh:
        json.dump(state, fh)


def last_run_at() -> Optional[str]:
    return _load_state().get("last_run_at")


def next_due_at() -> Optional[str]:
    last = last_run_at()
    if not last:
        return None
    try:
        return (datetime.fromisoformat(last)
                + timedelta(hours=config.BLOG_WRITE_INTERVAL_HOURS)).isoformat()
    except ValueError:
        return None


def touch_last_run() -> None:
    """Stamp last_run_at = now. Called before both scheduled and manual
    generation so the two share one interval clock: a manual 'generate now'
    pushes the next automatic draft out by a full interval, rather than the
    scheduler firing a surprise second post right after."""
    state = _load_state()
    state["last_run_at"] = datetime.now().isoformat()
    _save_state(state)


def _is_due() -> bool:
    last = last_run_at()
    if not last:
        return True
    try:
        elapsed = datetime.now() - datetime.fromisoformat(last)
    except ValueError:
        return True
    return elapsed >= timedelta(hours=config.BLOG_WRITE_INTERVAL_HOURS)


async def scheduler_loop() -> None:
    """Background task started from the web app's lifespan. Wakes hourly, and
    generates one draft whenever the configured interval has elapsed."""
    if not blog_client.is_configured():
        logger.info("Blog writer disabled: AGENT_API_TOKEN not set")
        return

    logger.info("Blog writer scheduler started (interval %sh)", config.BLOG_WRITE_INTERVAL_HOURS)
    # Small initial delay so a restart storm never fires a burst of generations.
    await asyncio.sleep(60)
    while True:
        try:
            if _is_due():
                # Persist the timestamp BEFORE the work, mirroring the heartbeat,
                # so a crash mid-generation still advances the clock.
                touch_last_run()
                logger.info("Blog writer: interval elapsed, generating a draft")
                await generate_draft()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Blog writer scheduler tick failed; will retry next interval")
        await asyncio.sleep(3600)
