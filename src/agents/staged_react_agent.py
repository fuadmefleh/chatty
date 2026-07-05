"""Staged ReACT (Reasoning and Acting) Agent.

This agent implements a structured reasoning process with explicit stages:
1. DECOMPOSE - Break down the user's query into sub-tasks
2. MEMORY - Check if memory can answer the query
3. PLAN - Determine which skills/tools are needed
4. EXECUTE - Run the chosen skills/tools
5. SYNTHESIZE - Combine results into a coherent answer
6. REFLECT - Evaluate if the answer is complete and correct
7. MEMORIZE - Store useful information for future use
"""
import asyncio
import json
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import tiktoken
from src.core import config
from src.core.llm import LLMProvider, get_llm_provider, with_retries
from src.core.memory import MemoryManager
from src.core.skills_manager import SkillsManager
from src.core.memory_tools import MemoryTools
from src.core.logging_config import get_agent_logger, get_api_logger, get_tools_logger

# Get specialized loggers
agent_logger = get_agent_logger()
api_logger = get_api_logger()
tools_logger = get_tools_logger()


class ReACTStage(Enum):
    """Stages of the ReACT reasoning process."""
    DECOMPOSE = "decompose"
    MEMORY = "memory"
    PLAN = "plan"
    EXECUTE = "execute"
    SYNTHESIZE = "synthesize"
    REFLECT = "reflect"
    MEMORIZE = "memorize"
    COMPLETE = "complete"


@dataclass
class ReACTState:
    """Tracks the state of the ReACT reasoning process."""
    stage: ReACTStage = ReACTStage.DECOMPOSE
    user_query: str = ""
    
    # Decomposition results
    sub_tasks: List[str] = field(default_factory=list)
    query_type: str = ""  # question, action, conversation, etc.
    
    # Memory results
    memory_relevant: bool = False
    memory_context: str = ""
    
    # Planning results
    skills_needed: List[str] = field(default_factory=list)
    tools_to_use: List[str] = field(default_factory=list)
    execution_plan: List[Dict] = field(default_factory=list)
    
    # Execution results
    tool_results: List[Dict[str, Any]] = field(default_factory=list)
    
    # Synthesis
    synthesized_answer: str = ""
    
    # Reflection
    confidence_score: float = 0.0
    needs_more_info: bool = False
    reflection_notes: str = ""
    
    # Memorization
    facts_to_remember: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        """Convert state to dictionary for logging."""
        return {
            "stage": self.stage.value,
            "user_query": self.user_query[:100] + "..." if len(self.user_query) > 100 else self.user_query,
            "sub_tasks": self.sub_tasks,
            "skills_needed": self.skills_needed,
            "tools_to_use": self.tools_to_use,
            "tool_results_count": len(self.tool_results),
            "confidence_score": self.confidence_score
        }


