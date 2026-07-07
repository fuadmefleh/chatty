"""Tests for StagedReACTAgent's loop behavior: conversation history plumbing,
transient-error retries, and backgrounded REFLECT/MEMORIZE stages."""
import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from src.agents.staged_react_agent import StagedReACTAgent, ReACTState
from src.core import config
from src.core.llm import LLMResponse, LLMRetryableError, MAX_LLM_RETRIES


class FakeLLMProvider:
    """Minimal LLMProvider stand-in for tests that don't care about the
    real OpenAI/Anthropic wire format, only that StagedReACTAgent calls
    through self.llm correctly."""
    model = "fake-model"

    def __init__(self):
        self.complete = AsyncMock(return_value=LLMResponse(content=""))
        self.complete_with_tools = AsyncMock(return_value=LLMResponse(content="", tool_calls=[]))

    @property
    def supports_vision(self) -> bool:
        return False

    async def complete_vision(self, prompt, image_b64, *, max_tokens=800) -> str:
        return ""

    def stream_with_tools(self, *args, **kwargs):
        raise NotImplementedError


@pytest.fixture
def agent(tmp_path, monkeypatch):
    # StagedReACTAgent constructs a real MemoryTools(user_id) internally, which
    # resolves paths under config.MEMORY_DIR at construction time - isolate it
    # to a tmp dir so tests that exercise memory tools (e.g. save_important_fact)
    # don't write into the real project's memory/ folder.
    monkeypatch.setattr(config, "MEMORY_DIR", tmp_path)

    # save_important_fact -> MemoryManager.add_long_term_memory tries to embed
    # the fact for semantic search; stub it out so schema-callability tests
    # never make a live OpenAI API call.
    async def _fake_get_embedding(text: str):
        return [0.1, 0.2, 0.3]

    monkeypatch.setattr("src.core.embeddings.get_embedding", _fake_get_embedding)

    memory_manager = MagicMock()
    memory_manager.user_id = "test_user_agentic_loop"
    memory_manager.get_recent_memory = AsyncMock(return_value="")
    memory_manager.get_long_term_memory = AsyncMock(return_value="")

    skills_manager = MagicMock()
    skills_manager.get_all_tools.return_value = {}
    skills_manager.get_openai_tools.return_value = []
    skills_manager.get_all_skills.return_value = []

    return StagedReACTAgent(memory_manager, skills_manager, llm_provider=FakeLLMProvider())


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
    async def test_call_llm_retries_then_succeeds(self, agent, monkeypatch):
        monkeypatch.setattr("src.core.llm.retry.asyncio.sleep", AsyncMock())

        success = LLMResponse(content="ok")
        agent.llm.complete = AsyncMock(side_effect=[LLMRetryableError("boom"), success])

        result = await agent._call_llm("prompt")

        assert result == "ok"
        assert agent.llm.complete.call_count == 2

    @pytest.mark.asyncio
    async def test_call_llm_falls_back_on_persistent_failure(self, agent, monkeypatch):
        monkeypatch.setattr("src.core.llm.retry.asyncio.sleep", AsyncMock())

        errors = [LLMRetryableError("boom") for _ in range(MAX_LLM_RETRIES + 1)]
        agent.llm.complete = AsyncMock(side_effect=errors)

        result = await agent._call_llm("prompt")

        assert result == ""
        assert agent.llm.complete.call_count == MAX_LLM_RETRIES + 1


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


