"""Tests for src/managers/trending_manager.py - the GitHub-trending scan +
curation pipeline. Unlike self_upgrade_manager, this never runs the coding
agent itself - it only proposes suggestions for a human to act on, so these
tests focus on storage/dedup correctness and the scan/curate steps in
isolation (network + LLM calls are mocked).
"""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.managers import trending_manager as tm


def make_manager(tmp_path):
    return tm.TrendingSuggestionsManager(data_dir=str(tmp_path / "trending_suggestions"))


def test_create_and_list_newest_first(tmp_path):
    mgr = make_manager(tmp_path)
    first = mgr.create(
        repo="foo/bar", repo_url="https://github.com/foo/bar", description="d",
        language="python", stars="100", rationale="r", integration_prompt="p",
    )
    second = mgr.create(
        repo="baz/qux", repo_url="https://github.com/baz/qux", description="d2",
        language="typescript", stars="200", rationale="r2", integration_prompt="p2",
    )
    listed = mgr.list()
    assert [s.id for s in listed] == [second.id, first.id]
    assert listed[0].status == "pending"


def test_get_update_delete(tmp_path):
    mgr = make_manager(tmp_path)
    s = mgr.create(
        repo="foo/bar", repo_url="https://github.com/foo/bar", description="d",
        language="python", stars="100", rationale="r", integration_prompt="p",
    )

    assert mgr.get(s.id).id == s.id
    assert mgr.get("nope") is None

    updated = mgr.update(s.id, status="implemented", request_id="req-1")
    assert updated.status == "implemented"
    assert updated.request_id == "req-1"
    assert mgr.get(s.id).status == "implemented"

    assert mgr.delete(s.id) is True
    assert mgr.get(s.id) is None
    assert mgr.delete(s.id) is False


def test_list_by_status(tmp_path):
    mgr = make_manager(tmp_path)
    pending = mgr.create(
        repo="foo/bar", repo_url="u", description="d", language="python",
        stars="1", rationale="r", integration_prompt="p",
    )
    dismissed = mgr.create(
        repo="baz/qux", repo_url="u2", description="d2", language="python",
        stars="2", rationale="r2", integration_prompt="p2",
    )
    mgr.update(dismissed.id, status="dismissed")

    assert [s.id for s in mgr.list_by_status("pending")] == [pending.id]
    assert [s.id for s in mgr.list_by_status("dismissed")] == [dismissed.id]


def test_seen_repos_includes_every_status(tmp_path):
    mgr = make_manager(tmp_path)
    mgr.create(repo="foo/bar", repo_url="u", description="d", language="python",
               stars="1", rationale="r", integration_prompt="p")
    s2 = mgr.create(repo="baz/qux", repo_url="u2", description="d2", language="python",
                     stars="2", rationale="r2", integration_prompt="p2")
    mgr.update(s2.id, status="dismissed")

    assert tm.TrendingSuggestionsManager(data_dir=mgr.data_dir).seen_repos() == {"foo/bar", "baz/qux"}


def test_extract_json_array_plain():
    assert tm._extract_json_array('[{"repo": "a/b"}]') == [{"repo": "a/b"}]


def test_extract_json_array_wrapped_in_prose_and_fences():
    text = 'Sure, here you go:\n```json\n[{"repo": "a/b"}]\n```\nHope that helps!'
    assert tm._extract_json_array(text) == [{"repo": "a/b"}]


def test_extract_json_array_returns_none_on_garbage():
    assert tm._extract_json_array("not json at all") is None


@pytest.mark.asyncio
async def test_scan_trending_repos_parses_html():
    html = """
    <html><body>
    <article class="Box-row">
      <h2><a href="/octocat/hello-world">octocat / hello-world</a></h2>
      <p>A friendly demo repo</p>
      <a href="/octocat/hello-world/stargazers">1,234</a>
    </article>
    </body></html>
    """
    mock_resp = MagicMock(status_code=200, text=html)

    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=mock_resp)):
        repos = await tm._scan_trending_repos(["python"], per_language=5)

    assert len(repos) == 1
    assert repos[0]["repo"] == "octocat/hello-world"
    assert repos[0]["repo_url"] == "https://github.com/octocat/hello-world"
    assert repos[0]["description"] == "A friendly demo repo"
    assert repos[0]["stars"] == "1,234"
    assert repos[0]["language"] == "python"


@pytest.mark.asyncio
async def test_scan_trending_repos_skips_non_200():
    mock_resp = MagicMock(status_code=429, text="")
    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=mock_resp)):
        repos = await tm._scan_trending_repos(["python"], per_language=5)
    assert repos == []


@pytest.mark.asyncio
async def test_curate_ideas_filters_to_known_repos():
    repos = [
        {"repo": "foo/bar", "repo_url": "u", "description": "d", "language": "python", "stars": "1"},
    ]
    skills_manager = MagicMock()
    skills_manager.get_all_skills.return_value = []

    fake_response = MagicMock()
    fake_response.choices = [MagicMock(message=MagicMock(content='[{"repo": "foo/bar", "rationale": "r", "integration_prompt": "p"}, {"repo": "unknown/repo", "rationale": "x", "integration_prompt": "y"}]'))]
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=fake_response)

    with patch("openai.AsyncOpenAI", return_value=mock_client):
        ideas = await tm._curate_ideas(repos, skills_manager)

    assert len(ideas) == 1
    assert ideas[0]["repo"] == "foo/bar"
    assert ideas[0]["rationale"] == "r"
    assert ideas[0]["integration_prompt"] == "p"


@pytest.mark.asyncio
async def test_curate_ideas_empty_repos_short_circuits():
    assert await tm._curate_ideas([], MagicMock()) == []


