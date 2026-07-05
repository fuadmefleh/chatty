"""Tests for OpenAIProvider: translation to/from LLMResponse/StreamChunk and
retry-error mapping. Covers both the "openai" and "local" CHAT_PROVIDER
configurations, since local is just this same provider pointed at a
different base_url."""
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from openai import APIConnectionError

from src.core.llm import LLMRetryableError, with_retries
from src.core.llm.openai_provider import OpenAIProvider


def _connection_error() -> APIConnectionError:
    return APIConnectionError(request=httpx.Request("POST", "http://test.local"))


def _make_provider(**kwargs) -> OpenAIProvider:
    defaults = dict(api_key="sk-test", base_url=None, model="gpt-4o")
    defaults.update(kwargs)
    return OpenAIProvider(**defaults)


@pytest.mark.asyncio
async def test_complete_returns_normalized_response():
    provider = _make_provider()
    fake_response = MagicMock()
    fake_response.usage = None
    fake_response.choices = [MagicMock(message=MagicMock(content="hi there"), finish_reason="stop")]
    provider.client.chat.completions.create = AsyncMock(return_value=fake_response)

    result = await provider.complete([{"role": "user", "content": "hello"}])

    assert result.content == "hi there"
    assert result.tool_calls == []
    assert result.stop_reason == "stop"


@pytest.mark.asyncio
async def test_complete_json_mode_sets_response_format():
    provider = _make_provider()
    fake_response = MagicMock()
    fake_response.usage = None
    fake_response.choices = [MagicMock(message=MagicMock(content="{}"), finish_reason="stop")]
    provider.client.chat.completions.create = AsyncMock(return_value=fake_response)

    await provider.complete([{"role": "user", "content": "hello"}], response_format="json")

    _, kwargs = provider.client.chat.completions.create.call_args
    assert kwargs["response_format"] == {"type": "json_object"}


@pytest.mark.asyncio
async def test_complete_with_tools_normalizes_tool_calls():
    provider = _make_provider()
    fake_function = MagicMock(arguments='{"city":"NYC"}')
    fake_function.name = "get_weather"  # MagicMock(name=...) sets the mock's repr, not an attribute
    fake_tool_call = MagicMock(id="call_1", function=fake_function)
    fake_response = MagicMock()
    fake_response.usage = None
    fake_response.choices = [MagicMock(
        message=MagicMock(content=None, tool_calls=[fake_tool_call]),
        finish_reason="tool_calls",
    )]
    provider.client.chat.completions.create = AsyncMock(return_value=fake_response)

    result = await provider.complete_with_tools(
        [{"role": "user", "content": "weather?"}],
        [{"type": "function", "function": {"name": "get_weather", "parameters": {}}}],
    )

    assert result.stop_reason == "tool_calls"
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].id == "call_1"
    assert result.tool_calls[0].name == "get_weather"
    assert result.tool_calls[0].arguments == '{"city":"NYC"}'

    # round-trips back into an OpenAI-shaped assistant message unmodified
    message = result.to_openai_message()
    assert message["tool_calls"][0]["function"]["name"] == "get_weather"


@pytest.mark.asyncio
async def test_transient_openai_errors_become_llm_retryable_error():
    provider = _make_provider()
    provider.client.chat.completions.create = AsyncMock(side_effect=_connection_error())

    with pytest.raises(LLMRetryableError):
        await provider.complete([{"role": "user", "content": "hello"}])


@pytest.mark.asyncio
async def test_with_retries_recovers_from_transient_openai_error(monkeypatch):
    monkeypatch.setattr("src.core.llm.retry.asyncio.sleep", AsyncMock())
    provider = _make_provider()
    fake_response = MagicMock()
    fake_response.usage = None
    fake_response.choices = [MagicMock(message=MagicMock(content="ok"), finish_reason="stop")]
    provider.client.chat.completions.create = AsyncMock(
        side_effect=[_connection_error(), fake_response]
    )

    result = await with_retries(
        lambda: provider.complete([{"role": "user", "content": "hello"}])
    )

    assert result.content == "ok"
    assert provider.client.chat.completions.create.call_count == 2


def test_temperature_support_sniffing():
    assert _make_provider(model="gpt-4o").supports_temperature is True
    assert _make_provider(model="o1-mini").supports_temperature is False
    assert _make_provider(model="gpt-5-nano").supports_temperature is False


def test_local_provider_defaults_no_vision():
    local = OpenAIProvider(api_key="not-needed", base_url="http://localhost:8080/v1", model="qwen3.6-27b", supports_vision=False)
    assert local.supports_vision is False

    openai_provider = _make_provider(supports_vision=True)
    assert openai_provider.supports_vision is True