class TestMemoryToolSchema:
    """The OpenAI-advertised parameter names for the always-on memory tools
    (_get_memory_tools_definitions) must match what _execute_memory_tool
    actually passes through to MemoryTools - a past mismatch (advertised
    "pattern" vs. the real "search_term") meant the LLM's schema-conformant
    call would always throw, silently swallowed by the dispatcher's
    try/except into an "Error executing ..." string."""

    @pytest.mark.asyncio
    async def test_search_memory_grep_advertised_params_are_callable(self, agent):
        tool_defs = agent._get_memory_tools_definitions()
        search_def = next(t for t in tool_defs if t["function"]["name"] == "search_memory_grep")
        required_params = search_def["function"]["parameters"]["required"]

        arguments = {param: "test" for param in required_params}
        result = await agent._execute_memory_tool("search_memory_grep", arguments)

        assert not result.startswith("Error executing"), result

    @pytest.mark.asyncio
    async def test_save_important_fact_advertised_params_are_callable(self, agent):
        tool_defs = agent._get_memory_tools_definitions()
        save_def = next(t for t in tool_defs if t["function"]["name"] == "save_important_fact")
        required_params = save_def["function"]["parameters"]["required"]

        arguments = {param: "test" for param in required_params}
        result = await agent._execute_memory_tool("save_important_fact", arguments)

        assert not result.startswith("Error executing"), result

    @pytest.mark.asyncio
    @pytest.mark.parametrize("tool_name", [
        "list_memory_files",
        "read_memory_file",
        "search_by_date_range",
        "search_pattern",
        "search_recent_mentions",
    ])
    async def test_newly_wired_tools_advertised_params_are_callable(self, agent, tool_name):
        tool_defs = agent._get_memory_tools_definitions()
        tool_def = next(t for t in tool_defs if t["function"]["name"] == tool_name)
        required_params = tool_def["function"]["parameters"]["required"]

        arguments = {
            param: "2026-01-01" if "date" in param else "test"
            for param in required_params
        }
        result = await agent._execute_memory_tool(tool_name, arguments)

        assert not result.startswith("Error executing"), result

    @pytest.mark.asyncio
    @pytest.mark.parametrize("tool_name,required_arg_name", [
        ("search_by_date_range", "start_date"),
        ("search_pattern", "regex_pattern"),
        ("search_recent_mentions", "topic"),
    ])
    async def test_new_memory_tools_are_routed_by_execute_tool(self, agent, tool_name, required_arg_name):
        """_execute_tool's dispatch gate used to be a startswith() prefix
        tuple that didn't match these 3 tool names at all, so advertising
        them without fixing the gate would silently misroute every call to
        skills_manager.execute_tool() (-> 'Unknown tool: ...') instead of
        ever reaching MemoryTools. This exercises _execute_tool directly
        (not _execute_memory_tool), since that's the real dispatch entry
        point the LLM's tool calls actually go through."""
        tool_defs = agent._get_memory_tools_definitions()
        tool_def = next(t for t in tool_defs if t["function"]["name"] == tool_name)
        required_params = tool_def["function"]["parameters"]["required"]

        arguments = {
            param: "2026-01-01" if "date" in param else "test"
            for param in required_params
        }
        result = await agent._execute_tool(tool_name, arguments)

        assert not result.startswith("Unknown tool"), result

    @pytest.mark.asyncio
    async def test_forget_fact_advertised_params_are_callable(self, agent):
        tool_defs = agent._get_memory_tools_definitions()
        tool_def = next(t for t in tool_defs if t["function"]["name"] == "forget_fact")
        required_params = tool_def["function"]["parameters"]["required"]

        arguments = {param: "test" for param in required_params}
        result = await agent._execute_tool("forget_fact", arguments)

        assert not result.startswith("Error executing"), result
        assert not result.startswith("Unknown tool"), result

    @pytest.mark.asyncio
    async def test_delete_fact_by_id_advertised_params_are_callable(self, agent):
        tool_defs = agent._get_memory_tools_definitions()
        tool_def = next(t for t in tool_defs if t["function"]["name"] == "delete_fact_by_id")
        required_params = tool_def["function"]["parameters"]["required"]

        arguments = {param: "test" for param in required_params}
        result = await agent._execute_tool("delete_fact_by_id", arguments)

        assert not result.startswith("Error executing"), result
        assert not result.startswith("Unknown tool"), result

    @pytest.mark.asyncio
    async def test_semantic_search_memory_advertised_params_are_callable(self, agent):
        tool_defs = agent._get_memory_tools_definitions()
        tool_def = next(t for t in tool_defs if t["function"]["name"] == "semantic_search_memory")
        required_params = tool_def["function"]["parameters"]["required"]

        arguments = {param: "test" for param in required_params}
        result = await agent._execute_tool("semantic_search_memory", arguments)

        assert not result.startswith("Error executing"), result
        assert not result.startswith("Unknown tool"), result
