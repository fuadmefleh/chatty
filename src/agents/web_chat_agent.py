"""Web Chat Agent - a simplified agent for the Chatty web dashboard.

Unlike StagedReACTAgent (which has 7 stages and Telegram-specific code),
this agent uses a direct OpenAI function-calling loop:
1. Send user message + conversation history + available tools
2. If OpenAI requests tool calls, execute them and feed results back
3. Yield text chunks as they arrive (streaming)
4. Save interaction to memory when done

Usage:
    agent = WebChatAgent(skills_manager=sm, memory_manager=mm)
    async for chunk in agent.stream("Hello!"):
        print(chunk, end="", flush=True)
"""
import json
from typing import AsyncGenerator, List, Dict, Any
from openai import AsyncOpenAI
from src.core import config
from src.core.memory import MemoryManager
from src.core.skills_manager import SkillsManager

MAX_TOOL_ITERATIONS = 8
MAX_HISTORY = 20  # messages kept in sliding window
SYSTEM_PROMPT = """You are Chatty, a helpful AI assistant accessible via a web dashboard. \
You have access to skills and tools to help the user with notes, orders, budget, reminders, \
web search, and more. Be concise, friendly, and helpful. \
When using tools, act on the results and provide a clear, direct answer."""


class WebChatAgent:
    """Direct OpenAI function-calling agent with streaming, for the web UI."""

    def __init__(self, skills_manager: SkillsManager, memory_manager: MemoryManager):
        self.client = AsyncOpenAI(api_key=config.CHAT_API_KEY, base_url=config.CHAT_BASE_URL)
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

    async def stream(self, user_message: str) -> AsyncGenerator[str, None]:
        """Process a user message and stream response text chunks.

        Maintains conversation history across calls (within the same agent instance).
        Saves the completed interaction to memory.
        """
        # Build messages
        self._history.append({"role": "user", "content": user_message})

        # Trim history to avoid token bloat
        if len(self._history) > MAX_HISTORY:
            self._history = self._history[-MAX_HISTORY:]

        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + self._history

        # Load recent memory context and prepend as a system note
        try:
            recent_memory = await self.memory_manager.get_recent_memory(days=3)
            if recent_memory:
                messages.insert(1, {
                    "role": "system",
                    "content": f"Recent conversation memory:\n{recent_memory[:3000]}"
                })
        except Exception:
            pass

        tools = self._get_tools()
        full_response = ""

        # Only set temperature for models that support it — o1, o1-mini,
        # o3-mini, and some newer OpenAI models reject a custom temperature.
        model_lower = config.CHAT_MODEL.lower()
        unsupported_temp_models = ['o1', 'o3', 'gpt-5']
        supports_temperature = not any(x in model_lower for x in unsupported_temp_models)

        for _ in range(MAX_TOOL_ITERATIONS):
            # Call OpenAI with streaming
            stream_kwargs = dict(
                model=config.CHAT_MODEL,
                messages=messages,
                stream=True,
            )
            if supports_temperature:
                stream_kwargs["temperature"] = 0.7
            if tools:
                stream_kwargs["tools"] = tools
                stream_kwargs["tool_choice"] = "auto"

            assistant_content = ""
            tool_calls_acc: Dict[int, Dict] = {}  # index -> {id, name, arguments}

            async with await self.client.chat.completions.create(**stream_kwargs) as stream:
                async for chunk in stream:
                    delta = chunk.choices[0].delta if chunk.choices else None
                    if delta is None:
                        continue

                    # Accumulate text
                    if delta.content:
                        assistant_content += delta.content
                        full_response += delta.content
                        yield delta.content

                    # Accumulate tool calls
                    if delta.tool_calls:
                        for tc in delta.tool_calls:
                            idx = tc.index
                            if idx not in tool_calls_acc:
                                tool_calls_acc[idx] = {
                                    "id": tc.id or "",
                                    "name": tc.function.name if tc.function else "",
                                    "arguments": "",
                                }
                            if tc.id:
                                tool_calls_acc[idx]["id"] = tc.id
                            if tc.function:
                                if tc.function.name:
                                    tool_calls_acc[idx]["name"] = tc.function.name
                                if tc.function.arguments:
                                    tool_calls_acc[idx]["arguments"] += tc.function.arguments

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
            full_response += "\n[Max tool iterations reached]"

        # Save to history and memory
        self._history.append({"role": "assistant", "content": full_response})
        try:
            await self.memory_manager.add_interaction(user_message, full_response)
        except Exception:
            pass
