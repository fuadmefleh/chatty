"""Skills system for loading agent capabilities from markdown files."""
import aiofiles
from pathlib import Path
from typing import List, Dict, Optional, Callable
import re
import importlib.util
import inspect
from src.core import config
from src.core.logging_config import get_skills_logger

# Get skills logger
skills_logger = get_skills_logger()


class Skill:
    """Represents a single agent skill."""
    
    def __init__(self, name: str, description: str, usage: str, examples: str = "", tools: Optional[Dict[str, Callable]] = None):
        """Initialize a skill.
        
        Args:
            name: Name of the skill
            description: What the skill does
            usage: How to use the skill
            examples: Example usage (optional)
            tools: Dictionary of tool functions available to this skill
        """
        self.name = name
        self.description = description
        self.usage = usage
        self.examples = examples
        self.tools = tools or {}
    
    def to_prompt_format(self) -> str:
        """Convert skill to a format suitable for LLM prompt."""
        parts = [
            f"**{self.name}**",
            f"Description: {self.description}",
            f"Usage: {self.usage}"
        ]
        
        if self.examples:
            parts.append(f"Examples:\n{self.examples}")
        
        return "\n".join(parts)
    
    def __str__(self) -> str:
        return f"Skill({self.name})"
    
    def __repr__(self) -> str:
        return self.__str__()


class SkillsManager:
    """Manages loading and accessing agent skills from markdown files."""
    
    def __init__(self):
        """Initialize the skills manager."""
        self.skills: Dict[str, Skill] = {}
        self.skills_dir = config.SKILLS_DIR
        self.skills_dir.mkdir(exist_ok=True)
    
    async def load_skills(self):
        """Load all skills from the skills directory."""
        self.skills.clear()
        
        # Look for skill folders (directories containing .md files)
        skill_folders = [d for d in self.skills_dir.iterdir() if d.is_dir()]
        
        for skill_folder in skill_folders:
            try:
                skill = await self._load_skill_from_folder(skill_folder)
                if skill:
                    self.skills[skill.name] = skill
                    skills_logger.info(f"Loaded skill: {skill.name} from {skill_folder.name}")
            except Exception as e:
                skills_logger.error(f"Error loading skill from {skill_folder}: {e}", exc_info=True)
    
    async def _load_skill_from_folder(self, folder_path: Path) -> Optional[Skill]:
        """Load a skill from a folder containing .md file and optional .py tools.
        
        Args:
            folder_path: Path to the skill folder
            
        Returns:
            Loaded Skill object or None if loading failed
        """
        # Find the main .md file (should have same name as folder or be the only .md)
        md_files = list(folder_path.glob("*.md"))
        
        if not md_files:
            skills_logger.warning(f"No .md file found in skill folder: {folder_path}")
            return None
        
        # Use the first .md file found
        md_file = md_files[0]
        
        # Parse the skill definition
        skill = await self._parse_skill_file(md_file)
        
        # Load Python tools from the folder
        skill.tools = await self._load_skill_tools(folder_path)
        
        return skill
    
    async def _load_skill_tools(self, folder_path: Path) -> Dict[str, Callable]:
        """Load Python tool scripts from a skill folder.
        
        Args:
            folder_path: Path to the skill folder
            
        Returns:
            Dictionary mapping tool names to callable functions
        """
        tools = {}
        
        # Find all .py files in the folder
        py_files = [f for f in folder_path.glob("*.py") if f.name != "__init__.py"]
        
        for py_file in py_files:
            try:
                # Load the module dynamically
                spec = importlib.util.spec_from_file_location(
                    f"skill_tool_{folder_path.name}_{py_file.stem}",
                    py_file
                )
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    
                    # Look for an 'execute' function or any async function
                    if hasattr(module, 'execute'):
                        tools[py_file.stem] = module.execute
                    else:
                        # Find all async functions in the module
                        for name, obj in inspect.getmembers(module):
                            if inspect.iscoroutinefunction(obj) and not name.startswith('_'):
                                tools[name] = obj
                                
            except Exception as e:
                skills_logger.error(f"Error loading tool from {py_file}: {e}", exc_info=True)
        
        return tools
    
    async def _parse_skill_file(self, file_path: Path) -> Optional[Skill]:
        """Parse a skill markdown file.
        
        Expected format:
        # Skill Name
        
        ## Description
        What the skill does
        
        ## Usage
        How to use it
        
        ## Examples (optional)
        Example usage
        
        Args:
            file_path: Path to the skill markdown file
            
        Returns:
            Parsed Skill object
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
    
    def get_skill(self, name: str) -> Skill:
        """Get a specific skill by name."""
        return self.skills.get(name)
    
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
    async def create_skill(self, name: str, description: str, usage: str, 
                          examples: str = "", tools_code: Optional[Dict[str, str]] = None) -> Skill:
        """Create a new skill with its folder structure.
        
        Args:
            name: Name of the skill
            description: What the skill does
            usage: How to use the skill
            examples: Example usage (optional)
            tools_code: Dictionary of tool_name -> Python code for tool scripts
            
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
        
        # Create tool files if provided
        if tools_code:
            for tool_name, code in tools_code.items():
                tool_file = skill_folder / f"{tool_name}.py"
                async with aiofiles.open(tool_file, 'w') as f:
                    await f.write(code)
        
        # Load and return the new skill
        skill = await self._load_skill_from_folder(skill_folder)
        if skill:
            self.skills[skill.name] = skill
        
        return skill