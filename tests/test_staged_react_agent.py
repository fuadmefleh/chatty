"""Tests for StagedReACTAgent's loop behavior: conversation history plumbing,
transient-error retries, and backgrounded REFLECT/MEMORIZE stages."""
import asyncio
import json
import httpx
import pytest
from unittest.mock import AsyncMock, MagicMock

from openai import APIConnectionError

from src.agents.staged_react_agent import (
    StagedReACTAgent,
    ReACTState,
    MAX_LLM_RETRIES,
)


@pytest.fixture
def agent():
    memory_manager = MagicMock()
    memory_manager.user_id = "test_user_agentic_loop"
    memory_manager.get_recent_memory = AsyncMock(return_value="")
    memory_manager.get_long_term_memory = AsyncMock(return_value="")

    skills_manager = MagicMock()
    skills_manager.get_all_tools.return_value = {}
    skills_manager.get_openai_tools.return_value = []
    skills_manager.get_all_skills.return_value = []

    return StagedReACTAgent(memory_manager, skills_manager)


def _connection_error() -> APIConnectionError:
    return APIConnectionError(request=httpx.Request("POST", "http://test.local"))


class TestConversationHistoryInPrompts:
    @pytest.mark.asyncio
    async def test_decompose_prompt_includes_history(self, agent):
        captured = {}

        async def fake_call_llm(prompt, response_format="text"):
            captured["prompt"] = prompt
            return json.dumps({"query_type": "question", "sub_tasks": []})

        agent._call_llm = fake_call_llm

        history = [
            {"role": "user", "content": "My favorite color is teal."},
            {"role": "assistant", "content": "Got it, teal it is!"},
        ]
        state = ReACTState(user_query="What did I say my favorite color was?")
        await agent._stage_decompose(state, history)

        assert "teal" in captured["prompt"]

    @pytest.mark.asyncio
    async def test_synthesize_prompt_includes_history(self, agent):
        captured = {}

        async def fake_call_llm(prompt, response_format="text"):
            captured["prompt"] = prompt
            return "final answer"

        agent._call_llm = fake_call_llm

        history = [
            {"role": "user", "content": "My favorite color is teal."},
            {"role": "assistant", "content": "Got it, teal it is!"},
        ]
        state = ReACTState(user_query="What's my favorite color?")
        await agent._stage_synthesize(state, history)

        assert "teal" in captured["prompt"]

    @pytest.mark.asyncio
    async def test_empty_history_omits_history_section(self, agent):
        captured = {}

        async def fake_call_llm(prompt, response_format="text"):
            captured["prompt"] = prompt
            return json.dumps({"query_type": "greeting", "sub_tasks": []})

        agent._call_llm = fake_call_llm

        state = ReACTState(user_query="hi")
        await agent._stage_decompose(state, [])

        assert "Recent Conversation" not in captured["prompt"]


class TestTransientErrorRetries:
    @pytest.mark.asyncio
    async def test_create_completion_retries_then_succeeds(self, agent, monkeypatch):
        monkeypatch.setattr("src.agents.staged_react_agent.asyncio.sleep", AsyncMock())

        success = MagicMock()
        success.choices = [MagicMock(message=MagicMock(content="ok"))]

        agent.client.chat.completions.create = AsyncMock(
            side_effect=[_connection_error(), success]
        )

        response = await agent._create_completion(model="x", messages=[])

        assert response is success
        assert agent.client.chat.completions.create.call_count == 2

    @pytest.mark.asyncio
    async def test_create_completion_raises_after_max_retries(self, agent, monkeypatch):
        monkeypatch.setattr("src.agents.staged_react_agent.asyncio.sleep", AsyncMock())

        errors = [_connection_error() for _ in range(MAX_LLM_RETRIES + 1)]
        agent.client.chat.completions.create = AsyncMock(side_effect=errors)

        with pytest.raises(APIConnectionError):
            await agent._create_completion(model="x", messages=[])

        assert agent.client.chat.completions.create.call_count == MAX_LLM_RETRIES + 1

    @pytest.mark.asyncio
    async def test_call_llm_falls_back_on_persistent_failure(self, agent, monkeypatch):
        monkeypatch.setattr("src.agents.staged_react_agent.asyncio.sleep", AsyncMock())

        errors = [_connection_error() for _ in range(MAX_LLM_RETRIES + 1)]
        agent.client.chat.completions.create = AsyncMock(side_effect=errors)

        result = await agent._call_llm("prompt")

        assert result == ""


class TestBackgroundedReflectAndMemorize:
    @pytest.mark.asyncio
    async def test_think_returns_before_reflect_and_memorize_complete(self, agent):
        async def fake_decompose(state, history):
            return state

        async def fake_memory(state):
            return state

        async def fake_plan(state):
            state.tools_to_use = []
            return state

        async def fake_execute(state):
            return state

        async def fake_synthesize(state, history):
            state.synthesized_answer = "final answer"
            return state

        reflect_started = asyncio.Event()
        memorize_done = asyncio.Event()

        async def fake_reflect(state):
            reflect_started.set()
            return state

        async def fake_memorize(state):
            memorize_done.set()
            return state

        agent._stage_decompose = fake_decompose
        agent._stage_memory = fake_memory
        agent._stage_plan = fake_plan
        agent._stage_execute = fake_execute
        agent._stage_synthesize = fake_synthesize
        agent._stage_reflect = fake_reflect
        agent._stage_memorize = fake_memorize

        answer = await agent.think("hello", [])

        assert answer == "final answer"
        # REFLECT/MEMORIZE are scheduled but haven't run yet at this point.
        assert not reflect_started.is_set()
        assert not memorize_done.is_set()
        assert len(agent._background_tasks) == 1

        # Let the background task finish and confirm it actually runs.
        task = next(iter(agent._background_tasks))
        await task

        assert reflect_started.is_set()
        assert memorize_done.is_set()

    @pytest.mark.asyncio
    async def test_background_error_does_not_propagate(self, agent):
        async def fake_decompose(state, history):
            return state

        async def fake_memory(state):
            return state

        async def fake_plan(state):
            state.tools_to_use = []
            return state

        async def fake_execute(state):
            return state

        async def fake_synthesize(state, history):
            state.synthesized_answer = "final answer"
            return state

        async def failing_reflect(state):
            raise RuntimeError("boom")

        agent._stage_decompose = fake_decompose
        agent._stage_memory = fake_memory
        agent._stage_plan = fake_plan
        agent._stage_execute = fake_execute
        agent._stage_synthesize = fake_synthesize
        agent._stage_reflect = failing_reflect

        answer = await agent.think("hello", [])
        assert answer == "final answer"

        task = next(iter(agent._background_tasks))
        await task  # should not raise — errors are caught inside _finish_reasoning
