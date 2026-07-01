"""Enhanced Skills system with dynamic tool loading.

Skills are loaded from the skills/ directory. Each skill folder can contain:
- A .md file describing the skill (for LLM context)
- A tools.py file defining SkillTool classes (for function calling)
- Other Python files for implementation logic
"""
import aiofiles
from pathlib import Path
from typing import List, Dict, Optional, Callable, Any, TYPE_CHECKING
import re
import importlib.util
import importlib
import inspect
import sys
from src.core import config
from src.core.logging_config import get_skills_logger
from src.core.skill_tool import SkillTool, get_skill_tools

# Get skills logger
skills_logger = get_skills_logger()


class Skill:
    """Represents a single agent skill with its description and tools."""
    
    def __init__(
        self, 
        name: str, 
        description: str, 
        usage: str, 
        examples: str = "",
        folder_path: Optional[Path] = None,
        tools: Optional[List[SkillTool]] = None
    ):
        """Initialize a skill.
        
        Args:
            name: Name of the skill
            description: What the skill does
            usage: How to use the skill
            examples: Example usage (optional)
            folder_path: Path to the skill folder
            tools: List of SkillTool instances
        """
        self.name = name
        self.description = description
        self.usage = usage
        self.examples = examples
        self.folder_path = folder_path
        self.tools: List[SkillTool] = tools or []
        self._tools_loaded = False
    
    def to_prompt_format(self) -> str:
        """Convert skill to a format suitable for LLM prompt."""
        parts = [
            f"**{self.name}**",
            f"Description: {self.description}",
            f"Usage: {self.usage}"
        ]
        
        if self.examples:
            parts.append(f"Examples:\n{self.examples}")
        
        # List available tools
        if self.tools:
            tool_names = [t.name for t in self.tools]
            parts.append(f"Tools: {', '.join(tool_names)}")
        
        return "\n".join(parts)
    
    def get_tool_names(self) -> List[str]:
        """Get list of tool names provided by this skill."""
        return [tool.name for tool in self.tools]
    
    def get_openai_tools(self) -> List[Dict[str, Any]]:
        """Get all tools in OpenAI function calling format."""
        return [tool.to_openai_tool() for tool in self.tools]
    
    def __str__(self) -> str:
        return f"Skill({self.name}, tools={len(self.tools)})"
    
    def __repr__(self) -> str:
        return self.__str__()


