"""Tests for the TTS skill (skills/tts/): provider abstraction and the
speak_text tool."""
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core import config
from src.core.request_context import current_chat_id
from skills.tts import providers
from skills.tts import tools as tts_tools
from skills.tts.tools import SpeakTextTool


class _FakeResponse:
    """Minimal stand-in for aiohttp.ClientResponse used as an async context manager."""

    def __init__(self, status=200, json_data=None, text_data="", read_data=b""):
        self.status = status
        self._json_data = json_data
        self._text_data = text_data
        self._read_data = read_data

    async def json(self):
        return self._json_data

    async def text(self):
        return self._text_data

    async def read(self):
        return self._read_data

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False


class _FakeSession:
    """Minimal stand-in for aiohttp.ClientSession; `responder` maps a
    (method, url) call to the canned _FakeResponse to return."""

    def __init__(self, responder):
        self._responder = responder
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append(("POST", url, kwargs))
        return self._responder("POST", url, kwargs)

    def get(self, url, **kwargs):
        self.calls.append(("GET", url, kwargs))
        return self._responder("GET", url, kwargs)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False


def _patch_session(monkeypatch, responder):
    fake_session = _FakeSession(responder)
    monkeypatch.setattr(providers.aiohttp, "ClientSession", lambda *a, **kw: fake_session)
    return fake_session


# --- synthesize_local ---

@pytest.mark.asyncio
async def test_synthesize_local_happy_path(monkeypatch):
    def responder(method, url, kwargs):
        if url.endswith("/generate"):
            assert kwargs["json"]["text"] == "hello"
            return _FakeResponse(status=200, json_data={"job_id": "job-1", "status": "queued"})
        if "/status/" in url:
            return _FakeResponse(status=200, json_data={"job_id": "job-1", "status": "completed", "filename": "job-1.mp3"})
        if "/download/" in url:
            return _FakeResponse(status=200, read_data=b"fake-mp3-bytes")
        raise AssertionError(f"unexpected call {method} {url}")

    _patch_session(monkeypatch, responder)

    result = await providers.synthesize_local("hello")

    assert result == b"fake-mp3-bytes"


@pytest.mark.asyncio
async def test_synthesize_local_raises_on_failed_status(monkeypatch):
    def responder(method, url, kwargs):
        if url.endswith("/generate"):
            return _FakeResponse(status=200, json_data={"job_id": "job-1", "status": "queued"})
        if "/status/" in url:
            return _FakeResponse(status=200, json_data={"job_id": "job-1", "status": "failed", "error": "engine crashed"})
        raise AssertionError(f"unexpected call {method} {url}")

    _patch_session(monkeypatch, responder)

    with pytest.raises(RuntimeError, match="engine crashed"):
        await providers.synthesize_local("hello")


# --- synthesize_elevenlabs ---

@pytest.mark.asyncio
async def test_synthesize_elevenlabs_happy_path(monkeypatch):
    monkeypatch.setattr(config, "ELEVENLABS_API_KEY", "key-test")

    def responder(method, url, kwargs):
        assert kwargs["headers"]["xi-api-key"] == "key-test"
        return _FakeResponse(status=200, read_data=b"fake-mp3-bytes")

    _patch_session(monkeypatch, responder)

    result = await providers.synthesize_elevenlabs("hello")

    assert result == b"fake-mp3-bytes"


@pytest.mark.asyncio
async def test_synthesize_elevenlabs_missing_api_key(monkeypatch):
    monkeypatch.setattr(config, "ELEVENLABS_API_KEY", None)

    with pytest.raises(RuntimeError, match="ELEVENLABS_API_KEY"):
        await providers.synthesize_elevenlabs("hello")


# --- synthesize_openai ---

