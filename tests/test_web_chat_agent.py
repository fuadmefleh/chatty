"""Tests for WebChatAgent's streaming tool-calling loop against the
LLMProvider abstraction (src/core/llm/)."""
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agents.web_chat_agent import MAX_TOOL_ITERATIONS, WebChatAgent
from src.core.llm import StreamChunk, ToolCallDelta


class FakeStreamingProvider:
    """Replays a fixed sequence of StreamChunk lists, one list per call to
    stream_with_tools (i.e. one list per tool-calling loop iteration)."""
    model = "fake-model"

    def __init__(self, turns):
        self._turns = list(turns)
        self.calls = []

    @property
    def supports_vision(self) -> bool:
        return False

    async def complete_vision(self, prompt, image_b64, *, max_tokens=800) -> str:
        return ""

    async def complete(self, *args, **kwargs):
        raise NotImplementedError

    async def complete_with_tools(self, *args, **kwargs):
        raise NotImplementedError

    async def stream_with_tools(self, messages, tools, *, tool_choice="auto", temperature=None):
        self.calls.append({"messages": [dict(m) for m in messages], "tools": tools})
        for chunk in self._turns.pop(0):
            yield chunk


def _make_agent(provider):
    skills_manager = MagicMock()
    skills_manager.skills = {}
    skills_manager.get_tool.return_value = None

    memory_manager = MagicMock()
    memory_manager.get_long_term_memory = AsyncMock(return_value="")
    memory_manager.get_recent_memory = AsyncMock(return_value="")
    memory_manager.add_interaction = AsyncMock()

    agent = WebChatAgent(skills_manager=skills_manager, memory_manager=memory_manager)
    agent.llm = provider
    return agent, memory_manager


@pytest.mark.asyncio
async def test_text_only_streaming_response():
    provider = FakeStreamingProvider([
        [
            StreamChunk(text_delta="Hello"),
            StreamChunk(text_delta=", world!", is_final=True, stop_reason="stop"),
        ],
    ])
    agent, memory_manager = _make_agent(provider)

    chunks = [c async for c in agent.stream("hi")]

    assert "".join(chunks) == "Hello, world!"
    assert len(provider.calls) == 1
    memory_manager.add_interaction.assert_awaited_once_with("hi", "Hello, world!")


@pytest.mark.asyncio
async def test_attachment_context_merged_into_user_turn_not_persisted():
    """attachment_context should reach the LLM grafted onto the current user
    turn's own content (not a separate system message - see _build_messages'
    docstring for why: a separate system note reliably got overridden by the
    local model's trained "I can't see images" refusal in live testing), and
    only for this completion - not stored in self._history, so it isn't
    repeated on later turns and doesn't pollute the persisted/displayed text."""
    provider = FakeStreamingProvider([
        [StreamChunk(text_delta="Nice photo!", is_final=True, stop_reason="stop")],
        [StreamChunk(text_delta="Sure, tell me more.", is_final=True, stop_reason="stop")],
    ])
    agent, _ = _make_agent(provider)

    chunks = [c async for c in agent.stream("check this out", attachment_context="It's a photo of a cat.")]
    assert "".join(chunks) == "Nice photo!"

    first_call_messages = provider.calls[0]["messages"]
    last_message = first_call_messages[-1]
    assert last_message["role"] == "user"
    assert "photo of a cat" in last_message["content"]
    assert "check this out" in last_message["content"]
    # The user-visible/persisted history entry stays the plain caption.
    assert {"role": "user", "content": "check this out"} in agent._history

    # A follow-up turn with no attachment must not resurface the old context.
    [c async for c in agent.stream("okay")]
    second_call_messages = provider.calls[1]["messages"]
    assert not any("photo of a cat" in m.get("content", "") for m in second_call_messages)


@pytest.mark.asyncio
async def test_tool_call_deltas_get_executed_and_looped():
    provider = FakeStreamingProvider([
        [
            StreamChunk(tool_call_deltas=[
                ToolCallDelta(index=0, id="call_1", name="get_weather", arguments_delta='{"city":'),
            ]),
            StreamChunk(tool_call_deltas=[
                ToolCallDelta(index=0, arguments_delta='"NYC"}'),
            ], is_final=True, stop_reason="tool_calls"),
        ],
        [
            StreamChunk(text_delta="It's sunny in NYC.", is_final=True, stop_reason="stop"),
        ],
    ])
    agent, _ = _make_agent(provider)

    tool = MagicMock()
    tool.execute = AsyncMock(return_value="sunny")
    agent.skills_manager.get_tool.return_value = tool

    chunks = [c async for c in agent.stream("weather?")]

    assert "".join(chunks) == "It's sunny in NYC."
    assert len(provider.calls) == 2
    tool.execute.assert_awaited_once_with(city="NYC")

    # Second call's messages must include the assistant tool_calls message
    # and the tool result, in OpenAI's wire shape.
    second_call_messages = provider.calls[1]["messages"]
    assert any(m.get("tool_calls") for m in second_call_messages if m["role"] == "assistant")
    tool_messages = [m for m in second_call_messages if m["role"] == "tool"]
    assert tool_messages[0]["tool_call_id"] == "call_1"
    assert tool_messages[0]["content"] == "sunny"


@pytest.mark.asyncio
async def test_max_tool_iterations_exhausted():
    # Every turn requests another tool call - the loop should give up after
    # MAX_TOOL_ITERATIONS and yield a clear message instead of looping forever.
    turn = [
        StreamChunk(tool_call_deltas=[
            ToolCallDelta(index=0, id="call_x", name="noop", arguments_delta="{}"),
        ], is_final=True, stop_reason="tool_calls"),
    ]
    provider = FakeStreamingProvider([turn] * MAX_TOOL_ITERATIONS)
    agent, _ = _make_agent(provider)

    tool = MagicMock()
    tool.execute = AsyncMock(return_value="ok")
    agent.skills_manager.get_tool.return_value = tool

    chunks = [c async for c in agent.stream("loop forever")]

    assert "[Max tool iterations reached]" in "".join(chunks)
    assert len(provider.calls) == MAX_TOOL_ITERATIONS
