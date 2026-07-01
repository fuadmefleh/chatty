"""Core tools package - Only memory tools remain here.

Skill-specific tools are now defined in their respective skill folders
(e.g., skills/walmart_orders/tools.py) and are loaded dynamically
by the SkillsManager.

This keeps src/ lean with only framework code.
"""
from src.core.tool_registry import ToolRegistry
from src.core.memory_tools import MemoryTools
from src.core.skills_manager import SkillsManager

# Import only memory tool classes (core framework tools)
from src.tools.memory_tools import (
    SearchMemoryGrepTool,
    SearchRecentMentionsTool,
    ReadMemoryFileTool,
    ListMemoryFilesTool,
    GetMemorySummaryTool,
    SaveImportantFactTool
)
from src.tools.skills_tools import CreateNewSkillTool


def create_core_tool_registry(memory_tools: MemoryTools, skills_manager: SkillsManager) -> ToolRegistry:
    """Create tool registry with only CORE tools (memory and skill management).
    
    Skill-specific tools are loaded dynamically via SkillsManager.
    
    Args:
        memory_tools: MemoryTools instance for memory-related tools
        skills_manager: SkillsManager instance for skill management
        
    Returns:
        Populated ToolRegistry with core tools only
    """
    registry = ToolRegistry()
    
    # Register memory tools (core framework tools)
    registry.register_multiple([
        SearchMemoryGrepTool(memory_tools),
        SearchRecentMentionsTool(memory_tools),
        ReadMemoryFileTool(memory_tools),
        ListMemoryFilesTool(memory_tools),
        GetMemorySummaryTool(memory_tools),
        SaveImportantFactTool(memory_tools)
    ])
    
    # Register skill management tool
    registry.register(CreateNewSkillTool(skills_manager))
    
    return registry


__all__ = [
    'ToolRegistry',
    'create_core_tool_registry',
    'SearchMemoryGrepTool',
    'SearchRecentMentionsTool',
    'ReadMemoryFileTool',
    'ListMemoryFilesTool',
    'GetMemorySummaryTool',
    'SaveImportantFactTool',
    'CreateNewSkillTool'
]
