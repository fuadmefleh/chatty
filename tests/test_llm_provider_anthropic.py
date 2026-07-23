"""Tests for AnthropicProvider's translation between atlas's OpenAI-shaped
messages/tools and Anthropic's Messages API. This is the highest-risk piece
of the provider abstraction (system-prompt extraction, tool_result batching,
prompt-engineered JSON mode, streaming event parsing) so it gets the most
direct coverage."""
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from anthropic import APIConnectionError

from src.core.llm import LLMRetryableError
from src.core.llm.anthropic_provider import (
    _split_system,
    _strip_json_fences,
    _to_anthropic_messages,
    _tools_to_anthropic,
    AnthropicProvider,
)


def _connection_error() -> APIConnectionError:
    return APIConnectionError(request=httpx.Request("POST", "http://test.local"))


def _text_block(text: str):
    return SimpleNamespace(type="text", text=text)


def _tool_use_block(id_, name, input_):
    return SimpleNamespace(type="tool_use", id=id_, name=name, input=input_)


def _message(content, stop_reason="end_turn"):
    return SimpleNamespace(content=content, stop_reason=stop_reason)


class TestMessageTranslation:
    def test_split_system_pulls_out_and_joins_system_messages(self):
        messages = [
            {"role": "system", "content": "You are Chatty."},
            {"role": "system", "content": "Long-term memory: likes teal."},
            {"role": "user", "content": "hi"},
        ]
        system, rest = _split_system(messages)
        assert system == "You are Chatty.\n\nLong-term memory: likes teal."
        assert rest == [{"role": "user", "content": "hi"}]

    def test_split_system_none_when_absent(self):
        system, rest = _split_system([{"role": "user", "content": "hi"}])
        assert system is None
        assert len(rest) == 1

    def test_trailing_tool_messages_batch_into_one_user_message(self):
        messages = [
            {"role": "user", "content": "weather in two cities?"},
            {
                "role": "assistant", "content": None,
                "tool_calls": [
                    {"id": "call_1", "type": "function", "function": {"name": "get_weather", "arguments": '{"city":"NYC"}'}},
                    {"id": "call_2", "type": "function", "function": {"name": "get_weather", "arguments": '{"city":"LA"}'}},
                ],
            },
            {"role": "tool", "tool_call_id": "call_1", "name": "get_weather", "content": "sunny"},
            {"role": "tool", "tool_call_id": "call_2", "name": "get_weather", "content": "cloudy"},
        ]
        out = _to_anthropic_messages(messages)

        assert out[0] == {"role": "user", "content": "weather in two cities?"}
        assert out[1]["role"] == "assistant"
        tool_use_blocks = [b for b in out[1]["content"] if b["type"] == "tool_use"]
        assert len(tool_use_blocks) == 2
        assert tool_use_blocks[0]["input"] == {"city": "NYC"}

        # Both tool results must land in a single subsequent user message.
        assert out[2]["role"] == "user"
        assert len(out[2]["content"]) == 2
        assert out[2]["content"][0] == {"type": "tool_result", "tool_use_id": "call_1", "content": "sunny"}
        assert out[2]["content"][1] == {"type": "tool_result", "tool_use_id": "call_2", "content": "cloudy"}

    def test_tools_translated_to_input_schema(self):
        openai_tools = [{
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get the weather",
                "parameters": {"type": "object", "properties": {"city": {"type": "string"}}},
            },
        }]
        anthropic_tools = _tools_to_anthropic(openai_tools)
        assert anthropic_tools == [{
            "name": "get_weather",
            "description": "Get the weather",
            "input_schema": {"type": "object", "properties": {"city": {"type": "string"}}},
        }]

    def test_tools_to_anthropic_none_when_empty(self):
        assert _tools_to_anthropic(None) is None
        assert _tools_to_anthropic([]) is None

    def test_strip_json_fences_handles_various_wrappings(self):
        assert _strip_json_fences('```json\n{"a": 1}\n```') == '{"a": 1}'
        assert _strip_json_fences('```\n{"a": 1}\n```') == '{"a": 1}'
        assert _strip_json_fences('{"a": 1}') == '{"a": 1}'


