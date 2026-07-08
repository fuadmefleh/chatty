"""Unit tests for the web-based Gmail reconnect flow in
skills/gmail/gmail_integration.py: status reporting, and the
state/PKCE-verifier bookkeeping around get_gmail_auth_url /
complete_gmail_auth. The real Google network call (Flow.fetch_token) is
monkeypatched out - these tests are about our own state machine, not
Google's OAuth server.
"""
import pickle
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from skills.gmail import gmail_integration as gmail


WEB_CLIENT_SECRETS = {
    "web": {
        "client_id": "test-client-id.apps.googleusercontent.com",
        "client_secret": "test-secret",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["https://fuadmefleh.fyi/api/chatty/gmail/callback"],
    }
}


@pytest.fixture(autouse=True)
def isolated_paths(tmp_path, monkeypatch):
    """Point every path gmail_integration touches at a scratch dir, and
    clear in-memory OAuth state between tests."""
    monkeypatch.setattr(gmail, "TOKEN_FILE", tmp_path / "gmail_token.json")
    monkeypatch.setattr(gmail, "WEB_CREDENTIALS_FILE", tmp_path / "web_credentials.json")
    gmail._pending_oauth_states.clear()
    yield
    gmail._pending_oauth_states.clear()


def write_web_credentials():
    import json
    gmail.WEB_CREDENTIALS_FILE.write_text(json.dumps(WEB_CLIENT_SECRETS))


def fake_creds(valid=False, expired=False, refresh_token=None):
    return SimpleNamespace(valid=valid, expired=expired, refresh_token=refresh_token)


# ── get_gmail_status ─────────────────────────────────────────────────────────

def test_status_disconnected_when_no_token_file():
    assert gmail.get_gmail_status() == {"status": "disconnected", "reconnect_available": False}


def test_status_reconnect_available_reflects_web_credentials_file():
    write_web_credentials()
    assert gmail.get_gmail_status() == {"status": "disconnected", "reconnect_available": True}


def test_status_connected_when_token_valid():
    with open(gmail.TOKEN_FILE, "wb") as f:
        pickle.dump(fake_creds(valid=True), f)
    assert gmail.get_gmail_status()["status"] == "connected"


def test_status_expired_when_refreshable():
    with open(gmail.TOKEN_FILE, "wb") as f:
        pickle.dump(fake_creds(valid=False, expired=True, refresh_token="rt"), f)
    assert gmail.get_gmail_status()["status"] == "expired"


def test_status_disconnected_when_expired_without_refresh_token():
    with open(gmail.TOKEN_FILE, "wb") as f:
        pickle.dump(fake_creds(valid=False, expired=True, refresh_token=None), f)
    assert gmail.get_gmail_status()["status"] == "disconnected"


def test_status_disconnected_on_corrupt_token_file():
    gmail.TOKEN_FILE.write_bytes(b"not a pickle")
    assert gmail.get_gmail_status()["status"] == "disconnected"


# ── get_gmail_auth_url ───────────────────────────────────────────────────────

def test_get_gmail_auth_url_raises_without_web_credentials():
    with pytest.raises(FileNotFoundError):
        gmail.get_gmail_auth_url()


def test_get_gmail_auth_url_stages_pending_state():
    write_web_credentials()
    url = gmail.get_gmail_auth_url()

    assert url.startswith("https://accounts.google.com/o/oauth2/auth")
    assert len(gmail._pending_oauth_states) == 1
    state = next(iter(gmail._pending_oauth_states))
    assert f"state={state}" in url
    code_verifier, issued_at = gmail._pending_oauth_states[state]
    assert isinstance(code_verifier, str) and len(code_verifier) >= 43
    assert issued_at <= time.time()


# ── complete_gmail_auth ──────────────────────────────────────────────────────

def test_complete_gmail_auth_rejects_unknown_state():
    write_web_credentials()
    with pytest.raises(ValueError):
        gmail.complete_gmail_auth("some-code", "state-that-was-never-issued")


def test_complete_gmail_auth_rejects_expired_state():
    write_web_credentials()
    gmail._pending_oauth_states["stale"] = ("verifier", time.time() - gmail.OAUTH_STATE_TTL_SECONDS - 1)
    with pytest.raises(ValueError):
        gmail.complete_gmail_auth("some-code", "stale")
    # Pruned on the same pass, not left dangling.
    assert "stale" not in gmail._pending_oauth_states


def test_complete_gmail_auth_exchanges_code_and_persists_token(monkeypatch):
    write_web_credentials()
    gmail.get_gmail_auth_url()
    state = next(iter(gmail._pending_oauth_states))
    expected_verifier = gmail._pending_oauth_states[state][0]

    sentinel_creds = fake_creds(valid=True)
    captured = {}

    class FakeFlow:
        def __init__(self, code_verifier):
            self.code_verifier = code_verifier
            self.credentials = sentinel_creds

        @classmethod
        def from_client_secrets_file(cls, path, scopes, redirect_uri, **kwargs):
            captured["autogenerate_code_verifier"] = kwargs.get("autogenerate_code_verifier")
            captured["code_verifier"] = kwargs.get("code_verifier")
            return cls(kwargs.get("code_verifier"))

        def fetch_token(self, **kwargs):
            captured["fetch_token_kwargs"] = kwargs

    monkeypatch.setattr(gmail, "Flow", FakeFlow)

    gmail.complete_gmail_auth("the-auth-code", state)

    # Same PKCE verifier that authorization_url generated must be reused,
    # not re-generated - otherwise Google would reject the exchange.
    assert captured["autogenerate_code_verifier"] is False
    assert captured["code_verifier"] == expected_verifier
    assert captured["fetch_token_kwargs"] == {"code": "the-auth-code"}

    # State is single-use.
    assert state not in gmail._pending_oauth_states

    # Token persisted in the same pickle format get_gmail_service() expects.
    # (pickle.load always returns a new object, so compare by value.)
    with open(gmail.TOKEN_FILE, "rb") as f:
        saved = pickle.load(f)
    assert saved == sentinel_creds


# ── disconnect_gmail ─────────────────────────────────────────────────────────

def test_disconnect_gmail_removes_token_and_reports_whether_one_existed():
    assert gmail.disconnect_gmail() is False

    with open(gmail.TOKEN_FILE, "wb") as f:
        pickle.dump(fake_creds(valid=True), f)
    assert gmail.disconnect_gmail() is True
    assert not gmail.TOKEN_FILE.exists()
