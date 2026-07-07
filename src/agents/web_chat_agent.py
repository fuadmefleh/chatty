"""Web Chat Agent - a simplified agent for the Chatty web dashboard.

Unlike StagedReACTAgent (which has 7 stages and Telegram-specific code),
this agent uses a direct function-calling loop:
1. Send user message + conversation history + available tools
2. If the LLM requests tool calls, execute them and feed results back
3. Yield text chunks as they arrive (streaming)
4. Save interaction to memory when done

Usage:
    agent = WebChatAgent(skills_manager=sm, memory_manager=mm)
    async for chunk in agent.stream("Hello!"):
        print(chunk, end="", flush=True)
"""
import json
from typing import AsyncGenerator, List, Dict, Any, Optional
from src.core import config
from src.core.llm import get_llm_provider
from src.core.memory import MemoryManager
from src.core.skills_manager import SkillsManager

MAX_TOOL_ITERATIONS = 8
MAX_HISTORY = 20  # messages kept in sliding window
SYSTEM_PROMPT = """You are Chatty, a helpful AI assistant accessible via a web dashboard. \
You have access to skills and tools to help the user with notes, orders, budget, reminders, \
web search, and more. Be concise, friendly, and helpful. \
When using tools, act on the results and provide a clear, direct answer."""


