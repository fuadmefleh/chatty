"""Tests for POST /api/chatty/audio (raw-body upload -> STT -> transcriptions queue)."""
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

import chatty_web_server as server


@pytest.fixture
def client():
    # Plain TestClient (not used as a context manager) does NOT run the
    # @app.on_event("startup") handler, so this never touches SkillsManager.
    return TestClient(server.app)


@pytest.fixture(autouse=True)
def isolated_transcriptions_manager(monkeypatch):
    tmpdir = tempfile.mkdtemp()
    monkeypatch.setattr(server, "transcriptions_manager", server.TranscriptionsManager(data_dir=tmpdir))
    monkeypatch.setattr(server, "WEB_USER_ID", "web_user")
    yield


def _headers(**overrides):
    headers = {
        "X-API-Key": server.API_KEY,
        "X-Device-Id": "device-123",
        "X-Chunk-Start": "2026-07-03T21:08:00.000Z",
        "X-Chunk-Duration": "20.00",
        "X-Source": "ios_app",
    }
    headers.update(overrides)
    return headers


def _mock_stt_response(json_body: dict, status_code: int = 200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_body
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        import httpx
        resp.raise_for_status.side_effect = httpx.HTTPStatusError("error", request=MagicMock(), response=resp)
    return resp


def test_wrong_api_key_rejected(client):
    resp = client.post(
        "/api/chatty/audio",
        content=b"fake-m4a-bytes",
        headers=_headers(**{"X-API-Key": "wrong"}),
    )
    assert resp.status_code == 401


def test_empty_body_rejected(client):
    resp = client.post("/api/chatty/audio", content=b"", headers=_headers())
    assert resp.status_code == 400


def test_valid_chunk_accepted_and_transcribed_plain_text(client):
    mock_post = AsyncMock(return_value=_mock_stt_response({"text": "buy milk tomorrow", "segments": [], "language": "en"}))

    with patch("httpx.AsyncClient.post", mock_post):
        resp = client.post(
            "/api/chatty/audio",
            content=b"fake-m4a-bytes",
            headers=_headers(),
        )

    assert resp.status_code == 202
    assert resp.json() == {"accepted": True}

    mock_post.assert_awaited_once()
    call_kwargs = mock_post.await_args.kwargs
    assert call_kwargs["files"]["file"][1] == b"fake-m4a-bytes"
    assert call_kwargs["data"]["diarize"] == "true"

    pending = server.transcriptions_manager.get_pending("web_user")
    assert len(pending) == 1
    assert "buy milk tomorrow" in pending[0].content
    assert "device-123" in pending[0].content
    assert "2026-07-03T21:08:00.000Z" in pending[0].content
    assert pending[0].source == "ios_app"


def test_diarized_segments_formatted_per_speaker(client):
    stt_result = {
        "text": "ignored when segments have speakers",
        "segments": [
            {"speaker": "SPEAKER_00", "text": "how's the rocket project going"},
            {"speaker": "SPEAKER_01", "text": "pretty well, launch is next week"},
        ],
        "language": "en",
    }
    mock_post = AsyncMock(return_value=_mock_stt_response(stt_result))

    with patch("httpx.AsyncClient.post", mock_post):
        resp = client.post("/api/chatty/audio", content=b"fake-m4a-bytes", headers=_headers())

    assert resp.status_code == 202
    pending = server.transcriptions_manager.get_pending("web_user")
    assert len(pending) == 1
    assert "SPEAKER_00: how's the rocket project going" in pending[0].content
    assert "SPEAKER_01: pretty well, launch is next week" in pending[0].content


def test_no_speech_produces_no_pending_transcription(client):
    mock_post = AsyncMock(return_value=_mock_stt_response({"text": "", "segments": [], "language": "en"}))

    with patch("httpx.AsyncClient.post", mock_post):
        resp = client.post("/api/chatty/audio", content=b"fake-m4a-bytes", headers=_headers())

    assert resp.status_code == 202
    assert server.transcriptions_manager.get_pending("web_user") == []


def test_stt_engine_failure_still_returns_202_but_stores_nothing(client):
    mock_post = AsyncMock(side_effect=ConnectionError("stt engine unreachable"))

    with patch("httpx.AsyncClient.post", mock_post):
        resp = client.post("/api/chatty/audio", content=b"fake-m4a-bytes", headers=_headers())

    # Client already got 202 before the background task ran the failing STT call.
    assert resp.status_code == 202
    assert server.transcriptions_manager.get_pending("web_user") == []


# ── Assistant mode (X-Mode: assistant + wake-word push) ─────────────────────
def test_assistant_mode_without_wake_word_transcribed_normally(client):
    """X-Mode: assistant chunks that don't mention "chatty" behave exactly
    like non-assistant chunks: mined into the pending queue, no push."""
    mock_post = AsyncMock(return_value=_mock_stt_response({"text": "buy milk tomorrow", "segments": [], "language": "en"}))
    mock_push = AsyncMock()

    with patch("httpx.AsyncClient.post", mock_post), patch.object(server, "_push_assistant_response", mock_push):
        resp = client.post(
            "/api/chatty/audio",
            content=b"fake-m4a-bytes",
            headers=_headers(**{"X-Mode": "assistant"}),
        )

    assert resp.status_code == 202
    mock_push.assert_not_awaited()
    pending = server.transcriptions_manager.get_pending("web_user")
    assert len(pending) == 1
    assert "buy milk tomorrow" in pending[0].content


def test_non_assistant_mode_ignores_wake_word(client):
    """Without X-Mode: assistant, a "chatty" mention is just text - preserves
    existing behaviour exactly."""
    mock_post = AsyncMock(return_value=_mock_stt_response({"text": "hey chatty remind me to call mom", "segments": [], "language": "en"}))
    mock_push = AsyncMock()

    with patch("httpx.AsyncClient.post", mock_post), patch.object(server, "_push_assistant_response", mock_push):
        resp = client.post("/api/chatty/audio", content=b"fake-m4a-bytes", headers=_headers())

    assert resp.status_code == 202
    mock_push.assert_not_awaited()
    pending = server.transcriptions_manager.get_pending("web_user")
    assert len(pending) == 1
    assert "hey chatty remind me to call mom" in pending[0].content


def test_assistant_mode_wake_word_triggers_push_and_skips_mining(client):
    mock_post = AsyncMock(return_value=_mock_stt_response(
        {"text": "hey Chatty what's the weather today", "segments": [], "language": "en"}
    ))
    mock_push = AsyncMock()

    with patch("httpx.AsyncClient.post", mock_post), patch.object(server, "_push_assistant_response", mock_push):
        resp = client.post(
            "/api/chatty/audio",
            content=b"fake-m4a-bytes",
            headers=_headers(**{"X-Mode": "assistant"}),
        )

    assert resp.status_code == 202
    mock_push.assert_awaited_once_with("device-123", "what's the weather today")
    # Skipped mining: the wake-word chunk never enters the pending queue.
    assert server.transcriptions_manager.get_pending("web_user") == []


def test_assistant_mode_wake_word_alone_uses_fallback_prompt(client):
    """Saying just "chatty" with nothing following falls back to a synthesized
    prompt rather than an empty query."""
    mock_post = AsyncMock(return_value=_mock_stt_response({"text": "Chatty", "segments": [], "language": "en"}))
    mock_push = AsyncMock()

    with patch("httpx.AsyncClient.post", mock_post), patch.object(server, "_push_assistant_response", mock_push):
        resp = client.post(
            "/api/chatty/audio",
            content=b"fake-m4a-bytes",
            headers=_headers(**{"X-Mode": "assistant"}),
        )

    assert resp.status_code == 202
    mock_push.assert_awaited_once()
    call_args = mock_push.await_args.args
    assert call_args[0] == "device-123"
    assert call_args[1] == server._ASSISTANT_FALLBACK_PROMPT
    assert server.transcriptions_manager.get_pending("web_user") == []
