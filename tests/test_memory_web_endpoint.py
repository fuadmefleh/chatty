"""Tests for GET /api/chatty/memory - confirms the wiki's structure (pages
with type/tags/summary, plus the index/log) is actually exposed to the web
dashboard, not squashed into the old flat {date, content, filename} shape."""
import json
import sys
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

import chatty_web_server as server
from src.core.wiki_store import WikiStore
from src.web import config as web_config

USER_ID = "test_web_memory_user"


@pytest.fixture
def client():
    return TestClient(server.app)


@pytest.fixture(autouse=True)
def isolated_memory_dir(monkeypatch):
    tmp_dir = Path(tempfile.mkdtemp())
    monkeypatch.setattr(web_config, "MEMORY_DIR", tmp_dir)
    monkeypatch.setattr(web_config, "WEB_USER_ID", USER_ID)
    return tmp_dir


def auth_headers():
    return {"X-API-Key": web_config.API_KEY}


def test_memory_endpoint_exposes_wiki_pages_and_catalog(client, isolated_memory_dir):
    long_term_dir = isolated_memory_dir / USER_ID / "long_term"
    wiki_store = WikiStore(USER_ID, long_term_dir)
    wiki_store.write_page(
        type_="entity", slug="sarah", title="Sarah", summary="User's sister.",
        body="- Lives in Austin, TX.", tags=["family"],
    )

    resp = client.get("/api/chatty/memory", headers=auth_headers())

    assert resp.status_code == 200
    data = resp.json()

    assert "wiki_index" in data and isinstance(data["wiki_index"], str)
    assert "Sarah" in data["wiki_index"]
    assert "wiki_log" in data and isinstance(data["wiki_log"], str)

    assert len(data["long_term"]) == 1
    page = data["long_term"][0]
    assert page["title"] == "Sarah"
    assert page["type"] == "entity"
    assert page["slug"] == "sarah"
    assert page["summary"] == "User's sister."
    assert page["tags"] == ["family"]
    assert "Lives in Austin" in page["body"]
    assert "updated" in page
    # Confirms the old flat shape is gone, not just additively present.
    assert "date" not in page
    assert "content" not in page
    assert "filename" not in page


def test_memory_endpoint_empty_wiki_returns_empty_long_term(client, isolated_memory_dir):
    resp = client.get("/api/chatty/memory", headers=auth_headers())

    assert resp.status_code == 200
    data = resp.json()
    assert data["long_term"] == []
    assert "No pages yet" in data["wiki_index"]


def test_get_memory_page_returns_full_page(client, isolated_memory_dir):
    long_term_dir = isolated_memory_dir / USER_ID / "long_term"
    wiki_store = WikiStore(USER_ID, long_term_dir)
    wiki_store.write_page(
        type_="entity", slug="sarah", title="Sarah", summary="User's sister.",
        body="- Lives in Austin, TX.", tags=["family"],
    )

    resp = client.get("/api/chatty/memory/page/entity/sarah", headers=auth_headers())

    assert resp.status_code == 200
    page = resp.json()
    assert page["title"] == "Sarah"
    assert page["type"] == "entity"
    assert page["slug"] == "sarah"
    assert page["summary"] == "User's sister."
    assert page["tags"] == ["family"]
    assert "Lives in Austin" in page["body"]
    assert "updated" in page


def test_get_memory_page_unknown_slug_404s(client, isolated_memory_dir):
    resp = client.get("/api/chatty/memory/page/entity/nonexistent", headers=auth_headers())
    assert resp.status_code == 404


def test_get_memory_page_invalid_type_400s(client, isolated_memory_dir):
    resp = client.get("/api/chatty/memory/page/bogus-type/sarah", headers=auth_headers())
    assert resp.status_code == 400


def test_create_memory_page_endpoint(client, isolated_memory_dir):
    resp = client.post(
        "/api/chatty/memory/page",
        headers=auth_headers(),
        json={"type": "concept", "slug": "budgeting", "title": "Budgeting", "summary": "s", "body": "- a", "tags": ["money"]},
    )

    assert resp.status_code == 201
    page = resp.json()
    assert page["title"] == "Budgeting"
    assert page["slug"] == "budgeting"
    assert page["tags"] == ["money"]

    long_term_dir = isolated_memory_dir / USER_ID / "long_term"
    wiki_store = WikiStore(USER_ID, long_term_dir)
    assert wiki_store.get_page("concept", "budgeting") is not None
    assert "created via dashboard" in wiki_store.read_log()


def test_create_memory_page_duplicate_slug_409s(client, isolated_memory_dir):
    long_term_dir = isolated_memory_dir / USER_ID / "long_term"
    WikiStore(USER_ID, long_term_dir).write_page(type_="concept", slug="budgeting", title="Budgeting", summary="s", body="- a")

    resp = client.post(
        "/api/chatty/memory/page",
        headers=auth_headers(),
        json={"type": "concept", "slug": "budgeting", "title": "Budgeting", "summary": "s", "body": "- a"},
    )
    assert resp.status_code == 409


