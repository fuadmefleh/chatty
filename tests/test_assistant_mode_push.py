"""Tests for _push_assistant_response: routing a wake-word-triggered query to
the open /api/chatty/chat WebSocket for a device, keyed by X-Device-Id."""
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import chatty_web_server as server


class FakeWebChatAgent:
    """Stands in for src.agents.web_chat_agent.WebChatAgent: records the query
    it was streamed and yields a fixed sequence of chunks."""

    last_instance = None

    def __init__(self, skills_manager, memory_manager):
        self.skills_manager = skills_manager
        self.memory_manager = memory_manager
        self.query = None
        FakeWebChatAgent.last_instance = self

    async def stream(self, query):
        self.query = query
        for chunk in ["It's ", "sunny ", "today."]:
            yield chunk


@pytest.fixture(autouse=True)
def fake_agent(monkeypatch):
    import src.agents.web_chat_agent as web_chat_agent_module
    monkeypatch.setattr(web_chat_agent_module, "WebChatAgent", FakeWebChatAgent)
    yield
    FakeWebChatAgent.last_instance = None


@pytest.fixture(autouse=True)
def clear_connections():
    server._active_chat_connections.clear()
    yield
    server._active_chat_connections.clear()


@pytest.mark.asyncio
async def test_no_open_connection_drops_silently():
    # No connection registered for this device - should not raise.
    await server._push_assistant_response("device-none", "what's the weather")
    assert FakeWebChatAgent.last_instance is None


@pytest.mark.asyncio
async def test_open_connection_streams_chunks_then_done():
    connection = server._ChatConnection(websocket=AsyncMock())
    server._active_chat_connections["device-123"] = connection

    await server._push_assistant_response("device-123", "what's the weather")

    assert FakeWebChatAgent.last_instance.query == "what's the weather"
    calls = [json.loads(c.args[0]) for c in connection.websocket.send_text.await_args_list]
    assert calls == [
        {"type": "chunk", "content": "It's "},
        {"type": "chunk", "content": "sunny "},
        {"type": "chunk", "content": "today."},
        {"type": "done"},
    ]


@pytest.mark.asyncio
async def test_send_failure_is_logged_not_raised():
    connection = server._ChatConnection(websocket=AsyncMock())
    connection.websocket.send_text = AsyncMock(side_effect=RuntimeError("socket closed"))
    server._active_chat_connections["device-123"] = connection

    # Should not raise even though the underlying send fails.
    await server._push_assistant_response("device-123", "what's the weather")
