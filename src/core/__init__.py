"""Core modules for the atlas bot."""
from . import config
from .memory import MemoryManager
from .memory_tools import MemoryTools
from .skills import SkillsManager as LegacySkillsManager
from .skills_manager import SkillsManager  # New dynamic skills manager
from .skill_tool import SkillTool  # Base class for skill tools

__all__ = [
    "config", 
    "MemoryManager", 
    "MemoryTools", 
    "SkillsManager",
    "LegacySkillsManager",
    "SkillTool"
]
