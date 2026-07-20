"""Tests for src/managers/insights_manager.py (schema, back-compat, filtering)."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.managers.insights_manager import (
    Insight,
    InsightsManager,
    LEGACY_SCHEMA_VERSION,
    STRUCTURED_SCHEMA_VERSION,
)

LEGACY_RECORD = {
    "id": "legacy-1",
    "topic": "ai",
    "summary": "A flat paragraph written before structured insights existed.",
    "sources": [{"title": "Source", "url": "https://a.example"}],
    "created_at": "2026-07-01T00:00:00",
    "user_id": "u1",
}


@pytest.fixture
def mgr(tmp_path):
    return InsightsManager(data_dir=str(tmp_path))


def test_legacy_record_loads_with_defaults():
    """Records written before this change must still deserialize."""
    insight = Insight.from_dict(LEGACY_RECORD)

    assert insight.summary == LEGACY_RECORD["summary"]
    assert insight.schema_version == LEGACY_SCHEMA_VERSION
    assert insight.headline == ""
    assert insight.what_to_watch == []
    assert insight.entities == []
    assert insight.connection is None
    assert insight.kind == "news"


def test_legacy_record_round_trips():
    restored = Insight.from_dict(Insight.from_dict(LEGACY_RECORD).to_dict())

    assert restored.id == "legacy-1"
    assert restored.summary == LEGACY_RECORD["summary"]
    assert restored.schema_version == LEGACY_SCHEMA_VERSION


def test_structured_insight_persists_and_reloads(mgr):
    mgr.add_insight(
        "u1", "ai", "flat summary", [],
        kind="news", significance=4,
        headline="Model released", what_happened="A lab shipped.",
        why_it_matters="Costs drop.", what_to_watch=["Pricing"],
        entities=["LabCo"], connection=None,
    )

    (loaded,) = mgr.get_insights("u1")

    assert loaded.headline == "Model released"
    assert loaded.why_it_matters == "Costs drop."
    assert loaded.what_to_watch == ["Pricing"]
    assert loaded.entities == ["LabCo"]
    assert loaded.significance == 4
    assert loaded.schema_version == STRUCTURED_SCHEMA_VERSION


def test_insight_without_headline_stays_legacy_version(mgr):
    """Callers that don't produce structured analysis still write valid records."""
    mgr.add_insight("u1", "ai", "just a summary", [])

    (loaded,) = mgr.get_insights("u1")
    assert loaded.schema_version == LEGACY_SCHEMA_VERSION


def test_get_insights_filters_by_min_significance(mgr):
    for sig in (2, 3, 5):
        mgr.add_insight("u1", "ai", f"summary {sig}", [], significance=sig, headline=f"h{sig}")

    assert len(mgr.get_insights("u1")) == 3
    assert len(mgr.get_insights("u1", min_significance=3)) == 2
    assert [i.significance for i in mgr.get_insights("u1", min_significance=5)] == [5]


def test_legacy_records_survive_significance_filter(mgr, tmp_path):
    """Legacy records default to significance 3 and must not silently vanish."""
    (tmp_path / "u1.json").write_text(json.dumps([LEGACY_RECORD]), encoding="utf-8")

    assert len(mgr.get_insights("u1", min_significance=2)) == 1
    assert len(mgr.get_insights("u1", min_significance=3)) == 1
    assert len(mgr.get_insights("u1", min_significance=4)) == 0


def test_get_insights_by_topic_filters_and_orders(mgr):
    mgr.add_insight("u1", "ai", "older ai", [], headline="older")
    mgr.add_insight("u1", "widgets", "widget news", [], headline="widgets")
    mgr.add_insight("u1", "ai", "newer ai", [], headline="newer")

    results = mgr.get_insights_by_topic("u1", "ai")

    assert [i.headline for i in results] == ["newer", "older"]


def test_get_insights_by_topic_respects_limit(mgr):
    for n in range(8):
        mgr.add_insight("u1", "ai", f"s{n}", [], headline=f"h{n}")

    assert len(mgr.get_insights_by_topic("u1", "ai", limit=5)) == 5


def test_get_insights_by_topic_empty_for_unknown_topic(mgr):
    mgr.add_insight("u1", "ai", "s", [], headline="h")

    assert mgr.get_insights_by_topic("u1", "nothing-here") == []
