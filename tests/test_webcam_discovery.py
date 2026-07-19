"""Tests for src/managers/webcam_discovery.py - the SearXNG-driven search +
LLM curation pipeline. Network and LLM calls are mocked throughout; these
tests focus on dedup and curation correctness."""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.managers import webcam_discovery as wd
from src.managers import webcam_manager as wm
from src.managers import webcam_verifier as wv


def make_sources_manager(tmp_path):
    return wm.WebcamSourcesManager(data_dir=str(tmp_path / "webcam_sources"))


def make_suggestions_manager(tmp_path):
    return wm.WebcamSuggestionsManager(data_dir=str(tmp_path / "webcam_sources"))


def test_parse_queries_splits_on_semicolon():
    assert wd._parse_queries("a; b ;c") == ["a", "b", "c"]
    assert wd._parse_queries("  ") == []


@pytest.mark.asyncio
async def test_run_discovery_searches_flattens_results():
    fake_client = MagicMock()
    fake_client.is_configured.return_value = True
    fake_client.search = AsyncMock(return_value={
        "success": True,
        "results": [
            {"title": "t1", "link": "https://reddit.com/1", "snippet": "s1"},
            {"title": "t2", "link": "https://reddit.com/2", "snippet": "s2"},
        ],
    })

    with patch("src.managers.webcam_discovery.get_search_client", return_value=fake_client):
        candidates = await wd._run_discovery_searches(["query one", "query two"], per_query=5)

    assert fake_client.search.call_count == 2
    assert len(candidates) == 4
    assert candidates[0]["link"] == "https://reddit.com/1"
    assert candidates[0]["query"] == "query one"


@pytest.mark.asyncio
async def test_run_discovery_searches_skips_when_not_configured():
    fake_client = MagicMock()
    fake_client.is_configured.return_value = False

    with patch("src.managers.webcam_discovery.get_search_client", return_value=fake_client):
        candidates = await wd._run_discovery_searches(["query"], per_query=5)

    assert candidates == []
    fake_client.search.assert_not_called()


def test_extract_json_array_plain():
    assert wd._extract_json_array('[{"name": "a"}]') == [{"name": "a"}]


def test_extract_json_array_wrapped_in_prose_and_fences():
    text = 'Sure, here you go:\n```json\n[{"name": "a"}]\n```\nHope that helps!'
    assert wd._extract_json_array(text) == [{"name": "a"}]


def test_extract_json_array_returns_none_on_garbage():
    assert wd._extract_json_array("not json at all") is None


@pytest.mark.asyncio
async def test_curate_suggestions_filters_to_known_links_and_valid_fields():
    candidates = [
        {"title": "t1", "link": "https://reddit.com/1", "snippet": "s1", "query": "q"},
    ]
    fake_response = MagicMock()
    fake_response.choices = [MagicMock(message=MagicMock(content=(
        '[{"name": "Cam 1", "url": "https://cam1.example/stream", "kind": "snapshot", '
        '"location": "NYC", "rationale": "looks real", "discovered_url": "https://reddit.com/1"},'
        '{"name": "Unrelated", "url": "https://x.example", "kind": "webpage", "location": "", '
        '"rationale": "x", "discovered_url": "https://not-in-candidates.example"}]'
    )))]
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=fake_response)

    with patch("openai.AsyncOpenAI", return_value=mock_client):
        ideas = await wd._curate_suggestions(candidates, max_suggestions=5)

    assert len(ideas) == 1
    assert ideas[0]["name"] == "Cam 1"
    assert ideas[0]["kind"] == "snapshot"
    assert ideas[0]["discovered_url"] == "https://reddit.com/1"


@pytest.mark.asyncio
async def test_curate_suggestions_empty_candidates_short_circuits():
    assert await wd._curate_suggestions([], max_suggestions=5) == []