@pytest.mark.asyncio
class TestAnthropicProviderCalls:
    async def test_complete_extracts_text(self):
        provider = AnthropicProvider(api_key="sk-ant-test", model="claude-sonnet-4-5")
        provider.client.messages.create = AsyncMock(
            return_value=_message([_text_block("hi there")])
        )

        result = await provider.complete([{"role": "user", "content": "hello"}])

        assert result.content == "hi there"
        assert result.tool_calls == []

    async def test_complete_with_tools_extracts_tool_use_as_json_string_args(self):
        provider = AnthropicProvider(api_key="sk-ant-test", model="claude-sonnet-4-5")
        provider.client.messages.create = AsyncMock(
            return_value=_message([_tool_use_block("toolu_1", "get_weather", {"city": "NYC"})], stop_reason="tool_use")
        )

        result = await provider.complete_with_tools(
            [{"role": "user", "content": "weather?"}],
            [{"type": "function", "function": {"name": "get_weather", "parameters": {}}}],
        )

        assert result.stop_reason == "tool_calls"
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].id == "toolu_1"
        assert result.tool_calls[0].name == "get_weather"
        # arguments must stay a JSON string, same contract as OpenAI's ToolCall
        assert result.tool_calls[0].arguments == '{"city": "NYC"}'

        # round-trips into an OpenAI-shaped assistant message unmodified
        openai_message = result.to_openai_message()
        assert openai_message["tool_calls"][0]["function"]["name"] == "get_weather"

    async def test_json_mode_appends_instruction_and_strips_code_fences(self):
        provider = AnthropicProvider(api_key="sk-ant-test", model="claude-sonnet-4-5")
        provider.client.messages.create = AsyncMock(
            return_value=_message([_text_block('```json\n{"query_type": "question", "sub_tasks": []}\n```')])
        )

        result = await provider.complete(
            [{"role": "user", "content": "decompose this"}], response_format="json",
        )

        _, kwargs = provider.client.messages.create.call_args
        assert "tools" not in kwargs
        assert kwargs["messages"][-1]["content"].startswith("decompose this")
        assert "Respond with ONLY the raw JSON object" in kwargs["messages"][-1]["content"]
        assert result.content == '{"query_type": "question", "sub_tasks": []}'
        assert json.loads(result.content) == {"query_type": "question", "sub_tasks": []}

    async def test_transient_error_becomes_llm_retryable_error(self):
        provider = AnthropicProvider(api_key="sk-ant-test", model="claude-sonnet-4-5")
        provider.client.messages.create = AsyncMock(side_effect=_connection_error())

        with pytest.raises(LLMRetryableError):
            await provider.complete([{"role": "user", "content": "hello"}])

    async def test_supports_vision_and_temperature(self):
        provider = AnthropicProvider(api_key="sk-ant-test", model="claude-sonnet-4-5")
        assert provider.supports_vision is True
        assert provider.supports_temperature is True

    async def test_complete_vision_sends_image_block(self):
        provider = AnthropicProvider(api_key="sk-ant-test", model="claude-sonnet-4-5")
        provider.client.messages.create = AsyncMock(
            return_value=_message([_text_block("a photo of a cat")])
        )

        result = await provider.complete_vision("what is this?", image_b64="ZmFrZQ==")

        assert result == "a photo of a cat"
        _, kwargs = provider.client.messages.create.call_args
        content = kwargs["messages"][0]["content"]
        assert content[0]["type"] == "image"
        assert content[0]["source"]["data"] == "ZmFrZQ=="


@pytest.mark.asyncio
class TestAnthropicStreaming:
    async def test_stream_with_tools_yields_text_and_tool_call_deltas(self):
        provider = AnthropicProvider(api_key="sk-ant-test", model="claude-sonnet-4-5")

        events = [
            SimpleNamespace(type="content_block_start", index=0, content_block=SimpleNamespace(type="text")),
            SimpleNamespace(type="content_block_delta", index=0, delta=SimpleNamespace(type="text_delta", text="Hel")),
            SimpleNamespace(type="content_block_delta", index=0, delta=SimpleNamespace(type="text_delta", text="lo")),
            SimpleNamespace(
                type="content_block_start", index=1,
                content_block=SimpleNamespace(type="tool_use", id="toolu_3", name="get_weather"),
            ),
            SimpleNamespace(
                type="content_block_delta", index=1,
                delta=SimpleNamespace(type="input_json_delta", partial_json='{"city":'),
            ),
            SimpleNamespace(
                type="content_block_delta", index=1,
                delta=SimpleNamespace(type="input_json_delta", partial_json='"NYC"}'),
            ),
            SimpleNamespace(type="message_delta", delta=SimpleNamespace(stop_reason="tool_use")),
        ]

        class FakeStreamCtx:
            async def __aenter__(self_):
                return self_

            async def __aexit__(self_, *exc):
                return False

            def __aiter__(self_):
                async def gen():
                    for e in events:
                        yield e
                return gen()

        provider.client.messages.stream = MagicMock(return_value=FakeStreamCtx())

        chunks = [c async for c in provider.stream_with_tools(
            [{"role": "user", "content": "weather?"}],
            [{"type": "function", "function": {"name": "get_weather", "parameters": {}}}],
        )]

        text = "".join(c.text_delta for c in chunks)
        assert text == "Hello"

        tool_deltas = [d for c in chunks for d in c.tool_call_deltas]
        assert tool_deltas[0].id == "toolu_3"
        assert tool_deltas[0].name == "get_weather"
        args = "".join(d.arguments_delta for d in tool_deltas)
        assert args == '{"city":"NYC"}'

        assert chunks[-1].is_final is True
        assert chunks[-1].stop_reason == "tool_use"
