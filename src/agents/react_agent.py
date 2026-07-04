"""Proper ReACT (Reasoning and Acting) agent with function calling.

NOTE: This is the legacy ReACT agent. Consider using StagedReACTAgent instead
for the new staged reasoning process.
"""
import json
from typing import List, Dict
from openai import AsyncOpenAI
from src.core import config
from src.core.memory import MemoryManager
from src.core.skills import SkillsManager
from src.core.memory_tools import MemoryTools
from src.tools import create_core_tool_registry
from src.core.logging_config import get_agent_logger, get_api_logger, get_tools_logger

# Get specialized loggers
agent_logger = get_agent_logger()
api_logger = get_api_logger()
tools_logger = get_tools_logger()


class ReACTAgent:
    """True ReACT agent using OpenAI function calling."""
    
    def __init__(self, memory_manager: MemoryManager, skills_manager: SkillsManager):
        """Initialize the ReACT agent.
        
        Args:
            memory_manager: Memory manager instance
            skills_manager: Skills manager instance
        """
        self.client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
        self.memory_manager = memory_manager
        self.skills_manager = skills_manager
        self.max_iterations = config.MAX_ITERATIONS
        self.memory_tools = MemoryTools(memory_manager.user_id)
        
        # Initialize tool registry with core tools only
        self.tool_registry = create_core_tool_registry(self.memory_tools, self.skills_manager)
        agent_logger.info(f"Initialized ReACTAgent for user {memory_manager.user_id} with {len(self.tool_registry)} tools")
    
    def _get_tools_definition(self) -> List[Dict]:
        """Get OpenAI function calling tool definitions.
        
        Returns:
            List of tool definitions for OpenAI API
        """
        return self.tool_registry.get_openai_tools()
    
    async def think(self, user_message: str, conversation_history: List[Dict] = None) -> str:
        """Process user message using true ReACT loop with function calling.
        
        Args:
            user_message: Message from the user
            conversation_history: Optional conversation history
            
        Returns:
            Agent's response
        """
        if conversation_history is None:
            conversation_history = []
        
        agent_logger.info(f"\n{'='*80}\nSTARTING ReACT LOOP for user {self.memory_manager.user_id}\nUser Message: {user_message}\n{'='*80}")
        
        # Load recent short-term memory
        short_term_memory = await self.memory_manager.get_recent_memory(days=3)
        agent_logger.debug(f"Short-term memory loaded: {len(short_term_memory)} characters")
        
        # Load long-term memory
        long_term_memory = await self.memory_manager.get_long_term_memory()
        agent_logger.debug(f"Long-term memory loaded: {len(long_term_memory)} characters")
        
        # Get skills
        skills_prompt = self.skills_manager.skills_to_prompt()
        
        # Build system prompt
        system_prompt = self._build_system_prompt(short_term_memory, long_term_memory, skills_prompt)
        
        # Initialize messages
        messages = [
            {"role": "system", "content": system_prompt}
        ]
        
        # Add conversation history (limited)
        messages.extend(conversation_history[-6:])
        
        # Add current user message
        messages.append({"role": "user", "content": user_message})
        
        # Run ReACT loop with function calling
        final_response = await self._react_loop(messages)
        
        return final_response
    
    def _build_system_prompt(self, short_term_memory: str, long_term_memory: str, skills: str) -> str:
        """Build the system prompt with memory and skills.
        
        Args:
            short_term_memory: Recent conversation memory
            long_term_memory: Consolidated long-term memory
            skills: Available skills
            
        Returns:
            Complete system prompt
        """
        prompt_parts = [
            config.SYSTEM_PROMPT,
            "\n## Your Long-Term Memory\n",
            "These are important things you've learned about the user over time:\n",
            long_term_memory[:config.MAX_MEMORY_TOKENS // 2],
            "\n## Your Recent Memory (Last 3 Days - TRUNCATED!)\n",
            "⚠️ Note: This is only a summary. For complete information, use search tools!\n",
            short_term_memory[:config.MAX_MEMORY_TOKENS // 2],
            "\n## Your Skills\n",
            skills,
            "\n## Memory Search Tools\n",
            "You have access to powerful memory search functions that let you find information from ALL past conversations.",
            "When a user asks about something they told you before (birthdays, names, preferences, etc.),",
            "you MUST use the search functions to look it up. The memory shown above is truncated!",
            "\nAvailable functions:",
            "- search_memory_grep: Search for keywords across all memory",
            "- search_recent_mentions: Find recent mentions of a topic",
            "- read_memory_file: Read a complete memory file",
            "- list_memory_files: See what files are available",
            "- get_memory_summary: Get an overview of memory",
            "- save_important_fact: Save important information to long-term memory",
            "- create_new_skill: Learn a new capability",
            "\n🔥 CRITICAL RULES:",
            "1. If user asks about personal information (birthdays, names, past conversations), you MUST call a search function BEFORE saying you don't have the information!",
            "2. When user shares NEW important information (birthdays, family members, preferences, goals), you MUST use save_important_fact to store it!",
            "3. Examples of information to save:",
            "   - Birthdays and important dates",
            "   - Family members and relationships",
            "   - Personal preferences (favorite foods, colors, activities)",
            "   - Goals and projects they're working on",
            "   - Important facts about their life",
            "\n🧠 LEARNING NEW SKILLS:",
            "You can create new skills when:",
            "1. You discover a new way to solve a problem that would be useful in the future",
            "2. The user teaches you a new capability or workflow",
            "3. You need a specialized tool or process you'll use repeatedly",
            "4. You want to remember a complex multi-step procedure",
            "\nThink of skills as your toolbox - add tools that make you more capable!",
        ]
        
        return "\n".join(prompt_parts)
    
    async def _react_loop(self, messages: List[Dict]) -> str:
        """Execute the ReACT loop with function calling.
        
        Args:
            messages: Conversation messages
            
        Returns:
            Final response
        """
        iteration = 0
        tools = self._get_tools_definition()
        
        agent_logger.info(f"Entering ReACT loop with max_iterations={self.max_iterations}, {len(tools)} tools available")
        
        while iteration < self.max_iterations:
            iteration += 1
            agent_logger.info(f"\n{'='*60}\nREACT ITERATION {iteration}/{self.max_iterations}\n{'='*60}")
            
            try:
                # Call OpenAI with tools
                api_logger.debug(f"Making OpenAI API call with model={config.OPENAI_MODEL}, messages={len(messages)}, tools={len(tools)}")
                response = await self.client.chat.completions.create(
                    model=config.OPENAI_MODEL,
                    messages=messages,
                    tools=tools,
                    tool_choice="auto"  # Let the model decide when to use tools
                )
                
                message = response.choices[0].message
                
                # Log token usage
                if hasattr(response, 'usage'):
                    api_logger.info(f"OpenAI API usage - Prompt: {response.usage.prompt_tokens}, Completion: {response.usage.completion_tokens}, Total: {response.usage.total_tokens}")
                
                # Check if the model wants to call functions
                if message.tool_calls:
                    agent_logger.info(f"[TOOL CALLS REQUESTED] {len(message.tool_calls)} function(s)")
                    
                    # Add assistant message with tool calls to history
                    messages.append(message)
                    
                    # Execute each tool call
                    for tool_call in message.tool_calls:
                        function_name = tool_call.function.name
                        function_args = json.loads(tool_call.function.arguments)
                        
                        agent_logger.info(f"[EXECUTING] {function_name}({json.dumps(function_args, indent=2)})")
                        tools_logger.info(f"Tool execution started: {function_name} with args: {function_args}")
                        
                        # Execute the function
                        result = await self._execute_function(function_name, function_args)
                        
                        agent_logger.info(f"[RESULT] {result[:200]}..." if len(result) > 200 else f"[RESULT] {result}")
                        tools_logger.info(f"Tool execution completed: {function_name}, result length: {len(result)} chars")
                        
                        # Add function result to messages
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": function_name,
                            "content": result
                        })
                    
                    # Continue loop to get the next response from the model
                    continue
                
                # No tool calls, this is the final answer
                if message.content:
                    agent_logger.info(f"\n[FINAL ANSWER]\n{message.content[:500]}{'...' if len(message.content) > 500 else ''}")
                    return message.content
                else:
                    agent_logger.warning("Model returned empty content without tool calls")
                    return "I apologize, I'm having trouble formulating a response."
                
            except Exception as e:
                error_msg = f"I apologize, but I encountered an error: {str(e)}"
                agent_logger.error(f"Error in ReACT loop iteration {iteration}: {e}", exc_info=True)
                return error_msg
        
        # Max iterations reached
        agent_logger.warning(f"Max iterations ({self.max_iterations}) reached!")
        return "I've thought about this extensively. Let me give you my best answer based on what I know."
    
    async def _execute_function(self, function_name: str, arguments: Dict) -> str:
        """Execute a tool function via the tool registry.
        
        Args:
            function_name: Name of the function to execute
            arguments: Function arguments
            
        Returns:
            Function result as string
        """
        return await self.tool_registry.execute(function_name, arguments)
    
    async def chat(self, user_message: str, conversation_history: List[Dict] = None) -> str:
        """Chat interface.
        
        Args:
            user_message: Message from user
            conversation_history: Optional conversation history
            
        Returns:
            Assistant response
        """
        return await self.think(user_message, conversation_history)
