"""Tests for GET /api/chatty/memory - confirms the wiki's structure (pages
with type/tags/summary, plus the index/log) is actually exposed to the web
dashboard, not squashed into the old flat {date, content, filename} shape."""
import sys
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

import chatty_web_server as server
from src.core.wiki_store import WikiStore

USER_ID = "test_web_memory_user"


@pytest.fixture
def client():
    return TestClient(server.app)


@pytest.fixture(autouse=True)
def isolated_memory_dir(monkeypatch):
    tmp_dir = Path(tempfile.mkdtemp())
    monkeypatch.setattr(server, "MEMORY_DIR", tmp_dir)
    monkeypatch.setattr(server, "WEB_USER_ID", USER_ID)
    return tmp_dir


def auth_headers():
    return {"X-API-Key": server.API_KEY}


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