class StagedReACTAgent:
    """ReACT agent with explicit reasoning stages."""
    
    # Token management constants
    MAX_TOKENS_PER_MINUTE = 180000  # Conservative limit (actual is 200K)
    MAX_TOOL_RESULT_CHARS = 1500  # Max characters per tool result
    MAX_MEMORY_CONTEXT_CHARS = 3000  # Max memory context size
    MAX_SYNTHESIS_CONTEXT_CHARS = 8000  # Max context for synthesis
    MAX_HISTORY_CONTEXT_CHARS = 2000  # Max conversation history included in prompts
    
    def __init__(
        self, memory_manager: MemoryManager, skills_manager: SkillsManager,
        llm_provider: Optional[LLMProvider] = None,
    ):
        """Initialize the staged ReACT agent.

        Args:
            memory_manager: Memory manager instance
            skills_manager: Skills manager instance (with dynamic tool loading)
            llm_provider: Optional LLM backend override (defaults to the
                configured CHAT_PROVIDER); mainly used to inject a fake in tests
        """
        self.llm = llm_provider or get_llm_provider()
        self.memory_manager = memory_manager
        self.skills_manager = skills_manager
        self.max_iterations = config.MAX_ITERATIONS
        self.memory_tools = MemoryTools(memory_manager.user_id)
        self.progress_callback = None  # Optional callback for progress updates
        self._background_tasks: set = set()  # Keeps REFLECT/MEMORIZE tasks alive until done
        
        # Initialize token encoder
        try:
            self.encoder = tiktoken.encoding_for_model(config.OPENAI_MODEL)
        except KeyError:
            self.encoder = tiktoken.get_encoding("cl100k_base")
        
        agent_logger.info(
            f"Initialized StagedReACTAgent for user {memory_manager.user_id} "
            f"with {len(self.skills_manager.get_all_tools())} skill tools"
        )
    
    async def think(self, user_message: str, conversation_history: List[Dict] = None, progress_callback=None) -> str:
        """Process user message through staged ReACT reasoning.
        
        Args:
            user_message: Message from the user
            conversation_history: Optional conversation history
            progress_callback: Optional async function to call with progress updates
            
        Returns:
            Agent's response
        """
        if conversation_history is None:
            conversation_history = []
        
        agent_logger.info(f"\n{'='*80}\nSTARTED ReACT PROCESS\nUser: {user_message}\n{'='*80}")
        
        # Initialize state
        state = ReACTState(user_query=user_message)
        
        try:
            # Stage 1: DECOMPOSE
            state = await self._stage_decompose(state, conversation_history)
            agent_logger.info(f"[DECOMPOSE] Query type: {state.query_type}, Sub-tasks: {state.sub_tasks}")
            
            # Stage 2: MEMORY
            state = await self._stage_memory(state)
            agent_logger.info(f"[MEMORY] Relevant: {state.memory_relevant}")
            
            # Stage 3: PLAN
            state = await self._stage_plan(state)
            agent_logger.info(f"[PLAN] Skills: {state.skills_needed}, Tools: {state.tools_to_use}")
            
            # Send progress update if tools will be executed
            if progress_callback and state.tools_to_use:
                tool_list = ", ".join(state.tools_to_use[:3])
                if len(state.tools_to_use) > 3:
                    tool_list += f" (+{len(state.tools_to_use) - 3} more)"
                await progress_callback(f"🔧 Using: {tool_list}...")
            
            # Stage 4: EXECUTE
            state = await self._stage_execute(state)
            agent_logger.info(f"[EXECUTE] Results count: {len(state.tool_results)}")
            
            # Send progress update when starting synthesis
            if progress_callback and state.tool_results:
                await progress_callback("✍️ Preparing response...")
            
            # Stage 5: SYNTHESIZE
            state = await self._stage_synthesize(state, conversation_history)
            agent_logger.info(f"[SYNTHESIZE] Answer length: {len(state.synthesized_answer)}")

            # Stages 6-7 (REFLECT, MEMORIZE) don't affect the reply, so run them
            # in the background after we return the answer instead of blocking on
            # two more LLM round-trips.
            task = asyncio.create_task(self._finish_reasoning(state))
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)

            return state.synthesized_answer

        except Exception as e:
            agent_logger.error(f"Error in ReACT process: {e}", exc_info=True)
            return f"I apologize, but I encountered an error while processing your request: {str(e)}"

    async def _finish_reasoning(self, state: ReACTState) -> None:
        """Run REFLECT and MEMORIZE after the reply has already been sent.

        Nothing awaits this task, so it must handle its own errors rather than
        letting them propagate silently to the event loop.
        """
        try:
            # Stage 6: REFLECT
            state = await self._stage_reflect(state)
            agent_logger.info(f"[REFLECT] Confidence: {state.confidence_score}, Notes: {state.reflection_notes[:100]}")

            # Stage 7: MEMORIZE
            state = await self._stage_memorize(state)
            agent_logger.info(f"[MEMORIZE] Facts stored: {len(state.facts_to_remember)}")
        except Exception as e:
            agent_logger.error(f"Error in background REFLECT/MEMORIZE: {e}", exc_info=True)


    async def _stage_decompose(self, state: ReACTState, history: List[Dict]) -> ReACTState:
        """Stage 1: Decompose the user's query into sub-tasks.
        
        Analyzes the query to understand:
        - What type of query is it (question, action, conversation)?
        - What sub-tasks need to be accomplished?
        - What information is needed?
        """
        state.stage = ReACTStage.DECOMPOSE

        # Get available skills for context
        skills_summary = self._get_skills_summary()
        recent_history = self._format_history(history[-6:])
        history_section = (
            f"\nRecent Conversation:\n{recent_history}\n" if recent_history else ""
        )

        prompt = f"""Analyze this user query and decompose it into actionable sub-tasks.
{history_section}
User Query: "{state.user_query}"

Available Skills:
{skills_summary}

Respond in JSON format:
{{
    "query_type": "question|action|conversation|greeting",
    "sub_tasks": ["task1", "task2", ...],
    "requires_tools": true|false,
    "key_entities": ["entity1", "entity2", ...]
}}

Be concise. If it's a simple greeting or conversation, sub_tasks can be empty."""

        response = await self._call_llm(prompt, response_format="json")
        
        try:
            result = json.loads(response)
            state.query_type = result.get("query_type", "conversation")
            state.sub_tasks = result.get("sub_tasks", [])
        except json.JSONDecodeError:
            state.query_type = "conversation"
            state.sub_tasks = []
        
        return state
    
    async def _stage_memory(self, state: ReACTState) -> ReACTState:
        """Stage 2: Check if memory can answer the query.
        
        Searches memory for relevant information that could help answer
        the user's query without needing external tools.
        """
        state.stage = ReACTStage.MEMORY
        
        # Load memory context with strict limits
        short_term = await self.memory_manager.get_recent_memory(days=2)
        long_term = await self.memory_manager.get_long_term_memory()
        
        # Truncate memory to prevent token bloat
        max_short = self.MAX_MEMORY_CONTEXT_CHARS // 2
        max_long = self.MAX_MEMORY_CONTEXT_CHARS // 2
        short_term = short_term[:max_short] if short_term else ""
        long_term = long_term[:max_long] if long_term else ""
        
        # Check if memory is relevant
        prompt = f"""Given this user query and available memory, determine if memory contains relevant information.

User Query: "{state.user_query}"
Sub-tasks: {state.sub_tasks}

Recent Memory (last 2 days):
{short_term}

Long-term Memory:
{long_term}

Respond in JSON:
{{
    "memory_relevant": true|false,
    "relevant_info": "summary of relevant information found, or empty string",
    "can_answer_fully": true|false
}}"""

        response = await self._call_llm(prompt, response_format="json")
        
        try:
            result = json.loads(response)
            state.memory_relevant = result.get("memory_relevant", False)
            state.memory_context = result.get("relevant_info", "")
        except json.JSONDecodeError:
            state.memory_relevant = False
            state.memory_context = ""
        
        return state
    
    async def _stage_plan(self, state: ReACTState) -> ReACTState:
        """Stage 3: Determine which skills and tools are needed.
        
        Based on the decomposed tasks and memory check, plans which
        skills and tools to use and in what order.
        """
        state.stage = ReACTStage.PLAN
        
        # If simple conversation/greeting, skip tools
        if state.query_type in ["greeting", "conversation"] and not state.sub_tasks:
            state.skills_needed = []
            state.tools_to_use = []
            state.execution_plan = []
            return state
        
        # Get available tools
        all_tools = self.skills_manager.get_openai_tools()
        memory_tools = self._get_memory_tools_definitions()
        combined_tools = all_tools + memory_tools
        
        tools_summary = "\n".join([
            f"- {t['function']['name']}: {t['function']['description'][:100]}"
            for t in combined_tools
        ])
        
        prompt = f"""Based on the user's query and sub-tasks, determine which tools to use.

User Query: "{state.user_query}"
Query Type: {state.query_type}
Sub-tasks: {state.sub_tasks}
Memory Context Available: {bool(state.memory_context)}

Available Tools:
{tools_summary}

IMPORTANT GUIDELINES:
1. Choose the MINIMUM number of tools needed
2. Avoid redundant tools (e.g., don't use both get_recent_emails AND search_emails for the same query)
3. For emails, prefer ONE targeted tool over multiple broad searches
4. Limit max_results to 10-20 items to prevent token overload
5. Only use include_body=true if user explicitly needs email content

Respond in JSON:
{{
    "tools_needed": ["tool_name1", "tool_name2", ...],
    "execution_order": [
        {{"tool": "tool_name", "purpose": "why", "args_hint": {{}}}},
        ...
    ],
    "reasoning": "brief explanation"
}}

If no tools needed, return empty arrays."""

        response = await self._call_llm(prompt, response_format="json")
        
        try:
            result = json.loads(response)
            state.tools_to_use = result.get("tools_needed", [])
            state.execution_plan = result.get("execution_order", [])
            
            # Determine skills from tools
            for tool_name in state.tools_to_use:
                skill = self.skills_manager.get_skill_for_tool(tool_name)
                if skill and skill.name not in state.skills_needed:
                    state.skills_needed.append(skill.name)
        except json.JSONDecodeError:
            state.tools_to_use = []
            state.execution_plan = []
        
        return state
    
    async def _stage_execute(self, state: ReACTState) -> ReACTState:
        """Stage 4: Execute the planned tools.
        
        Runs each tool in the execution plan, handling function calling
        with the LLM to determine proper arguments.
        """
        state.stage = ReACTStage.EXECUTE
        
        if not state.tools_to_use:
            return state
        
        # Get tool definitions
        skill_tools = self.skills_manager.get_openai_tools()
        memory_tools = self._get_memory_tools_definitions()
        all_tools = skill_tools + memory_tools
        
        # Filter to only needed tools
        needed_tools = [t for t in all_tools if t['function']['name'] in state.tools_to_use]
        
        # Build execution context
        messages = [
            {"role": "system", "content": self._build_execution_prompt(state)},
            {"role": "user", "content": state.user_query}
        ]
        
        # Execute with function calling loop
        iteration = 0
        while iteration < self.max_iterations:
            iteration += 1
            
            try:
                # Check token count before making request
                estimated_tokens = self._estimate_tokens(messages)
                if estimated_tokens > self.MAX_TOKENS_PER_MINUTE:
                    agent_logger.warning(f"Token count too high: {estimated_tokens}, compressing context")
                    messages = self._compress_messages(messages)
                
                response = await with_retries(
                    lambda: self.llm.complete_with_tools(
                        messages, needed_tools,
                        tool_choice="auto" if needed_tools else "none",
                    ),
                    logger=api_logger,
                )

                if response.tool_calls:
                    messages.append(response.to_openai_message())

                    for tool_call in response.tool_calls:
                        function_name = tool_call.name
                        try:
                            function_args = json.loads(tool_call.arguments)
                        except json.JSONDecodeError:
                            function_args = {}

                        tools_logger.info(f"Executing: {function_name}({function_args})")

                        # Execute the tool
                        result = await self._execute_tool(function_name, function_args)

                        # Truncate large results to prevent token bloat
                        truncated_result = self._truncate_tool_result(result, function_name)

                        state.tool_results.append({
                            "tool": function_name,
                            "args": function_args,
                            "result": truncated_result
                        })

                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": function_name,
                            "content": truncated_result
                        })
                else:
                    # No more tool calls needed
                    break
                    
            except Exception as e:
                tools_logger.error(f"Error in execution loop: {e}", exc_info=True)
                break
        
        return state
    
    async def _stage_synthesize(self, state: ReACTState, history: List[Dict]) -> ReACTState:
        """Stage 5: Synthesize results into a coherent answer.
        
        Combines tool results, memory context, and conversation history
        to generate a natural, helpful response.
        """
        state.stage = ReACTStage.SYNTHESIZE

        # Build synthesis context
        context_parts = []

        recent_history = self._format_history(history[-6:])
        if recent_history:
            context_parts.append(f"Recent Conversation:\n{recent_history}")

        if state.memory_context:
            context_parts.append(f"Memory Context:\n{state.memory_context}")
        
        if state.tool_results:
            # Intelligently summarize tool results
            results_text = "\n".join([
                f"Tool '{r['tool']}': {r['result'][:800]}"
                for r in state.tool_results
            ])
            context_parts.append(f"Tool Results:\n{results_text}")
        
        context = "\n\n".join(context_parts) if context_parts else "No additional context."
        
        # Ensure context doesn't exceed limits
        if len(context) > self.MAX_SYNTHESIS_CONTEXT_CHARS:
            context = context[:self.MAX_SYNTHESIS_CONTEXT_CHARS] + "\n\n[Context truncated for brevity]"
        
        prompt = f"""Synthesize a natural, helpful response for the user.

User Query: "{state.user_query}"
Query Type: {state.query_type}

Context:
{context}

Instructions:
- Be warm, personable, and engaging
- Present information clearly and concisely
- If data was retrieved, summarize it meaningfully
- If it's a greeting, respond naturally
- Use the Recent Conversation (if present) to resolve follow-ups, pronouns, and
  references to earlier turns — don't repeat information already covered
- Don't mention internal processes or tools used

Respond directly to the user:"""

        state.synthesized_answer = await self._call_llm(prompt)
        
        return state
    
    async def _stage_reflect(self, state: ReACTState) -> ReACTState:
        """Stage 6: Reflect on the response quality.
        
        Evaluates whether the synthesized answer adequately addresses
        the user's query and identifies any gaps.
        """
        state.stage = ReACTStage.REFLECT
        
        prompt = f"""Reflect on this response. Did it adequately address the user's query?

User Query: "{state.user_query}"
Sub-tasks: {state.sub_tasks}
Response Given: "{state.synthesized_answer[:500]}"
Tools Used: {[r['tool'] for r in state.tool_results]}

Respond in JSON:
{{
    "confidence_score": 0.0-1.0,
    "addressed_all_tasks": true|false,
    "missing_information": ["item1", ...],
    "reflection_notes": "brief self-assessment"
}}"""

        response = await self._call_llm(prompt, response_format="json")
        
        try:
            result = json.loads(response)
            state.confidence_score = result.get("confidence_score", 0.8)
            state.needs_more_info = not result.get("addressed_all_tasks", True)
            state.reflection_notes = result.get("reflection_notes", "")
        except json.JSONDecodeError:
            state.confidence_score = 0.7
            state.reflection_notes = "Unable to fully assess response quality"
        
        return state
    
    async def _stage_memorize(self, state: ReACTState) -> ReACTState:
        """Stage 7: Memorize useful information.
        
        Identifies any new facts, preferences, or important information
        from the conversation that should be stored for future use.
        """
        state.stage = ReACTStage.MEMORIZE
        
        prompt = f"""Identify any new, important facts from this conversation that should be remembered.

User Query: "{state.user_query}"
Response Given: "{state.synthesized_answer[:500]}"

Look for:
- Personal preferences the user mentioned
- Important dates, names, or facts shared
- Goals or projects mentioned
- Corrections to previous information

Respond in JSON:
{{
    "facts_to_remember": [
        {{"fact": "description", "category": "preference|personal|goal|other"}},
        ...
    ]
}}

If nothing important to remember, return empty array."""

        response = await self._call_llm(prompt, response_format="json")
        
        try:
            result = json.loads(response)
            facts = result.get("facts_to_remember", [])
            
            for fact_obj in facts:
                fact = fact_obj.get("fact", "")
                if fact:
                    state.facts_to_remember.append(fact)
                    # Actually save to memory
                    try:
                        await self.memory_tools.save_important_fact(
                            category=fact_obj.get("category", "other"),
                            content=fact
                        )
                        agent_logger.info(f"Saved fact to memory: {fact[:50]}")
                    except Exception as e:
                        agent_logger.warning(f"Failed to save fact: {e}")
        except json.JSONDecodeError:
            pass
        
        state.stage = ReACTStage.COMPLETE
        return state

    async def _call_llm(self, prompt: str, response_format: str = "text") -> str:
        """Make an LLM call for internal reasoning.

        Args:
            prompt: The prompt to send
            response_format: "text" or "json"

        Returns:
            LLM response content
        """
        try:
            response = await with_retries(
                lambda: self.llm.complete(
                    [{"role": "user", "content": prompt}],
                    response_format=response_format,
                    temperature=0.3,  # Lower for more consistent reasoning
                ),
                logger=api_logger,
            )
            return response.content or ""

        except Exception as e:
            api_logger.error(f"LLM call failed: {e}")
            return "{}" if response_format == "json" else ""
    
    async def _execute_tool(self, tool_name: str, arguments: Dict) -> str:
        """Execute a tool by name.
        
        Args:
            tool_name: Name of the tool
            arguments: Tool arguments
            
        Returns:
            Tool execution result
        """
        # Check if it's a memory tool
        if tool_name.startswith(("search_memory", "read_memory", "list_memory", 
                                  "get_memory", "save_important")):
            return await self._execute_memory_tool(tool_name, arguments)
        
        # Otherwise, it's a skill tool
        return await self.skills_manager.execute_tool(tool_name, arguments)
    
    async def _execute_memory_tool(self, tool_name: str, arguments: Dict) -> str:
        """Execute a memory tool.
        
        Args:
            tool_name: Name of the memory tool
            arguments: Tool arguments
            
        Returns:
            Tool result
        """
        try:
            if tool_name == "search_memory_grep":
                return await self.memory_tools.search_memory_grep(**arguments)
            elif tool_name == "search_recent_mentions":
                return await self.memory_tools.search_recent_mentions(**arguments)
            elif tool_name == "read_memory_file":
                return await self.memory_tools.read_memory_file(**arguments)
            elif tool_name == "list_memory_files":
                return await self.memory_tools.list_memory_files(**arguments)
            elif tool_name == "get_memory_summary":
                return await self.memory_tools.get_memory_summary()
            elif tool_name == "save_important_fact":
                return await self.memory_tools.save_important_fact(**arguments)
            else:
                return f"Unknown memory tool: {tool_name}"
        except Exception as e:
            return f"Error executing {tool_name}: {str(e)}"
    
    def _get_skills_summary(self) -> str:
        """Get a summary of available skills."""
        skills = self.skills_manager.get_all_skills()
        if not skills:
            return "No skills available."

        return "\n".join([
            f"- {s.name}: {s.description[:100]}"
            for s in skills
        ])

    def _format_history(self, history: List[Dict], max_chars: int = None) -> str:
        """Render recent conversation turns as a compact transcript for prompts.

        Args:
            history: List of {"role": ..., "content": ...} messages
            max_chars: Truncation limit; defaults to MAX_HISTORY_CONTEXT_CHARS

        Returns:
            Formatted transcript, or empty string if no history
        """
        if not history:
            return ""

        max_chars = max_chars if max_chars is not None else self.MAX_HISTORY_CONTEXT_CHARS

        lines = []
        for msg in history:
            role = "User" if msg.get("role") == "user" else "Assistant"
            content = msg.get("content", "")
            lines.append(f"{role}: {content}")

        transcript = "\n".join(lines)
        if len(transcript) > max_chars:
            # Keep the most recent turns (tail) rather than the oldest
            transcript = "[...earlier turns truncated...]\n" + transcript[-max_chars:]

        return transcript

    def _get_memory_tools_definitions(self) -> List[Dict]:
        """Get memory tools in OpenAI format."""
        return [
            {
                "type": "function",
                "function": {
                    "name": "search_memory_grep",
                    "description": "Search all memory files for a keyword or phrase",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "pattern": {"type": "string", "description": "The pattern to search for"}
                        },
                        "required": ["pattern"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "save_important_fact",
                    "description": "Save an important fact to long-term memory",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "fact": {"type": "string", "description": "The fact to remember"},
                            "category": {"type": "string", "description": "Category: preference, personal, goal, other"}
                        },
                        "required": ["fact"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_memory_summary",
                    "description": "Get a summary of all available memory",
                    "parameters": {"type": "object", "properties": {}, "required": []}
                }
            }
        ]
    
    def _build_execution_prompt(self, state: ReACTState) -> str:
        """Build the system prompt for tool execution."""
        return f"""You are executing tools to answer the user's query.

Query: {state.user_query}
Planned tools: {state.tools_to_use}

Call the necessary tools to gather information. After getting results, 
you can call additional tools if needed, or stop when you have enough information."""
    
    async def chat(self, user_message: str, conversation_history: List[Dict] = None) -> str:
        """Chat interface (alias for think).
        
        Args:
            user_message: Message from user
            conversation_history: Optional conversation history
            
        Returns:
            Assistant response
        """
        return await self.think(user_message, conversation_history)
    
    def _estimate_tokens(self, messages: List[Dict]) -> int:
        """Estimate token count for messages.
        
        Args:
            messages: List of message dictionaries
            
        Returns:
            Estimated token count
        """
        try:
            total = 0
            for msg in messages:
                # Handle both dict and Pydantic model (ChatCompletionMessage)
                if hasattr(msg, 'content'):
                    content = str(msg.content if msg.content else "")
                elif isinstance(msg, dict):
                    content = str(msg.get("content", ""))
                else:
                    content = str(msg)
                total += len(self.encoder.encode(content))
            return total
        except Exception:
            # Fallback to character-based estimation
            total_chars = 0
            for msg in messages:
                # Handle both dict and Pydantic model (ChatCompletionMessage)
                if hasattr(msg, 'content'):
                    total_chars += len(str(msg.content if msg.content else ""))
                elif isinstance(msg, dict):
                    total_chars += len(str(msg.get("content", "")))
                else:
                    total_chars += len(str(msg))
            return total_chars // 4  # Rough estimate: 4 chars per token
    
    def _compress_messages(self, messages: List[Dict]) -> List[Dict]:
        """Compress messages to fit within token limits.
        
        Args:
            messages: Original messages
            
        Returns:
            Compressed messages
        """
        compressed = []
        for msg in messages:
            # Handle both dict and Pydantic model (ChatCompletionMessage)
            if hasattr(msg, 'role'):
                role = msg.role
                content = str(msg.content if msg.content else "")
            elif isinstance(msg, dict):
                role = msg.get("role")
                content = msg.get("content", "")
            else:
                compressed.append(msg)
                continue
            
            # Keep system and user messages mostly intact
            if role in ["system", "user"]:
                compressed.append(msg)
            # Heavily compress tool results
            elif role == "tool":
                truncated_content = content[:500] + "..." if len(content) > 500 else content
                if isinstance(msg, dict):
                    compressed.append({**msg, "content": truncated_content})
                else:
                    # For Pydantic models, keep original (can't easily modify)
                    compressed.append(msg)
            else:
                compressed.append(msg)
        
        return compressed
    
    def _truncate_tool_result(self, result: str, tool_name: str) -> str:
        """Intelligently truncate tool results based on tool type.
        
        Args:
            result: Tool result string
            tool_name: Name of the tool
            
        Returns:
            Truncated result
        """
        if not result or len(result) <= self.MAX_TOOL_RESULT_CHARS:
            return result
        
        # For email tools, try to parse and summarize
        if "email" in tool_name.lower():
            try:
                data = json.loads(result)
                if isinstance(data, dict) and "emails" in data:
                    emails = data["emails"]
                    # Keep only essential fields and limit count
                    summarized_emails = []
                    for email in emails[:10]:  # Max 10 emails
                        summarized = {
                            "from": email.get("from", ""),
                            "subject": email.get("subject", ""),
                            "date": email.get("date", ""),
                            "snippet": email.get("snippet", "")[:200],  # Truncate snippet
                        }
                        # Only include message_id if no body
                        if "body" not in email:
                            summarized["message_id"] = email.get("message_id", "")
                        summarized_emails.append(summarized)
                    
                    return json.dumps({"count": data.get("count", 0), "emails": summarized_emails}, indent=2)
            except json.JSONDecodeError:
                pass
        
        # Generic truncation for other results
        return result[:self.MAX_TOOL_RESULT_CHARS] + "\\n\\n[Result truncated for brevity]"
