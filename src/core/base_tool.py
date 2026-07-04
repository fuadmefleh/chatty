"""Base tool interface for LLM tool calling."""
from abc import ABC, abstractmethod
from typing import Dict, Any


class BaseTool(ABC):
    """Abstract base class for all tools that can be called by the LLM."""
    
    def __init__(self):
        """Initialize the tool."""
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Return the tool name used in function calling."""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Return a description of what the tool does."""
        pass
    
    @property
    @abstractmethod
    def parameters(self) -> Dict[str, Any]:
        """Return the JSON Schema for the tool's parameters.
        
        Returns:
            Dict containing OpenAI function calling parameter schema
        """
        pass
    
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
