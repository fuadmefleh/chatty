"""Tests for POST /api/chatty/requests/retry-merges - the on-demand version
of the heartbeat's automatic merge_pending retry (see
self_upgrade_manager.retry_pending_merges and HeartbeatManager._process_pending_merges)."""
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

import chatty_web_server as server


@pytest.fixture
def client():
    # Plain TestClient (not used as a context manager) does NOT run the
    # @app.on_event("startup") handler, so this never touches SkillsManager.
    return TestClient(server.app)


def _headers(**overrides):
    headers = {"X-API-Key": server.API_KEY}
    headers.update(overrides)
    return headers


def test_retry_merges_requires_auth(client):
    resp = client.post("/api/chatty/requests/retry-merges")
    assert resp.status_code == 401


def test_retry_merges_delegates_and_returns_summaries(client):
    mock_retry = AsyncMock(return_value=["🔧 Deferred merge completed: fix a bug"])
    with patch("src.managers.self_upgrade_manager.retry_pending_merges", mock_retry):
        resp = client.post("/api/chatty/requests/retry-merges", headers=_headers())

    assert resp.status_code == 200
    assert resp.json() == {"summaries": ["🔧 Deferred merge completed: fix a bug"]}
    mock_retry.assert_awaited_once()
    args, kwargs = mock_retry.await_args
    assert args[0] is server.feature_requests_manager
    assert kwargs["send_message_callback"] is None
    assert kwargs["user_id"] == server.WEB_USER_ID


def test_retry_merges_empty_when_nothing_pending(client):
    mock_retry = AsyncMock(return_value=[])
    with patch("src.managers.self_upgrade_manager.retry_pending_merges", mock_retry):
        resp = client.post("/api/chatty/requests/retry-merges", headers=_headers())

    assert resp.status_code == 200
    assert resp.json() == {"summaries": []}
