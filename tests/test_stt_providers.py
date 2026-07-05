"""Tests for the pluggable STT provider abstraction (src/core/stt/)."""
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core import config
from src.core.stt import factory
from src.core.stt.local_whisper import LocalWhisperProvider
from src.core.stt.openai_provider import OpenAITranscriptionProvider
from src.core.stt.whisperx_http import WhisperXHTTPProvider


@pytest.fixture(autouse=True)
def reset_singleton():
    factory._stt_singleton = None
    yield
    factory._stt_singleton = None


@pytest.mark.asyncio
async def test_openai_transcription_provider_returns_text_only():
    provider = OpenAITranscriptionProvider(api_key="sk-test", model="whisper-1")
    fake_resp = MagicMock(text="hello world")
    provider.client.audio.transcriptions.create = AsyncMock(return_value=fake_resp)

    result = await provider.transcribe(b"fake-audio-bytes", filename_hint="chunk.m4a")

    assert result.text == "hello world"
    assert result.segments is None
    assert result.speaker_embeddings is None
    provider.client.audio.transcriptions.create.assert_awaited_once()
    _, kwargs = provider.client.audio.transcriptions.create.call_args
    assert kwargs["model"] == "whisper-1"


def test_local_whisper_provider_raises_clear_error_without_dependency():
    with pytest.raises(RuntimeError, match="requirements-local-stt.txt"):
        LocalWhisperProvider()


def test_factory_defaults_to_whisperx_http(monkeypatch):
    monkeypatch.setattr(config, "STT_PROVIDER", "whisperx_http")
    monkeypatch.setattr(config, "STT_ENGINE_URL", "http://example.test:8003")

    provider = factory.get_stt_provider()

    assert isinstance(provider, WhisperXHTTPProvider)
    assert provider.base_url == "http://example.test:8003"


def test_factory_selects_openai_provider(monkeypatch):
    monkeypatch.setattr(config, "STT_PROVIDER", "openai")
    monkeypatch.setattr(config, "OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr(config, "STT_OPENAI_MODEL", "gpt-4o-transcribe")

    provider = factory.get_stt_provider()

    assert isinstance(provider, OpenAITranscriptionProvider)
    assert provider.model == "gpt-4o-transcribe"


def test_factory_selects_local_whisper_provider(monkeypatch):
    monkeypatch.setattr(config, "STT_PROVIDER", "local_whisper")
    monkeypatch.setattr(config, "STT_LOCAL_MODEL_SIZE", "base")
    monkeypatch.setattr(config, "STT_LOCAL_DEVICE", "cpu")

    # faster-whisper isn't installed in this environment, so constructing
    # the real provider would raise - confirm the factory routes to it
    # (and surfaces that same clear error) rather than silently falling
    # back to whisperx_http.
    with pytest.raises(RuntimeError, match="requirements-local-stt.txt"):
        factory.get_stt_provider()


def test_factory_caches_singleton(monkeypatch):
    monkeypatch.setattr(config, "STT_PROVIDER", "whisperx_http")

    first = factory.get_stt_provider()
    second = factory.get_stt_provider()

    assert first is second
