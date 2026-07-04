"""Base class for skill-specific tools.

Skills define their tools by subclassing SkillTool in their own tools.py file.
The framework dynamically loads these tools when skills are activated.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List


class SkillTool(ABC):
    """Base class for tools defined within skill folders.
    
    Each skill can define multiple tools by creating a tools.py file
    that contains classes extending SkillTool.
    
    Example:
        # In skills/walmart_orders/tools.py
        from src.core.skill_tool import SkillTool
        
        class GetMonthlySpending(SkillTool):
            name = "get_monthly_walmart_spending"
            description = "Get total amount spent at Walmart for a specific month."
            
            parameters = {
                "type": "object",
                "properties": {
                    "year": {"type": "integer", "description": "Year (e.g., 2026)"},
                    "month": {"type": "integer", "description": "Month number (1-12)"}
                },
                "required": ["year", "month"]
            }
            
            async def execute(self, year: int, month: int) -> str:
                # Implementation here
                return json.dumps({"total": 150.00})
    """
    
    # Class attributes that must be defined by subclasses
    name: str = ""
    description: str = ""
    parameters: Dict[str, Any] = {"type": "object", "properties": {}, "required": []}
    
    def __init__(self):
        """Initialize the skill tool."""
        if not self.name:
            raise ValueError(f"{self.__class__.__name__} must define a 'name' attribute")
        if not self.description:
            raise ValueError(f"{self.__class__.__name__} must define a 'description' attribute")
    
    @abstractmethod
    async def execute(self, **kwargs) -> str:
        """Execute the tool with the given arguments.
        
        Args:
            **kwargs: Tool arguments as defined in the parameters schema
            
        Returns:
            Result as a string (will be sent back to the LLM)
        """
        pass
    
    def to_openai_tool(self) -> Dict[str, Any]:
        """Convert this tool to OpenAI function calling format.
        
        Returns:
            Dict in OpenAI tool format
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters
            }
        }
    
    def __str__(self) -> str:
        return f"SkillTool({self.name})"
    
    def __repr__(self) -> str:
        return self.__str__()


def get_skill_tools(module) -> List[SkillTool]:
    """Extract all SkillTool subclasses from a module.
    
    Args:
        module: Python module to inspect
        
    Returns:
        List of instantiated SkillTool objects
    """
    import inspect
    
    tools = []
    for name, obj in inspect.getmembers(module, inspect.isclass):
        if (issubclass(obj, SkillTool) and 
            obj is not SkillTool and
            hasattr(obj, 'name') and obj.name):
            try:
                tools.append(obj())
            except Exception as e:
                print(f"Warning: Could not instantiate tool {name}: {e}")
    
    return tools
