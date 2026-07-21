"""Tests for src/managers/insight_analyzer.py (parsing, grading, validation)."""
import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.managers import insight_analyzer
from src.managers.insight_analyzer import Analysis

ONE_INSIGHT = """{
  "headline": "Widget makers consolidate",
  "what_happened": "Two of the three largest makers merged.",
  "why_it_matters": "Pricing power shifts to a single supplier.",
  "what_to_watch": ["Regulatory response", "Price changes"],
  "entities": ["AcmeCorp", "WidgetCo"],
  "significance": 4,
  "source_urls": ["https://a.example"],
  "connection": null
}"""

VALID_JSON = ONE_INSIGHT

ITEMS = [
    {"title": "Merger announced", "snippet": "details", "link": "https://a.example"},
    {"title": "Factory opens", "snippet": "unrelated story", "link": "https://b.example"},
]


ALL_URLS = [i["link"] for i in ITEMS]

# Groups every finding into one storyline - the default so that tests about a
# single insight don't have to care about the clustering phase.
ONE_GROUP = '{"storylines": [{"label": "everything", "source_urls": %s}]}' % json.dumps(ALL_URLS)


def _as_response(content):
    message = MagicMock()
    message.content = content
    choice = MagicMock()
    choice.message = message
    response = MagicMock()
    response.choices = [choice]
    return response


def mock_llm(insight, cluster=ONE_GROUP):
    """Route the two phases of analyze() to different canned responses.

    analyze() makes one clustering call and then one call per storyline, so a
    single canned response is no longer enough. `insight` may be a string (all
    storylines answer the same) or a callable taking the prompt, for tests
    where each storyline needs its own answer.
    """
    async def create(*, messages, **kwargs):
        prompt = messages[0]["content"]
        if '"storylines"' in prompt:
            return _as_response(cluster)
        return _as_response(insight(prompt) if callable(insight) else insight)

    client = MagicMock()
    client.chat.completions.create = AsyncMock(side_effect=create)

    mock_openai = MagicMock()
    mock_openai.AsyncOpenAI = MagicMock(return_value=client)
    return patch.dict(sys.modules, {"openai": mock_openai})


@pytest.mark.asyncio
async def test_parses_well_formed_json():
    with mock_llm(VALID_JSON):
        (analysis,) = await insight_analyzer.analyze("news", "widgets", ITEMS)

    assert analysis.headline == "Widget makers consolidate"
    assert analysis.why_it_matters.startswith("Pricing power")
    assert analysis.what_to_watch == ["Regulatory response", "Price changes"]
    assert analysis.entities == ["AcmeCorp", "WidgetCo"]
    assert analysis.significance == 4
    assert analysis.connection is None


@pytest.mark.asyncio
async def test_parses_json_wrapped_in_code_fences():
    with mock_llm(f"Here you go:\n```json\n{VALID_JSON}\n```"):
        (analysis,) = await insight_analyzer.analyze("news", "widgets", ITEMS)

    assert analysis.headline == "Widget makers consolidate"


@pytest.mark.asyncio
async def test_malformed_json_degrades_rather_than_dropping():
    """An unparseable response must still yield a storable, unpushed insight."""
    with mock_llm("The widget market consolidated this week and prices rose."):
        (analysis,) = await insight_analyzer.analyze("news", "widgets", ITEMS)

    assert "widget market consolidated" in analysis.what_happened
    assert analysis.significance == insight_analyzer.FALLBACK_SIGNIFICANCE


@pytest.mark.asyncio
async def test_missing_optional_fields_default_cleanly():
    with mock_llm('{"what_happened": "A thing happened.", "significance": 3}'):
        (analysis,) = await insight_analyzer.analyze("news", "widgets", ITEMS)

    assert analysis.what_happened == "A thing happened."
    assert analysis.headline == "A thing happened."  # falls back to what_happened
    assert analysis.why_it_matters == ""
    assert analysis.what_to_watch == []
    assert analysis.entities == []


@pytest.mark.asyncio
async def test_significance_is_clamped_to_range():
    with mock_llm('{"headline": "h", "what_happened": "w", "significance": 99}'):
        (analysis,) = await insight_analyzer.analyze("news", "widgets", ITEMS)

    assert analysis.significance == 5


