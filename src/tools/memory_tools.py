"""Memory-related tools for LLM function calling."""
from typing import Dict, Any
from src.core.base_tool import BaseTool
from src.core.memory_tools import MemoryTools


class SearchMemoryGrepTool(BaseTool):
    """Search all memory files for a specific term using grep."""
    
    def __init__(self, memory_tools: MemoryTools):
        super().__init__()
        self.memory_tools = memory_tools
    
    @property
    def name(self) -> str:
        return "search_memory_grep"
    
    @property
    def description(self) -> str:
        return "Search all memory files for a specific term using grep. Use this when user asks about past conversations, birthdays, names, or anything they mentioned before."
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "search_term": {
                    "type": "string",
                    "description": "The term to search for (e.g., 'Maliha', 'birthday', 'pizza')"
                },
                "context_lines": {
                    "type": "integer",
                    "description": "Number of lines before/after match to show (default: 2)",
                    "default": 2
                }
            },
            "required": ["search_term"]
        }
    
    async def execute(self, search_term: str, context_lines: int = 2) -> str:
        return await self.memory_tools.search_memory_grep(search_term, context_lines)


class SearchRecentMentionsTool(BaseTool):
    """Find recent mentions of a topic in the last N days of conversations."""
    
    def __init__(self, memory_tools: MemoryTools):
        super().__init__()
        self.memory_tools = memory_tools
    
    @property
    def name(self) -> str:
        return "search_recent_mentions"
    
    @property
    def description(self) -> str:
        return "Find recent mentions of a topic in the last N days of conversations."
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "Topic to search for"
                },
                "days": {
                    "type": "integer",
                    "description": "Number of recent days to search (default: 7)",
                    "default": 7
                }
            },
            "required": ["topic"]
        }
    
    async def execute(self, topic: str, days: int = 7) -> str:
        return await self.memory_tools.search_recent_mentions(topic, days)


class ReadMemoryFileTool(BaseTool):
    """Read the complete content of a specific memory file."""
    
    def __init__(self, memory_tools: MemoryTools):
        super().__init__()
        self.memory_tools = memory_tools
    
    @property
    def name(self) -> str:
        return "read_memory_file"
    
    @property
    def description(self) -> str:
        return "Read the complete content of a specific memory file."
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "Name of the file (e.g., '2026-01-30.md')"
                },
                "memory_type": {
                    "type": "string",
                    "enum": ["short_term", "long_term"],
                    "description": "Type of memory file",
                    "default": "short_term"
                }
            },
            "required": ["filename"]
        }
    
    async def execute(self, filename: str, memory_type: str = "short_term") -> str:
        return await self.memory_tools.read_memory_file(filename, memory_type)


class ListMemoryFilesTool(BaseTool):
    """List all available memory files."""
    
    def __init__(self, memory_tools: MemoryTools):
        super().__init__()
        self.memory_tools = memory_tools
    
    @property
    def name(self) -> str:
        return "list_memory_files"
    
    @property
    def description(self) -> str:
        return "List all available memory files."
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "memory_type": {
                    "type": "string",
                    "enum": ["short_term", "long_term", "all"],
                    "description": "Type of memory to list",
                    "default": "all"
                }
            },
            "required": []
        }
    
    async def execute(self, memory_type: str = "all") -> str:
        return await self.memory_tools.list_memory_files(memory_type)


class GetMemorySummaryTool(BaseTool):
    """Get an overview of available memory files and categories."""
    
    def __init__(self, memory_tools: MemoryTools):
        super().__init__()
        self.memory_tools = memory_tools
    
    @property
    def name(self) -> str:
        return "get_memory_summary"
    
    @property
    def description(self) -> str:
        return "Get an overview of available memory files and categories."
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "required": []
        }
    
    async def execute(self) -> str:
        return await self.memory_tools.get_memory_summary()


class SaveImportantFactTool(BaseTool):
    """Save important information to long-term memory."""
    
    def __init__(self, memory_tools: MemoryTools):
        super().__init__()
        self.memory_tools = memory_tools
    
    @property
    def name(self) -> str:
        return "save_important_fact"
    
    @property
    def description(self) -> str:
        return "Save important information to long-term memory. Use this when the user shares personal information, preferences, or facts they want remembered (birthdays, family, preferences, goals, etc.)."
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "enum": ["important_facts", "relationships", "personal_preferences", "goals_and_projects", "key_insights", "recurring_topics"],
                    "description": "Category to save the information to. Use 'important_facts' for birthdays, names, etc. Use 'relationships' for family/friends info."
                },
                "content": {
                    "type": "string",
                    "description": "The information to save. Be specific and include all relevant details (names, dates, etc.)"
                }
            },
            "required": ["category", "content"]
        }
    
    async def execute(self, category: str, content: str) -> str:
        return await self.memory_tools.save_important_fact(category, content)