class WebChatAgent:
    """Direct function-calling agent with streaming, for the web UI."""

    def __init__(self, skills_manager: SkillsManager, memory_manager: MemoryManager):
        self.llm = get_llm_provider()
        self.skills_manager = skills_manager
        self.memory_manager = memory_manager
        self._history: List[Dict[str, Any]] = []

    def _get_tools(self) -> List[Dict]:
        """Return OpenAI tool specs for all loaded skills."""
        if not self.skills_manager:
            return []
        tools = []
        for skill in self.skills_manager.skills.values():
            tools.extend(skill.get_openai_tools())
        return tools

    async def _execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Execute a skill tool and return its result as a string."""
        if not self.skills_manager:
            return json.dumps({"error": "Skills manager not available"})

        tool = self.skills_manager.get_tool(tool_name)
        if tool is None:
            return json.dumps({"error": f"Unknown tool: {tool_name}"})

        try:
            result = await tool.execute(**arguments)
            return result if isinstance(result, str) else json.dumps(result)
        except Exception as e:
            return json.dumps({"error": str(e)})

    async def _build_messages(self, attachment_context: Optional[str] = None) -> List[Dict[str, Any]]:
        """Assemble the system prompt + memory context + conversation history."""
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + self._history

        # Load recent + long-term memory context and prepend as system notes
        try:
            max_chars = config.MAX_MEMORY_TOKENS // 2
            long_term_memory = await self.memory_manager.get_long_term_memory(max_chars=max_chars)
            if long_term_memory:
                messages.insert(1, {
                    "role": "system",
                    "content": f"Long-term memory about this user:\n{long_term_memory}"
                })

            recent_memory = await self.memory_manager.get_recent_memory(days=3)
            if recent_memory:
                messages.insert(1, {
                    "role": "system",
                    "content": f"Recent conversation memory:\n{recent_memory[:max_chars]}"
                })
        except Exception:
            pass

        # Describes an image/video the user just attached to their latest message
        # (see chatty_web_server.py's websocket_chat). Grafted onto that user
        # turn's own content - live-tested against this deployment's local model
        # and found that a *separate system message* saying "here's what the
        # image shows" got silently overridden by the model's trained "I can't
        # see images" refusal once real memory context padded the conversation,
        # even with explicit "don't say you can't see images" instructions.
        # Folding it into the user message itself (what the user is literally
        # saying to you) doesn't trigger that reflex. Builds a new dict rather
        # than mutating messages[-1] in place, since that dict is the same
        # object as self._history[-1] (shallow list copy above) - mutating it
        # would leak the description into persisted/displayed history, which
        # should stay just the user's caption.
        if attachment_context and messages and messages[-1]["role"] == "user":
            last = messages[-1]
            caption = last.get("content") or ""
            merged = f"{attachment_context}\n\n{caption}".strip() if caption else attachment_context
            messages[-1] = {**last, "content": merged}

        return messages

    async def _run_completion(self, messages: List[Dict[str, Any]], tools: List[Dict]) -> AsyncGenerator[str, None]:
        """Run the tool-calling completion loop, yielding text deltas as they arrive.

        Pure: does not touch self._history or memory_manager.
        """
        for _ in range(MAX_TOOL_ITERATIONS):
            assistant_content = ""
            tool_calls_acc: Dict[int, Dict] = {}  # index -> {id, name, arguments}

            async for chunk in self.llm.stream_with_tools(
                messages, tools, tool_choice="auto" if tools else "none",
            ):
                if chunk.text_delta:
                    assistant_content += chunk.text_delta
                    yield chunk.text_delta

                for tcd in chunk.tool_call_deltas:
                    idx = tcd.index
                    if idx not in tool_calls_acc:
                        tool_calls_acc[idx] = {"id": "", "name": "", "arguments": ""}
                    if tcd.id:
                        tool_calls_acc[idx]["id"] = tcd.id
                    if tcd.name:
                        tool_calls_acc[idx]["name"] = tcd.name
                    if tcd.arguments_delta:
                        tool_calls_acc[idx]["arguments"] += tcd.arguments_delta

            # If no tool calls, we're done
            if not tool_calls_acc:
                messages.append({"role": "assistant", "content": assistant_content})
                break

            # Build assistant message with tool_calls
            tool_calls_list = []
            for idx in sorted(tool_calls_acc.keys()):
                tc = tool_calls_acc[idx]
                tool_calls_list.append({
                    "id": tc["id"],
                    "type": "function",
                    "function": {"name": tc["name"], "arguments": tc["arguments"]},
                })
            messages.append({
                "role": "assistant",
                "content": assistant_content or None,
                "tool_calls": tool_calls_list,
            })

            # Execute tool calls and add results
            for tc in tool_calls_list:
                try:
                    args = json.loads(tc["function"]["arguments"])
                except json.JSONDecodeError:
                    args = {}
                tool_result = await self._execute_tool(tc["function"]["name"], args)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": tool_result,
                })

        else:
            # Max iterations reached
            yield "\n[Max tool iterations reached]"

    async def stream(
        self, user_message: str, attachment_context: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """Process a new user message and stream response text chunks.

        Maintains conversation history across calls (within the same agent instance).
        Saves the completed interaction to memory. Persists partial output even if
        cancelled mid-stream, so self._history stays consistent with what the caller
        ends up persisting elsewhere.

        `attachment_context` (optional) is a text description of an image/video the
        user attached to this message (see chatty_web_server.py's websocket_chat) -
        fed to the LLM as an ephemeral system note for this turn only.
        """
        self._history.append({"role": "user", "content": user_message})

        # Trim history to avoid token bloat
        if len(self._history) > MAX_HISTORY:
            self._history = self._history[-MAX_HISTORY:]

        full_response = ""
        try:
            messages = await self._build_messages(attachment_context)
            tools = self._get_tools()
            async for delta in self._run_completion(messages, tools):
                full_response += delta
                yield delta
        finally:
            self._history.append({"role": "assistant", "content": full_response})
            try:
                await self.memory_manager.add_interaction(user_message, full_response)
            except Exception:
                pass

    async def regenerate(self) -> AsyncGenerator[str, None]:
        """Re-run completion for the current last user message, replacing the last response.

        Does not log to memory (the superseded response was never a genuine new turn),
        so a stale answer doesn't linger in the markdown memory log fed to future turns.
        """
        if self._history and self._history[-1]["role"] == "assistant":
            self._history.pop()
        if not self._history or self._history[-1]["role"] != "user":
            raise ValueError("No previous user message to regenerate a response for")

        full_response = ""
        try:
            messages = await self._build_messages()
            tools = self._get_tools()
            async for delta in self._run_completion(messages, tools):
                full_response += delta
                yield delta
        finally:
            self._history.append({"role": "assistant", "content": full_response})

    async def edit_last_user_message(self, new_text: str) -> AsyncGenerator[str, None]:
        """Overwrite the last user message and re-run completion for it.

        Does not log to memory, for the same reason as regenerate().
        """
        if self._history and self._history[-1]["role"] == "assistant":
            self._history.pop()
        if not self._history or self._history[-1]["role"] != "user":
            raise ValueError("No previous user message to edit")
        self._history[-1]["content"] = new_text

        full_response = ""
        try:
            messages = await self._build_messages()
            tools = self._get_tools()
            async for delta in self._run_completion(messages, tools):
                full_response += delta
                yield delta
        finally:
            self._history.append({"role": "assistant", "content": full_response})
