"""Tests for the Gmail reconnect endpoints (GET .../status, .../connect-url,
.../callback, POST .../disconnect) in chatty_web_server.py.

The actual OAuth exchange (Flow.fetch_token) is a real network call to
Google - these tests monkeypatch gmail_integration's functions rather than
hitting the network. See test_gmail_integration.py for unit tests of the
underlying OAuth-state/PKCE logic itself.
"""
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

import chatty_web_server as server
from skills.gmail import gmail_integration
from src.web import config


@pytest.fixture
def client():
    return TestClient(server.app, follow_redirects=False)


def auth_headers():
    return {"X-API-Key": config.API_KEY}


def test_gmail_status_requires_api_key(client):
    resp = client.get("/api/chatty/gmail/status")
    assert resp.status_code == 401


def test_gmail_status_passes_through_integration_result(client, monkeypatch):
    monkeypatch.setattr(
        gmail_integration, "get_gmail_status",
        lambda: {"status": "expired", "reconnect_available": True},
    )
    resp = client.get("/api/chatty/gmail/status", headers=auth_headers())
    assert resp.status_code == 200
    assert resp.json() == {"status": "expired", "reconnect_available": True}


def test_gmail_connect_url_returns_url(client, monkeypatch):
    monkeypatch.setattr(
        gmail_integration, "get_gmail_auth_url",
        lambda: "https://accounts.google.com/o/oauth2/auth?state=abc",
    )
    resp = client.get("/api/chatty/gmail/connect-url", headers=auth_headers())
    assert resp.status_code == 200
    assert resp.json() == {"url": "https://accounts.google.com/o/oauth2/auth?state=abc"}


def test_gmail_connect_url_400_when_web_client_not_configured(client, monkeypatch):
    def _raise():
        raise FileNotFoundError("Web OAuth client not found")
    monkeypatch.setattr(gmail_integration, "get_gmail_auth_url", _raise)

    resp = client.get("/api/chatty/gmail/connect-url", headers=auth_headers())
    assert resp.status_code == 400


def test_gmail_callback_redirects_to_settings_on_success(client, monkeypatch):
    calls = {}
    def _complete(code, state):
        calls["args"] = (code, state)
    monkeypatch.setattr(gmail_integration, "complete_gmail_auth", _complete)

    resp = client.get("/api/chatty/gmail/callback", params={"code": "abc123", "state": "xyz"})
    assert resp.status_code in (302, 307)
    assert resp.headers["location"] == "/settings?gmail=connected"
    assert calls["args"] == ("abc123", "xyz")


def test_gmail_callback_redirects_to_settings_on_failure(client, monkeypatch):
    def _raise(code, state):
        raise ValueError("Unknown or expired OAuth state")
    monkeypatch.setattr(gmail_integration, "complete_gmail_auth", _raise)

    resp = client.get("/api/chatty/gmail/callback", params={"code": "abc123", "state": "xyz"})
    assert resp.status_code in (302, 307)
    assert resp.headers["location"] == "/settings?gmail=error"


def test_gmail_callback_redirects_to_error_when_google_reports_error(client):
    resp = client.get("/api/chatty/gmail/callback", params={"error": "access_denied"})
    assert resp.status_code in (302, 307)
    assert resp.headers["location"] == "/settings?gmail=error"


def test_gmail_callback_redirects_to_error_when_missing_params(client):
    resp = client.get("/api/chatty/gmail/callback")
    assert resp.status_code in (302, 307)
    assert resp.headers["location"] == "/settings?gmail=error"


def test_gmail_callback_is_not_behind_api_key(client, monkeypatch):
    """Google's redirect is a plain browser GET with no custom headers, so
    this route can't require X-API-Key - it must stay reachable without it."""
    monkeypatch.setattr(gmail_integration, "complete_gmail_auth", lambda code, state: None)
    resp = client.get("/api/chatty/gmail/callback", params={"code": "abc", "state": "xyz"})
    assert resp.status_code != 401


def test_gmail_disconnect_requires_api_key(client):
    resp = client.post("/api/chatty/gmail/disconnect")
    assert resp.status_code == 401


def test_gmail_disconnect_calls_integration_and_reports_status(client, monkeypatch):
    called = {"disconnected": False}
    def _disconnect():
        called["disconnected"] = True
        return True
    monkeypatch.setattr(gmail_integration, "disconnect_gmail", _disconnect)
    monkeypatch.setattr(gmail_integration, "WEB_CREDENTIALS_FILE", Path("/nonexistent"))

    resp = client.post("/api/chatty/gmail/disconnect", headers=auth_headers())
    assert resp.status_code == 200
    assert called["disconnected"] is True
    assert resp.json() == {"status": "disconnected", "reconnect_available": False}