@pytest.mark.asyncio
async def test_curate_ideas_prompt_requires_backend_and_frontend():
    """The actual bug fix: curated ideas used to be steered toward bare
    skills/ tools ("Add a skill that uses <repo> to ...") with no frontend
    integration and no grounding beyond the trending page's one-line blurb.
    The prompt must now demand a whole feature (backend + dashboard UI,
    following this repo's own precedent) grounded in the repo's README."""
    repos = [
        {"repo": "foo/bar", "repo_url": "u", "description": "d", "language": "python",
         "stars": "1", "readme_excerpt": "Implements a novel caching algorithm."},
    ]
    skills_manager = MagicMock()
    skills_manager.get_all_skills.return_value = []

    fake_response = MagicMock()
    fake_response.choices = [MagicMock(message=MagicMock(content="[]"))]
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=fake_response)

    with patch("openai.AsyncOpenAI", return_value=mock_client):
        await tm._curate_ideas(repos, skills_manager)

    sent_prompt = mock_client.chat.completions.create.await_args.kwargs["messages"][0]["content"]
    assert "backend and frontend" in sent_prompt.lower()
    assert "order_explorer_site/frontend" in sent_prompt
    assert "webcams" in sent_prompt.lower()
    assert "Add a skill that uses" not in sent_prompt  # the old biased example wording
    assert "Implements a novel caching algorithm." in sent_prompt  # README excerpt included


@pytest.mark.asyncio
async def test_fetch_readme_excerpt_tries_candidates_and_truncates():
    long_readme = "x" * 1000

    async def fake_get(self, url, *args, **kwargs):
        if url.endswith("/README.md"):
            return MagicMock(status_code=200, text=long_readme)
        return MagicMock(status_code=404, text="")

    with patch("httpx.AsyncClient.get", new=fake_get):
        excerpt = await tm._fetch_readme_excerpt("foo/bar")

    assert excerpt == long_readme[:tm._README_EXCERPT_MAX_CHARS]
    assert len(excerpt) == tm._README_EXCERPT_MAX_CHARS


@pytest.mark.asyncio
async def test_fetch_readme_excerpt_empty_when_all_candidates_missing():
    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=MagicMock(status_code=404, text=""))):
        excerpt = await tm._fetch_readme_excerpt("foo/bar")
    assert excerpt == ""


@pytest.mark.asyncio
async def test_run_trending_scan_dedups_against_seen_repos(tmp_path):
    mgr = make_manager(tmp_path)
    mgr.create(repo="already/seen", repo_url="u", description="d", language="python",
                stars="1", rationale="r", integration_prompt="p")

    scanned = [
        {"repo": "already/seen", "repo_url": "u", "description": "d", "language": "python", "stars": "1"},
        {"repo": "new/repo", "repo_url": "u2", "description": "d2", "language": "python", "stars": "2"},
    ]

    with patch("src.managers.trending_manager._scan_trending_repos", new=AsyncMock(return_value=scanned)), \
         patch("src.managers.trending_manager._fetch_readme_excerpt", new=AsyncMock(return_value="")), \
         patch("src.managers.trending_manager._curate_ideas", new=AsyncMock(return_value=[
             {"repo": "new/repo", "repo_url": "u2", "description": "d2", "language": "python",
              "stars": "2", "rationale": "worth it", "integration_prompt": "add it"},
         ])) as mock_curate:

        result = await tm.run_trending_scan(MagicMock(), mgr)

    # Only the un-seen repo should have been passed to curation.
    curated_input = mock_curate.call_args.args[0]
    assert [r["repo"] for r in curated_input] == ["new/repo"]

    assert result is not None and "new/repo" in result
    stored = mgr.list_by_status("pending")
    assert [s.repo for s in stored] == ["new/repo", "already/seen"]
    assert stored[0].integration_prompt == "add it"


@pytest.mark.asyncio
async def test_run_trending_scan_attaches_readme_excerpts_before_curating(tmp_path):
    mgr = make_manager(tmp_path)
    scanned = [
        {"repo": "new/repo", "repo_url": "u", "description": "d", "language": "python", "stars": "1"},
    ]

    with patch("src.managers.trending_manager._scan_trending_repos", new=AsyncMock(return_value=scanned)), \
         patch("src.managers.trending_manager._fetch_readme_excerpt", new=AsyncMock(return_value="cool algorithm")), \
         patch("src.managers.trending_manager._curate_ideas", new=AsyncMock(return_value=[])) as mock_curate:

        await tm.run_trending_scan(MagicMock(), mgr)

    curated_input = mock_curate.call_args.args[0]
    assert curated_input[0]["readme_excerpt"] == "cool algorithm"


@pytest.mark.asyncio
async def test_run_trending_scan_returns_none_when_nothing_new(tmp_path):
    mgr = make_manager(tmp_path)
    with patch("src.managers.trending_manager._scan_trending_repos", new=AsyncMock(return_value=[])):
        result = await tm.run_trending_scan(MagicMock(), mgr)
    assert result is None


@pytest.mark.asyncio
async def test_run_trending_scan_returns_none_when_curation_finds_nothing(tmp_path):
    mgr = make_manager(tmp_path)
    scanned = [{"repo": "new/repo", "repo_url": "u", "description": "d", "language": "python", "stars": "1"}]
    with patch("src.managers.trending_manager._scan_trending_repos", new=AsyncMock(return_value=scanned)), \
         patch("src.managers.trending_manager._fetch_readme_excerpt", new=AsyncMock(return_value="")), \
         patch("src.managers.trending_manager._curate_ideas", new=AsyncMock(return_value=[])):
        result = await tm.run_trending_scan(MagicMock(), mgr)
    assert result is None
    assert mgr.list() == []