@pytest.mark.asyncio
async def test_synthesize_openai_happy_path(monkeypatch):
    monkeypatch.setattr(config, "OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr(config, "OPENAI_TTS_MODEL", "tts-1")
    monkeypatch.setattr(config, "OPENAI_TTS_VOICE", "alloy")

    fake_response = MagicMock()
    fake_response.read = AsyncMock(return_value=b"fake-mp3-bytes")
    fake_client = MagicMock()
    fake_client.audio.speech.create = AsyncMock(return_value=fake_response)
    monkeypatch.setattr(providers, "AsyncOpenAI", MagicMock(return_value=fake_client))

    result = await providers.synthesize_openai("hello")

    assert result == b"fake-mp3-bytes"
    _, kwargs = fake_client.audio.speech.create.call_args
    assert kwargs["model"] == "tts-1"
    assert kwargs["voice"] == "alloy"


@pytest.mark.asyncio
async def test_synthesize_openai_missing_api_key(monkeypatch):
    monkeypatch.setattr(config, "OPENAI_API_KEY", None)

    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        await providers.synthesize_openai("hello")


# --- dispatcher ---

@pytest.mark.asyncio
async def test_dispatcher_selects_provider_from_config(monkeypatch):
    monkeypatch.setattr(config, "TTS_PROVIDER", "local")
    fake = AsyncMock(return_value=b"local-bytes")
    monkeypatch.setattr(providers, "synthesize_local", fake)

    result = await providers.synthesize("hello")

    assert result == b"local-bytes"
    fake.assert_awaited_once()


@pytest.mark.asyncio
async def test_dispatcher_provider_override(monkeypatch):
    monkeypatch.setattr(config, "TTS_PROVIDER", "local")
    fake_local = AsyncMock(return_value=b"local-bytes")
    fake_eleven = AsyncMock(return_value=b"eleven-bytes")
    monkeypatch.setattr(providers, "synthesize_local", fake_local)
    monkeypatch.setattr(providers, "synthesize_elevenlabs", fake_eleven)

    result = await providers.synthesize("hello", provider="elevenlabs")

    assert result == b"eleven-bytes"
    fake_eleven.assert_awaited_once()
    fake_local.assert_not_awaited()


@pytest.mark.asyncio
async def test_dispatcher_unknown_provider_raises():
    with pytest.raises(ValueError, match="Unknown TTS provider"):
        await providers.synthesize("hello", provider="bogus")


# --- SpeakTextTool ---

@pytest.mark.asyncio
async def test_speak_text_tool_sends_voice_when_chat_id_present(monkeypatch):
    tool = SpeakTextTool()
    token = current_chat_id.set(555)
    try:
        monkeypatch.setattr(tts_tools._providers, "synthesize", AsyncMock(return_value=b"fake-mp3"))
        monkeypatch.setattr(tts_tools, "_transcode_to_ogg_opus", AsyncMock(return_value=b"fake-ogg"))
        mock_bot_instance = MagicMock()
        mock_bot_instance.send_voice = AsyncMock()
        mock_bot_instance.send_audio = AsyncMock()
        monkeypatch.setattr(tts_tools, "Bot", MagicMock(return_value=mock_bot_instance))

        result = await tool.execute(text="hello")
        data = json.loads(result)

        assert data["success"] is True
        mock_bot_instance.send_voice.assert_awaited_once()
        mock_bot_instance.send_audio.assert_not_awaited()
        _, kwargs = mock_bot_instance.send_voice.call_args
        assert kwargs["chat_id"] == 555
        assert kwargs["voice"] == b"fake-ogg"
    finally:
        current_chat_id.reset(token)


@pytest.mark.asyncio
async def test_speak_text_tool_returns_error_json_when_chat_id_missing():
    tool = SpeakTextTool()
    assert current_chat_id.get() is None

    result = await tool.execute(text="hello")
    data = json.loads(result)

    assert data["success"] is False
    assert "chat" in data["error"].lower()


@pytest.mark.asyncio
async def test_speak_text_tool_falls_back_to_send_audio_when_ffmpeg_fails(monkeypatch):
    tool = SpeakTextTool()
    token = current_chat_id.set(555)
    try:
        monkeypatch.setattr(tts_tools._providers, "synthesize", AsyncMock(return_value=b"fake-mp3"))
        monkeypatch.setattr(tts_tools, "_transcode_to_ogg_opus", AsyncMock(return_value=None))
        mock_bot_instance = MagicMock()
        mock_bot_instance.send_voice = AsyncMock()
        mock_bot_instance.send_audio = AsyncMock()
        monkeypatch.setattr(tts_tools, "Bot", MagicMock(return_value=mock_bot_instance))

        result = await tool.execute(text="hello")
        data = json.loads(result)

        assert data["success"] is True
        mock_bot_instance.send_audio.assert_awaited_once()
        mock_bot_instance.send_voice.assert_not_awaited()
        _, kwargs = mock_bot_instance.send_audio.call_args
        assert kwargs["audio"] == b"fake-mp3"
    finally:
        current_chat_id.reset(token)


@pytest.mark.asyncio
async def test_speak_text_tool_returns_error_when_synthesis_fails(monkeypatch):
    tool = SpeakTextTool()
    token = current_chat_id.set(555)
    try:
        monkeypatch.setattr(tts_tools._providers, "synthesize", AsyncMock(side_effect=RuntimeError("boom")))

        result = await tool.execute(text="hello")
        data = json.loads(result)

        assert data["success"] is False
        assert "boom" in data["error"]
    finally:
        current_chat_id.reset(token)


def test_tool_has_required_attributes():
    tool = SpeakTextTool()
    assert tool.name == "speak_text"
    assert tool.parameters["type"] == "object"
    assert tool.parameters["required"] == ["text"]