@pytest.mark.asyncio
async def test_run_webcam_discovery_scan_dedups_against_seen_urls(tmp_path):
    sources_mgr = make_sources_manager(tmp_path)
    suggestions_mgr = make_suggestions_manager(tmp_path)
    suggestions_mgr.create(name="Already", url="u", discovered_url="https://reddit.com/already-seen")
    sources_mgr.create(name="Existing Source", url="https://reddit.com/already-a-source")

    searched = [
        {"title": "t1", "link": "https://reddit.com/already-seen", "snippet": "s", "query": "q"},
        {"title": "t2", "link": "https://reddit.com/already-a-source", "snippet": "s", "query": "q"},
        {"title": "t3", "link": "https://reddit.com/new", "snippet": "s", "query": "q"},
    ]

    with patch("src.managers.webcam_discovery._run_discovery_searches", new=AsyncMock(return_value=searched)), \
         patch("src.managers.webcam_discovery._curate_suggestions", new=AsyncMock(return_value=[
             {"name": "New Cam", "url": "https://new.example/stream", "kind": "webpage",
              "location": "", "rationale": "worth it", "discovered_url": "https://reddit.com/new"},
         ])) as mock_curate, \
         patch("src.managers.webcam_discovery.verify_webcam", new=AsyncMock(
             return_value=wv.VerifyResult(ok=True, status="ok", detail="looks fine"),
         )):

        result = await wd.run_webcam_discovery_scan(sources_mgr, suggestions_mgr)

    curated_input = mock_curate.call_args.args[0]
    assert [c["link"] for c in curated_input] == ["https://reddit.com/new"]

    assert result is not None and "New Cam" in result
    stored = suggestions_mgr.list_by_status("pending")
    assert [s.name for s in stored] == ["New Cam", "Already"]
    assert [s for s in stored if s.name == "New Cam"][0].verify_status == "ok"


@pytest.mark.asyncio
async def test_run_webcam_discovery_scan_drops_ideas_that_fail_verification(tmp_path):
    sources_mgr = make_sources_manager(tmp_path)
    suggestions_mgr = make_suggestions_manager(tmp_path)
    searched = [{"title": "t", "link": "https://reddit.com/x", "snippet": "s", "query": "q"}]

    with patch("src.managers.webcam_discovery._run_discovery_searches", new=AsyncMock(return_value=searched)), \
         patch("src.managers.webcam_discovery._curate_suggestions", new=AsyncMock(return_value=[
             {"name": "Dead Cam", "url": "https://dead.example/stream", "kind": "snapshot",
              "location": "", "rationale": "worth it", "discovered_url": "https://reddit.com/x"},
         ])), \
         patch("src.managers.webcam_discovery.verify_webcam", new=AsyncMock(
             return_value=wv.VerifyResult(ok=False, status="unreachable", detail="404"),
         )):

        result = await wd.run_webcam_discovery_scan(sources_mgr, suggestions_mgr)

    assert result is None
    assert suggestions_mgr.list() == []


@pytest.mark.asyncio
async def test_run_webcam_discovery_scan_returns_none_when_nothing_new(tmp_path):
    sources_mgr = make_sources_manager(tmp_path)
    suggestions_mgr = make_suggestions_manager(tmp_path)
    with patch("src.managers.webcam_discovery._run_discovery_searches", new=AsyncMock(return_value=[])):
        result = await wd.run_webcam_discovery_scan(sources_mgr, suggestions_mgr)
    assert result is None


@pytest.mark.asyncio
async def test_run_webcam_discovery_scan_returns_none_when_curation_finds_nothing(tmp_path):
    sources_mgr = make_sources_manager(tmp_path)
    suggestions_mgr = make_suggestions_manager(tmp_path)
    searched = [{"title": "t", "link": "https://reddit.com/x", "snippet": "s", "query": "q"}]
    with patch("src.managers.webcam_discovery._run_discovery_searches", new=AsyncMock(return_value=searched)), \
         patch("src.managers.webcam_discovery._curate_suggestions", new=AsyncMock(return_value=[])):
        result = await wd.run_webcam_discovery_scan(sources_mgr, suggestions_mgr)
    assert result is None
    assert suggestions_mgr.list() == []