def test_create_memory_page_invalid_type_400s(client, isolated_memory_dir):
    resp = client.post(
        "/api/chatty/memory/page",
        headers=auth_headers(),
        json={"type": "bogus-type", "slug": "x", "title": "X"},
    )
    assert resp.status_code == 400


def test_update_memory_page_endpoint(client, isolated_memory_dir):
    long_term_dir = isolated_memory_dir / USER_ID / "long_term"
    WikiStore(USER_ID, long_term_dir).write_page(type_="concept", slug="budgeting", title="Budgeting", summary="old", body="- old")

    resp = client.put(
        "/api/chatty/memory/page/concept/budgeting",
        headers=auth_headers(),
        json={"title": "Budgeting", "summary": "new", "body": "- new", "tags": ["money"]},
    )

    assert resp.status_code == 200
    page = resp.json()
    assert page["summary"] == "new"
    assert "new" in page["body"]

    wiki_store = WikiStore(USER_ID, long_term_dir)
    assert "edited via dashboard" in wiki_store.read_log()


def test_update_memory_page_unknown_404s(client, isolated_memory_dir):
    resp = client.put(
        "/api/chatty/memory/page/concept/nonexistent",
        headers=auth_headers(),
        json={"title": "X", "summary": "s", "body": "- a"},
    )
    assert resp.status_code == 404


def test_delete_memory_page_endpoint(client, isolated_memory_dir):
    long_term_dir = isolated_memory_dir / USER_ID / "long_term"
    WikiStore(USER_ID, long_term_dir).write_page(type_="concept", slug="budgeting", title="Budgeting", summary="s", body="- a")

    resp = client.delete("/api/chatty/memory/page/concept/budgeting", headers=auth_headers())
    assert resp.status_code == 200
    assert resp.json() == {"deleted": True}

    follow_up = client.get("/api/chatty/memory/page/concept/budgeting", headers=auth_headers())
    assert follow_up.status_code == 404


def test_delete_memory_page_unknown_404s(client, isolated_memory_dir):
    resp = client.delete("/api/chatty/memory/page/concept/nonexistent", headers=auth_headers())
    assert resp.status_code == 404


def test_get_memory_page_backlinks_endpoint(client, isolated_memory_dir):
    long_term_dir = isolated_memory_dir / USER_ID / "long_term"
    wiki_store = WikiStore(USER_ID, long_term_dir)
    wiki_store.write_page(type_="entity", slug="sarah", title="Sarah", summary="s", body="- Sister.")
    wiki_store.write_page(
        type_="concept", slug="family-trip", title="Family Trip", summary="s",
        body="- Went hiking with [Sarah](pages/entities/sarah.md).",
    )

    resp = client.get("/api/chatty/memory/page/entity/sarah/backlinks", headers=auth_headers())

    assert resp.status_code == 200
    backlinks = resp.json()
    assert len(backlinks) == 1
    assert backlinks[0]["slug"] == "family-trip"
    assert backlinks[0]["type"] == "concept"


def test_get_memory_page_backlinks_unknown_page_404s(client, isolated_memory_dir):
    resp = client.get("/api/chatty/memory/page/entity/nonexistent/backlinks", headers=auth_headers())
    assert resp.status_code == 404


def test_get_memory_health_endpoint_empty_before_lint(client, isolated_memory_dir):
    resp = client.get("/api/chatty/memory/health", headers=auth_headers())

    assert resp.status_code == 200
    health = resp.json()
    assert health["generated_at"] is None
    assert health["orphans"] == []
    assert health["contradictions"] == []
    assert health["coverage_gaps"] == []


class _StubLLM:
    """Minimal async LLM stand-in so lint_wiki()'s contradiction/coverage-gap
    check doesn't make a real network call in this test."""

    async def complete(self, messages, *, response_format="text", temperature=None):
        from types import SimpleNamespace
        return SimpleNamespace(content=json.dumps({"contradictions": [], "coverage_gaps": []}))


@pytest.mark.asyncio
async def test_get_memory_health_endpoint_after_lint_run(client, isolated_memory_dir, monkeypatch):
    from src.core import config
    from src.core.memory import MemoryManager

    # MemoryManager resolves paths off src.core.config.MEMORY_DIR, a separate
    # binding from this file's src.web.config.MEMORY_DIR - both must point at
    # the same isolated tmp dir or lint_wiki() would touch the real memory/ dir.
    monkeypatch.setattr(config, "MEMORY_DIR", isolated_memory_dir)
    monkeypatch.setattr("src.core.memory.get_llm_provider", lambda: _StubLLM())

    long_term_dir = isolated_memory_dir / USER_ID / "long_term"
    WikiStore(USER_ID, long_term_dir).write_page(type_="concept", slug="lonely", title="Lonely Page", summary="s", body="- unlinked")

    manager = MemoryManager(USER_ID)
    await manager.lint_wiki()

    resp = client.get("/api/chatty/memory/health", headers=auth_headers())

    assert resp.status_code == 200
    health = resp.json()
    assert health["generated_at"] is not None
    assert any(o["slug"] == "lonely" for o in health["orphans"])