@pytest.mark.asyncio
async def test_non_numeric_significance_falls_back():
    with mock_llm('{"headline": "h", "what_happened": "w", "significance": "very high"}'):
        (analysis,) = await insight_analyzer.analyze("news", "widgets", ITEMS)

    assert analysis.significance == insight_analyzer.FALLBACK_SIGNIFICANCE


@pytest.mark.asyncio
async def test_connection_to_known_prior_is_kept():
    prior = [{"id": "prior-1", "created_at": "2026-07-01T00:00:00", "headline": "Earlier", "entities": []}]
    body = (
        '{"headline": "h", "what_happened": "w", "significance": 4,'
        ' "connection": {"prior_insight_id": "prior-1", "relation": "contradicts", "note": "Reverses it."}}'
    )
    with mock_llm(body):
        (analysis,) = await insight_analyzer.analyze("news", "widgets", ITEMS, prior)

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
        (analysis,) = await insight_analyzer.analyze("news", "widgets", ITEMS, prior)

    assert analysis.connection is None


@pytest.mark.asyncio
async def test_unknown_relation_falls_back_to_follows_up():
    prior = [{"id": "prior-1", "created_at": "2026-07-01T00:00:00", "headline": "Earlier", "entities": []}]
    body = (
        '{"headline": "h", "what_happened": "w", "significance": 4,'
        ' "connection": {"prior_insight_id": "prior-1", "relation": "invents_a_relation", "note": "n"}}'
    )
    with mock_llm(body):
        (analysis,) = await insight_analyzer.analyze("news", "widgets", ITEMS, prior)

    assert analysis.connection["relation"] == "follows_up"


@pytest.mark.asyncio
async def test_no_items_short_circuits_without_llm_call():
    assert await insight_analyzer.analyze("news", "widgets", []) == []


@pytest.mark.asyncio
async def test_llm_failure_returns_empty():
    mock_openai = MagicMock()
    mock_openai.AsyncOpenAI = MagicMock(side_effect=RuntimeError("no api key"))

    with patch.dict(sys.modules, {"openai": mock_openai}):
        assert await insight_analyzer.analyze("news", "widgets", ITEMS) == []


@pytest.mark.asyncio
async def test_empty_response_returns_empty():
    with mock_llm(""):
        assert await insight_analyzer.analyze("news", "widgets", ITEMS) == []


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


# ── Clustering into storylines ───────────────────────────────────────────────

TWO_GROUPS = """{"storylines": [
  {"label": "merger", "source_urls": ["https://a.example"]},
  {"label": "factory", "source_urls": ["https://b.example"]}
]}"""


def insight_per_url(prompt):
    """Answer a phase-2 call according to which finding it was handed."""
    if "https://a.example" in prompt:
        return '{"headline": "Merger", "what_happened": "Two makers merged.", "significance": 4}'
    return '{"headline": "Factory", "what_happened": "A plant opened.", "significance": 2}'


@pytest.mark.asyncio
async def test_each_storyline_gets_its_own_llm_call():
    """One call to cluster, then one per storyline - not one call for all."""
    with mock_llm(insight_per_url, cluster=TWO_GROUPS) as _:
        with patch("src.managers.insight_analyzer._complete", wraps=insight_analyzer._complete) as complete:
            analyses = await insight_analyzer.analyze("news", "widgets", ITEMS)

    assert complete.await_count == 3  # 1 clustering + 2 storylines
    assert len(analyses) == 2


@pytest.mark.asyncio
async def test_multiple_storylines_become_multiple_analyses():
    """The whole point: one scan's findings yield one card per distinct story."""
    with mock_llm(insight_per_url, cluster=TWO_GROUPS):
        analyses = await insight_analyzer.analyze("news", "widgets", ITEMS)

    assert [a.headline for a in analyses] == ["Merger", "Factory"]


@pytest.mark.asyncio
async def test_analyses_are_ordered_by_significance():
    """Storylines resolve concurrently, so order must come from the grading."""
    with mock_llm(insight_per_url, cluster=TWO_GROUPS):
        analyses = await insight_analyzer.analyze("news", "widgets", ITEMS)

    assert [a.significance for a in analyses] == [4, 2]


