"""Tests for the webcam sources & suggestions endpoints
(/api/chatty/webcam-sources, /api/chatty/webcam-suggestions)."""
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, AsyncMock

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

import chatty_web_server as server
from src.managers.webcam_manager import WebcamSourcesManager, WebcamSuggestionsManager
from src.web import config, state


@pytest.fixture
def client():
    return TestClient(server.app)


@pytest.fixture(autouse=True)
def isolated_managers(monkeypatch):
    data_dir = tempfile.mkdtemp()
    monkeypatch.setattr(state, "webcam_sources_manager", WebcamSourcesManager(data_dir=data_dir))
    monkeypatch.setattr(state, "webcam_suggestions_manager", WebcamSuggestionsManager(data_dir=data_dir))
    yield


def auth_headers():
    return {"X-API-Key": config.API_KEY}


def test_sources_list_starts_empty(client):
    resp = client.get("/api/chatty/webcam-sources", headers=auth_headers())
    assert resp.status_code == 200
    assert resp.json() == []


def test_create_list_update_delete_source(client):
    create_resp = client.post(
        "/api/chatty/webcam-sources", headers=auth_headers(),
        json={"name": "Times Square Cam", "url": "https://cam.example/1", "kind": "snapshot", "location": "NYC"},
    )
    assert create_resp.status_code == 201
    source = create_resp.json()
    assert source["source"] == "manual"
    assert source["enabled"] is True

    listed = client.get("/api/chatty/webcam-sources", headers=auth_headers()).json()
    assert [s["id"] for s in listed] == [source["id"]]

    update_resp = client.put(
        f"/api/chatty/webcam-sources/{source['id']}", headers=auth_headers(), json={"enabled": False},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["enabled"] is False

    delete_resp = client.delete(f"/api/chatty/webcam-sources/{source['id']}", headers=auth_headers())
    assert delete_resp.status_code == 200
    assert client.get("/api/chatty/webcam-sources", headers=auth_headers()).json() == []


def test_create_source_missing_fields_rejected(client):
    resp = client.post(
        "/api/chatty/webcam-sources", headers=auth_headers(),
        json={"name": "", "url": "https://cam.example/1"},
    )
    assert resp.status_code == 400


def test_create_source_invalid_kind_rejected(client):
    resp = client.post(
        "/api/chatty/webcam-sources", headers=auth_headers(),
        json={"name": "Cam", "url": "https://cam.example/1", "kind": "not-a-kind"},
    )
    assert resp.status_code == 400


def test_update_source_invalid_kind_rejected(client):
    source = client.post(
        "/api/chatty/webcam-sources", headers=auth_headers(),
        json={"name": "Cam", "url": "https://cam.example/1"},
    ).json()

    resp = client.put(
        f"/api/chatty/webcam-sources/{source['id']}", headers=auth_headers(), json={"kind": "not-a-kind"},
    )
    assert resp.status_code == 400


def test_update_unknown_source_404s(client):
    resp = client.put("/api/chatty/webcam-sources/no-such-id", headers=auth_headers(), json={"enabled": False})
    assert resp.status_code == 404


def test_delete_unknown_source_404s(client):
    resp = client.delete("/api/chatty/webcam-sources/no-such-id", headers=auth_headers())
    assert resp.status_code == 404


def test_suggestions_scan_returns_list(client):
    with patch("src.web.routers.webcam.run_webcam_discovery_scan", new=AsyncMock(return_value="ok")):
        resp = client.post("/api/chatty/webcam-suggestions/scan", headers=auth_headers())
    assert resp.status_code == 200
    assert resp.json() == []


def test_approve_suggestion_creates_linked_source(client):
    suggestion = state.webcam_suggestions_manager.create(
        name="Discovered Cam", url="https://cam.example/discovered",
        discovered_url="https://reddit.com/thread", kind="snapshot", location="NYC", rationale="looks real",
    )

    resp = client.post(f"/api/chatty/webcam-suggestions/{suggestion.id}/approve", headers=auth_headers())
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "approved"
    assert body["source_id"] is not None

    sources = client.get("/api/chatty/webcam-sources", headers=auth_headers()).json()
    assert len(sources) == 1
    assert sources[0]["id"] == body["source_id"]
    assert sources[0]["source"] == "suggestion"
    assert sources[0]["suggestion_id"] == suggestion.id
    assert sources[0]["name"] == "Discovered Cam"

    # Approving again is rejected - it's already been actioned.
    second_resp = client.post(f"/api/chatty/webcam-suggestions/{suggestion.id}/approve", headers=auth_headers())
    assert second_resp.status_code == 409


def test_dismiss_and_delete_suggestion(client):
    suggestion = state.webcam_suggestions_manager.create(
        name="Cam", url="https://cam.example", discovered_url="https://reddit.com/x",
    )

    dismiss_resp = client.post(f"/api/chatty/webcam-suggestions/{suggestion.id}/dismiss", headers=auth_headers())
    assert dismiss_resp.status_code == 200
    assert dismiss_resp.json()["status"] == "dismissed"

    second_dismiss = client.post(f"/api/chatty/webcam-suggestions/{suggestion.id}/dismiss", headers=auth_headers())
    assert second_dismiss.status_code == 409

    delete_resp = client.delete(f"/api/chatty/webcam-suggestions/{suggestion.id}", headers=auth_headers())
    assert delete_resp.status_code == 200
    assert client.get("/api/chatty/webcam-suggestions", headers=auth_headers()).json() == []


def test_approve_unknown_suggestion_404s(client):
    resp = client.post("/api/chatty/webcam-suggestions/no-such-id/approve", headers=auth_headers())
    assert resp.status_code == 404


def test_delete_unknown_suggestion_404s(client):
    resp = client.delete("/api/chatty/webcam-suggestions/no-such-id", headers=auth_headers())
    assert resp.status_code == 404
