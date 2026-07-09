"""Tests for the async wiki-reorganization workflow
(/api/chatty/memory/reorganize/propose|apply|status).

propose/apply kick off a FastAPI BackgroundTasks job and return an
immediate "proposing"/"applying" snapshot; the job itself runs to
completion before TestClient's synchronous request cycle returns control
here, so the *response body* reflects the pre-task snapshot while a
follow-up GET /status observes the completed result - exactly mirroring
what a real client sees by polling after navigating back to the page.
"""
import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

import chatty_web_server as server
from src.core.memory import MemoryManager
from src.managers import wiki_reorganize_manager
from src.web import config


@pytest.fixture
def client():
    return TestClient(server.app)


@pytest.fixture(autouse=True)
def isolated_state_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(wiki_reorganize_manager, "_STATE_DIR", tmp_path)
    monkeypatch.setattr(config, "WEB_USER_ID", "web_user")
    yield


def _auth_headers():
    return {"X-API-Key": config.API_KEY}


SAMPLE_TARGET_PAGES = [
    {
        "type": "entity", "slug": "jane", "title": "Jane", "summary": "Spouse",
        "source_pages": ["concept/family"], "already_exists": False,
    },
    {
        "type": "entity", "slug": "sam", "title": "Sam", "summary": "Kid",
        "source_pages": ["concept/family"], "already_exists": False,
    },
]


def test_status_defaults_to_idle(client):
    resp = client.get("/api/chatty/memory/reorganize/status", headers=_auth_headers())
    assert resp.status_code == 200
    assert resp.json() == {
        "status": "idle", "target_pages": None, "applied_keys": [],
        "error": None, "apply_result": None, "updated_at": None,
    }


def test_propose_runs_in_background_and_status_reflects_result(client, monkeypatch):
    monkeypatch.setattr(
        MemoryManager, "propose_reorganization",
        AsyncMock(return_value={"target_pages": SAMPLE_TARGET_PAGES}),
    )

    resp = client.post("/api/chatty/memory/reorganize/propose", headers=_auth_headers())
    assert resp.status_code == 200
    # Response reflects the pre-task snapshot returned by the route itself.
    assert resp.json()["status"] == "proposing"

    status = client.get("/api/chatty/memory/reorganize/status", headers=_auth_headers()).json()
    assert status["status"] == "proposed"
    assert status["target_pages"] == SAMPLE_TARGET_PAGES
    assert status["applied_keys"] == []
    assert status["error"] is None


def test_propose_error_recorded_in_status(client, monkeypatch):
    monkeypatch.setattr(
        MemoryManager, "propose_reorganization",
        AsyncMock(side_effect=RuntimeError("llm unavailable")),
    )

    client.post("/api/chatty/memory/reorganize/propose", headers=_auth_headers())

    status = client.get("/api/chatty/memory/reorganize/status", headers=_auth_headers()).json()
    assert status["status"] == "propose_error"
    assert "llm unavailable" in status["error"]
    assert status["target_pages"] is None


def test_repeated_propose_while_running_does_not_restart(client, monkeypatch):
    mock_propose = AsyncMock(return_value={"target_pages": SAMPLE_TARGET_PAGES})
    monkeypatch.setattr(MemoryManager, "propose_reorganization", mock_propose)

    # Simulate a job already mid-flight (as if a prior request started it and
    # hasn't finished, without needing a slow real background task here).
    wiki_reorganize_manager.start_proposing("web_user")

    resp = client.post("/api/chatty/memory/reorganize/propose", headers=_auth_headers())
    assert resp.json()["status"] == "proposing"
    mock_propose.assert_not_called()


def test_apply_selected_subset_keeps_full_proposal_and_accumulates_applied_keys(client, monkeypatch):
    wiki_reorganize_manager.set_proposed("web_user", SAMPLE_TARGET_PAGES)
    monkeypatch.setattr(
        MemoryManager, "apply_reorganization",
        AsyncMock(return_value="Wrote 1 page."),
    )

    resp = client.post(
        "/api/chatty/memory/reorganize/apply", headers=_auth_headers(),
        json={"target_pages": [SAMPLE_TARGET_PAGES[0]]},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "applying"

    status = client.get("/api/chatty/memory/reorganize/status", headers=_auth_headers()).json()
    assert status["status"] == "applied"
    assert status["apply_result"] == "Wrote 1 page."
    assert status["applied_keys"] == ["entity/jane"]
    # The full proposal (including the unselected page) is still intact.
    assert status["target_pages"] == SAMPLE_TARGET_PAGES


def test_apply_error_recorded_in_status(client, monkeypatch):
    wiki_reorganize_manager.set_proposed("web_user", SAMPLE_TARGET_PAGES)
    monkeypatch.setattr(
        MemoryManager, "apply_reorganization",
        AsyncMock(side_effect=RuntimeError("disk full")),
    )

    client.post(
        "/api/chatty/memory/reorganize/apply", headers=_auth_headers(),
        json={"target_pages": [SAMPLE_TARGET_PAGES[0]]},
    )

    status = client.get("/api/chatty/memory/reorganize/status", headers=_auth_headers()).json()
    assert status["status"] == "apply_error"
    assert "disk full" in status["error"]


def test_reorganize_endpoints_require_auth(client):
    assert client.get("/api/chatty/memory/reorganize/status").status_code == 401
    assert client.post("/api/chatty/memory/reorganize/propose").status_code == 401
    assert client.post("/api/chatty/memory/reorganize/apply", json={"target_pages": []}).status_code == 401