@pytest.mark.asyncio
async def test_each_storyline_keeps_only_its_own_sources():
    """Attribution comes from the grouping, not from the model's say-so."""
    with mock_llm(insight_per_url, cluster=TWO_GROUPS):
        merger, factory = await insight_analyzer.analyze("news", "widgets", ITEMS)

    assert merger.source_urls == ["https://a.example"]
    assert factory.source_urls == ["https://b.example"]


@pytest.mark.asyncio
async def test_storyline_analysis_sees_only_its_own_findings():
    """A per-storyline call must not be handed the other stories' articles."""
    seen = []

    def record(prompt):
        seen.append(prompt)
        return '{"headline": "h", "what_happened": "w", "significance": 3}'

    with mock_llm(record, cluster=TWO_GROUPS):
        await insight_analyzer.analyze("news", "widgets", ITEMS)

    merger_prompt = next(p for p in seen if "https://a.example" in p)
    assert "https://b.example" not in merger_prompt


@pytest.mark.asyncio
async def test_one_failing_storyline_does_not_lose_the_others():
    def half_broken(prompt):
        if "https://a.example" in prompt:
            return ""          # empty response - this storyline is lost
        return '{"headline": "Factory", "what_happened": "w", "significance": 3}'

    with mock_llm(half_broken, cluster=TWO_GROUPS):
        analyses = await insight_analyzer.analyze("news", "widgets", ITEMS)

    assert [a.headline for a in analyses] == ["Factory"]


@pytest.mark.asyncio
async def test_failed_clustering_falls_back_to_one_storyline():
    """A scan yielding one insight beats a scan yielding none."""
    with mock_llm(VALID_JSON, cluster="not json at all"):
        analyses = await insight_analyzer.analyze("news", "widgets", ITEMS)

    assert len(analyses) == 1
    assert analyses[0].headline == "Widget makers consolidate"


@pytest.mark.asyncio
async def test_unknown_urls_in_a_group_are_ignored():
    cluster = '{"storylines": [{"label": "x", "source_urls": ["https://a.example", "https://invented.example"]}]}'
    with mock_llm(VALID_JSON, cluster=cluster):
        (analysis,) = await insight_analyzer.analyze("news", "widgets", ITEMS)

    assert analysis.source_urls == ["https://a.example"]


@pytest.mark.asyncio
async def test_empty_groups_are_skipped():
    """A group naming no known URL has nothing to analyze."""
    cluster = ('{"storylines": [{"label": "real", "source_urls": ["https://a.example"]},'
               ' {"label": "empty", "source_urls": ["https://nope.example"]}]}')
    with mock_llm(VALID_JSON, cluster=cluster):
        analyses = await insight_analyzer.analyze("news", "widgets", ITEMS)

    assert len(analyses) == 1


@pytest.mark.asyncio
async def test_group_count_is_capped():
    groups = ",".join(
        '{"label": "g%d", "source_urls": ["%s"]}' % (n, ITEMS[n % 2]["link"]) for n in range(20)
    )
    with mock_llm(VALID_JSON, cluster='{"storylines": [%s]}' % groups):
        analyses = await insight_analyzer.analyze("news", "widgets", ITEMS)

    from src.core import config
    assert len(analyses) == config.INSIGHT_MAX_PER_SCAN


@pytest.mark.asyncio
async def test_single_finding_skips_the_clustering_call():
    """Nothing to group, so don't pay for a call that can only say 'one group'."""
    one = [ITEMS[0]]
    with mock_llm(VALID_JSON):
        with patch("src.managers.insight_analyzer._complete", wraps=insight_analyzer._complete) as complete:
            analyses = await insight_analyzer.analyze("news", "widgets", one)

    assert complete.await_count == 1
    assert len(analyses) == 1


def test_cluster_prompt_asks_for_distinct_storylines():
    prompt = insight_analyzer._build_cluster_prompt("widgets", ITEMS)

    assert "DISTINCT STORYLINES" in prompt
    assert str(insight_analyzer.config.INSIGHT_MAX_PER_SCAN) in prompt


def test_analysis_prompt_asks_for_a_single_insight():
    prompt = insight_analyzer._build_prompt("news", "widgets", ITEMS, [])

    assert "ONE story" in prompt
    assert "storylines" not in prompt  # phase 2 must not trigger the cluster branch