class SkillsManager:
    """Manages loading and accessing agent skills with dynamic tool loading."""
    
    def __init__(self):
        """Initialize the skills manager."""
        self.skills: Dict[str, Skill] = {}
        self.skills_dir = config.SKILLS_DIR
        self.skills_dir.mkdir(exist_ok=True)
        self._all_tools: Dict[str, SkillTool] = {}  # tool_name -> SkillTool
        self._tool_to_skill: Dict[str, str] = {}    # tool_name -> skill_name
    
    async def load_skills(self):
        """Load all skills from the skills directory."""
        self.skills.clear()
        self._all_tools.clear()
        self._tool_to_skill.clear()
        
        # Look for skill folders (directories containing .md files)
        skill_folders = [d for d in self.skills_dir.iterdir() if d.is_dir()]
        
        for skill_folder in skill_folders:
            try:
                skill = await self._load_skill_from_folder(skill_folder)
                if skill:
                    self.skills[skill.name] = skill
                    
                    # Index all tools
                    for tool in skill.tools:
                        self._all_tools[tool.name] = tool
                        self._tool_to_skill[tool.name] = skill.name
                    
                    tools_count = len(skill.tools)
                    skills_logger.info(f"Loaded skill: {skill.name} from {skill_folder.name} with {tools_count} tools")
            except Exception as e:
                skills_logger.error(f"Error loading skill from {skill_folder}: {e}", exc_info=True)
        
        skills_logger.info(f"Total skills loaded: {len(self.skills)}, Total tools: {len(self._all_tools)}")
    
    async def _load_skill_from_folder(self, folder_path: Path) -> Optional[Skill]:
        """Load a skill from a folder containing .md file and optional tools.py.
        
        Args:
            folder_path: Path to the skill folder
            
        Returns:
            Loaded Skill object or None if loading failed
        """
        # Find the main .md file
        md_files = list(folder_path.glob("*.md"))
        
        # Skip README.md and similar
        md_files = [f for f in md_files if f.name.lower() not in ['readme.md', 'quickstart.md']]
        
        if not md_files:
            skills_logger.warning(f"No skill .md file found in: {folder_path}")
            return None
        
        # Use the first .md file found
        md_file = md_files[0]
        
        # Parse the skill definition
        skill = await self._parse_skill_file(md_file)
        skill.folder_path = folder_path
        
        # Load tools from tools.py if it exists
        skill.tools = await self._load_skill_tools(folder_path)
        
        return skill
    
    async def _load_skill_tools(self, folder_path: Path) -> List[SkillTool]:
        """Load SkillTool classes from a skill's tools.py file.
        
        Args:
            folder_path: Path to the skill folder
            
        Returns:
            List of SkillTool instances
        """
        tools_file = folder_path / "tools.py"
        
        if not tools_file.exists():
            skills_logger.debug(f"No tools.py found in {folder_path}")
            return []
        
        try:
            # Create a unique module name
            module_name = f"skills_tools_{folder_path.name}"
            
            # Load the module dynamically
            spec = importlib.util.spec_from_file_location(module_name, tools_file)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                
                # Add the skill folder to sys.path temporarily for relative imports
                skill_parent = str(folder_path.parent)
                if skill_parent not in sys.path:
                    sys.path.insert(0, skill_parent)
                
                try:
                    spec.loader.exec_module(module)
                finally:
                    # Clean up sys.path
                    if skill_parent in sys.path:
                        sys.path.remove(skill_parent)
                
                # Extract SkillTool classes
                tools = get_skill_tools(module)
                skills_logger.debug(f"Loaded {len(tools)} tools from {tools_file}")
                return tools
                
        except Exception as e:
            skills_logger.error(f"Error loading tools from {tools_file}: {e}", exc_info=True)
        
        return []
    
    async def _parse_skill_file(self, file_path: Path) -> Skill:
        """Parse a skill markdown file.
        
        Expected format:
        # Skill Name
        
        ## Description
        What the skill does
        
        ## Usage
        How to use it
        
        ## Examples (optional)
        Example usage
        """
        async with aiofiles.open(file_path, 'r') as f:
            content = await f.read()
        
        # Extract skill name from first heading
        name_match = re.search(r'^#\s+(.+?)$', content, re.MULTILINE)
        name = name_match.group(1).strip() if name_match else file_path.stem
        
        # Extract description
        desc_match = re.search(r'##\s+Description\s*\n+(.*?)(?=\n##|\Z)', content, re.DOTALL | re.IGNORECASE)
        description = desc_match.group(1).strip() if desc_match else ""
        
        # Extract usage
        usage_match = re.search(r'##\s+Usage\s*\n+(.*?)(?=\n##|\Z)', content, re.DOTALL | re.IGNORECASE)
        usage = usage_match.group(1).strip() if usage_match else ""
        
        # Extract examples (optional)
        examples_match = re.search(r'##\s+Examples?\s*\n+(.*?)(?=\n##|\Z)', content, re.DOTALL | re.IGNORECASE)
        examples = examples_match.group(1).strip() if examples_match else ""
        
        return Skill(name, description, usage, examples)
    
    def get_all_skills(self) -> List[Skill]:
        """Get list of all loaded skills."""
        return list(self.skills.values())
    
    def get_skill(self, name: str) -> Optional[Skill]:
        """Get a specific skill by name."""
        return self.skills.get(name)
    
    def get_skill_for_tool(self, tool_name: str) -> Optional[Skill]:
        """Get the skill that provides a specific tool."""
        skill_name = self._tool_to_skill.get(tool_name)
        if skill_name:
            return self.skills.get(skill_name)
        return None
    
    def get_all_tools(self) -> Dict[str, SkillTool]:
        """Get all tools from all skills."""
        return self._all_tools.copy()
    
    def get_tool(self, tool_name: str) -> Optional[SkillTool]:
        """Get a specific tool by name."""
        return self._all_tools.get(tool_name)
    
    def get_openai_tools(self) -> List[Dict[str, Any]]:
        """Get all tools in OpenAI function calling format."""
        return [tool.to_openai_tool() for tool in self._all_tools.values()]
    
    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Execute a skill tool by name.
        
        Args:
            tool_name: Name of the tool to execute
            arguments: Arguments to pass to the tool
            
        Returns:
            Tool execution result as string
        """
        tool = self._all_tools.get(tool_name)
        
        if tool is None:
            return f"Unknown tool: {tool_name}"
        
        try:
            result = await tool.execute(**arguments)
            return result
        except Exception as e:
            skills_logger.error(f"Error executing tool {tool_name}: {e}", exc_info=True)
            return f"Error executing {tool_name}: {str(e)}"
    
    def skills_to_prompt(self) -> str:
        """Convert all skills to a formatted prompt string."""
        if not self.skills:
            return "No skills available."
        
        skills_text = ["# Available Skills\n"]
        
        for skill in self.skills.values():
            skills_text.append(skill.to_prompt_format())
            skills_text.append("\n---\n")
        
        return "\n".join(skills_text)
    
    async def reload_skills(self):
        """Reload all skills from disk."""
        await self.load_skills()
    
    async def create_skill(
        self, 
        name: str, 
        description: str, 
        usage: str, 
        examples: str = "",
        tools_code: Optional[str] = None
    ) -> Skill:
        """Create a new skill with its folder structure.
        
        Args:
            name: Name of the skill
            description: What the skill does
            usage: How to use the skill
            examples: Example usage (optional)
            tools_code: Python code for tools.py file
            
        Returns:
            Created Skill object
        """
        # Create skill folder
        skill_folder = self.skills_dir / name.lower().replace(" ", "_")
        skill_folder.mkdir(exist_ok=True)
        
        # Create the main .md file
        md_content = f"""# {name}

## Description
{description}

## Usage
{usage}
"""
        
        if examples:
            md_content += f"""
## Examples
{examples}
"""
        
        md_file = skill_folder / f"{skill_folder.name}.md"
        async with aiofiles.open(md_file, 'w') as f:
            await f.write(md_content)
        
        # Create tools.py if provided
        if tools_code:
            tool_file = skill_folder / "tools.py"
            async with aiofiles.open(tool_file, 'w') as f:
                await f.write(tools_code)
        
        # Load and register the new skill
        skill = await self._load_skill_from_folder(skill_folder)
        if skill:
            self.skills[skill.name] = skill
            # Index tools
            for tool in skill.tools:
                self._all_tools[tool.name] = tool
                self._tool_to_skill[tool.name] = skill.name
        
        return skill
