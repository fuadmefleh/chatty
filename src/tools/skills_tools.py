"""Skills-related tools for LLM function calling."""
from typing import Dict, Any, Optional
from src.core.base_tool import BaseTool
from src.core.skills import SkillsManager


class CreateNewSkillTool(BaseTool):
    """Create a new skill that can be used in future conversations."""
    
    def __init__(self, skills_manager: SkillsManager):
        super().__init__()
        self.skills_manager = skills_manager
    
    @property
    def name(self) -> str:
        return "create_new_skill"
    
    @property
    def description(self) -> str:
        return "Create a new skill that you can use in future conversations. Use this when you need a capability you don't currently have, or when you learn a new way to do something useful. Skills persist across conversations and help you improve over time."
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Name of the skill (e.g., 'Image Analysis', 'Data Visualization')"
                },
                "description": {
                    "type": "string",
                    "description": "What the skill does and when to use it"
                },
                "usage": {
                    "type": "string",
                    "description": "How to use the skill (step-by-step guidance)"
                },
                "examples": {
                    "type": "string",
                    "description": "Example use cases for this skill (optional)"
                },
                "tools_code": {
                    "type": "object",
                    "description": "Optional Python tools for this skill. Keys are tool names, values are Python code strings. Each tool should have an 'async def execute(**kwargs)' function.",
                    "additionalProperties": {
                        "type": "string"
                    }
                }
            },
            "required": ["name", "description", "usage"]
        }
    
    async def execute(
        self,
        name: str,
        description: str,
        usage: str,
        examples: Optional[str] = None,
        tools_code: Optional[Dict[str, str]] = None
    ) -> str:
        skill = await self.skills_manager.create_skill(
            name=name,
            description=description,
            usage=usage,
            examples=examples or "",
            tools_code=tools_code
        )
        return f"✅ Created new skill: '{skill.name}'. You can now use this skill in future conversations!"
