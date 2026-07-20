"""Tests for src/managers/insight_analyzer.py (parsing, grading, validation)."""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.managers import insight_analyzer
from src.managers.insight_analyzer import Analysis

VALID_JSON = """{
  "headline": "Widget makers consolidate",
  "what_happened": "Two of the three largest makers merged.",
  "why_it_matters": "Pricing power shifts to a single supplier.",
  "what_to_watch": ["Regulatory response", "Price changes"],
  "entities": ["AcmeCorp", "WidgetCo"],
  "significance": 4,
  "connection": null
}"""

ITEMS = [{"title": "Merger announced", "snippet": "details", "link": "https://a.example"}]


def mock_llm(content):
    """Patch the OpenAI client so analyze() sees `content` as the response."""
    message = MagicMock()
    message.content = content
    choice = MagicMock()
    choice.message = message
    response = MagicMock()
    response.choices = [choice]

    client = MagicMock()
    client.chat.completions.create = AsyncMock(return_value=response)

    mock_openai = MagicMock()
    mock_openai.AsyncOpenAI = MagicMock(return_value=client)
    return patch.dict(sys.modules, {"openai": mock_openai})


@pytest.mark.asyncio
async def test_parses_well_formed_json():
    with mock_llm(VALID_JSON):
        analysis = await insight_analyzer.analyze("news", "widgets", ITEMS)

    assert analysis.headline == "Widget makers consolidate"
    assert analysis.why_it_matters.startswith("Pricing power")
    assert analysis.what_to_watch == ["Regulatory response", "Price changes"]
    assert analysis.entities == ["AcmeCorp", "WidgetCo"]
    assert analysis.significance == 4
    assert analysis.connection is None


@pytest.mark.asyncio
async def test_parses_json_wrapped_in_code_fences():
    with mock_llm(f"Here you go:\n```json\n{VALID_JSON}\n```"):
        analysis = await insight_analyzer.analyze("news", "widgets", ITEMS)

    assert analysis.headline == "Widget makers consolidate"


@pytest.mark.asyncio
async def test_malformed_json_degrades_rather_than_dropping():
    """An unparseable response must still yield a storable, unpushed insight."""
    with mock_llm("The widget market consolidated this week and prices rose."):
        analysis = await insight_analyzer.analyze("news", "widgets", ITEMS)

    assert analysis is not None
    assert "widget market consolidated" in analysis.what_happened
    assert analysis.significance == insight_analyzer.FALLBACK_SIGNIFICANCE


@pytest.mark.asyncio
async def test_missing_optional_fields_default_cleanly():
    with mock_llm('{"what_happened": "A thing happened.", "significance": 3}'):
        analysis = await insight_analyzer.analyze("news", "widgets", ITEMS)

    assert analysis.what_happened == "A thing happened."
    assert analysis.headline == "A thing happened."  # falls back to what_happened
    assert analysis.why_it_matters == ""
    assert analysis.what_to_watch == []
    assert analysis.entities == []


@pytest.mark.asyncio
async def test_significance_is_clamped_to_range():
    with mock_llm('{"headline": "h", "what_happened": "w", "significance": 99}'):
        analysis = await insight_analyzer.analyze("news", "widgets", ITEMS)

    assert analysis.significance == 5


@pytest.mark.asyncio
async def test_non_numeric_significance_falls_back():
    with mock_llm('{"headline": "h", "what_happened": "w", "significance": "very high"}'):
        analysis = await insight_analyzer.analyze("news", "widgets", ITEMS)

    assert analysis.significance == insight_analyzer.FALLBACK_SIGNIFICANCE


@pytest.mark.asyncio
async def test_connection_to_known_prior_is_kept():
    prior = [{"id": "prior-1", "created_at": "2026-07-01T00:00:00", "headline": "Earlier", "entities": []}]
    body = (
        '{"headline": "h", "what_happened": "w", "significance": 4,'
        ' "connection": {"prior_insight_id": "prior-1", "relation": "contradicts", "note": "Reverses it."}}'
    )
    with mock_llm(body):
        analysis = await insight_analyzer.analyze("news", "widgets", ITEMS, prior)

    assert analysis.connection == {
        "prior_insight_id": "prior-1",
        "relation": "contradicts",
        "note": "Reverses it.",
    }


@pytest.mark.asyncio
async def test_connection_to_unknown_prior_is_dropped():
    """A hallucinated id would render as a dead link, so it must not survive."""
    prior = [{"id": "prior-1", "created_at": "2026-07-01T00:00:00", "headline": "Earlier", "entities": []}]
    body = (
        '{"headline": "h", "what_happened": "w", "significance": 4,'
        ' "connection": {"prior_insight_id": "made-up", "relation": "follows_up", "note": "n"}}'
    )
    with mock_llm(body):
        analysis = await insight_analyzer.analyze("news", "widgets", ITEMS, prior)

    assert analysis.connection is None


@pytest.mark.asyncio
async def test_unknown_relation_falls_back_to_follows_up():
    prior = [{"id": "prior-1", "created_at": "2026-07-01T00:00:00", "headline": "Earlier", "entities": []}]
    body = (
        '{"headline": "h", "what_happened": "w", "significance": 4,'
        ' "connection": {"prior_insight_id": "prior-1", "relation": "invents_a_relation", "note": "n"}}'
    )
    with mock_llm(body):
        analysis = await insight_analyzer.analyze("news", "widgets", ITEMS, prior)

    assert analysis.connection["relation"] == "follows_up"


@pytest.mark.asyncio
async def test_no_items_short_circuits_without_llm_call():
    analysis = await insight_analyzer.analyze("news", "widgets", [])
    assert analysis is None


@pytest.mark.asyncio
async def test_llm_failure_returns_none():
    mock_openai = MagicMock()
    mock_openai.AsyncOpenAI = MagicMock(side_effect=RuntimeError("no api key"))

    with patch.dict(sys.modules, {"openai": mock_openai}):
        analysis = await insight_analyzer.analyze("news", "widgets", ITEMS)

    assert analysis is None


@pytest.mark.asyncio
async def test_empty_response_returns_none():
    with mock_llm(""):
        analysis = await insight_analyzer.analyze("news", "widgets", ITEMS)

    assert analysis is None


@pytest.mark.asyncio
async def test_prompt_includes_prior_insights_and_findings():
    prior = [{"id": "prior-1", "created_at": "2026-07-01T00:00:00", "headline": "Earlier widget news", "entities": ["AcmeCorp"]}]
    prompt = insight_analyzer._build_prompt("news", "widgets", ITEMS, prior)

    assert "widgets" in prompt
    assert "Merger announced" in prompt
    assert "prior-1" in prompt
    assert "Earlier widget news" in prompt


def test_to_summary_renders_sections():
    analysis = Analysis(
        headline="Widget makers consolidate",
        what_happened="Two makers merged.",
        why_it_matters="Pricing power shifts.",
        what_to_watch=["Regulatory response"],
        significance=4,
        connection={"prior_insight_id": "p1", "relation": "follows_up", "note": "Builds on July merger talk."},
    )
    summary = analysis.to_summary()

    assert "Widget makers consolidate" in summary
    assert "Why it matters: Pricing power shifts." in summary
    assert "Context: Builds on July merger talk." in summary
    assert "• Regulatory response" in summary


def test_to_summary_omits_empty_sections():
    summary = Analysis(headline="H", what_happened="W", significance=2).to_summary()

    assert summary == "H\n\nW"
