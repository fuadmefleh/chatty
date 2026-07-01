"""Tool registry for managing and executing LLM tools."""
from typing import Dict, List, Any, Optional
from src.core.base_tool import BaseTool
from src.core.logging_config import get_tools_logger

# Get tools logger
tools_logger = get_tools_logger()


class ToolRegistry:
    """Registry for managing tools that can be called by the LLM."""
    
    def __init__(self):
        """Initialize the tool registry."""
        self._tools: Dict[str, BaseTool] = {}
        tools_logger.info("Tool registry initialized")
    
    def register(self, tool: BaseTool) -> None:
        """Register a tool.
        
        Args:
            tool: Tool instance to register
        """
        if tool.name in self._tools:
            tools_logger.warning(f"Tool '{tool.name}' is already registered. Overwriting.")
        
        self._tools[tool.name] = tool
        tools_logger.debug(f"Registered tool: {tool.name}")
    
    def register_multiple(self, tools: List[BaseTool]) -> None:
        """Register multiple tools at once.
        
        Args:
            tools: List of tool instances to register
        """
        for tool in tools:
            self.register(tool)
    
    def unregister(self, tool_name: str) -> None:
        """Unregister a tool.
        
        Args:
            tool_name: Name of the tool to unregister
        """
        if tool_name in self._tools:
            del self._tools[tool_name]
            tools_logger.info(f"Unregistered tool: {tool_name}")
        else:
            tools_logger.warning(f"Attempted to unregister unknown tool: {tool_name}")
    
    def get_tool(self, tool_name: str) -> Optional[BaseTool]:
        """Get a tool by name.
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            Tool instance or None if not found
        """
        return self._tools.get(tool_name)
    
    def list_tools(self) -> List[str]:
        """List all registered tool names.
        
        Returns:
            List of tool names
        """
        return list(self._tools.keys())
    
    def get_openai_tools(self) -> List[Dict[str, Any]]:
        """Get all tools in OpenAI function calling format.
        
        Returns:
            List of tool definitions for OpenAI API
        """
        return [tool.to_openai_tool() for tool in self._tools.values()]
    
    async def execute(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Execute a tool by name.
        
        Args:
            tool_name: Name of the tool to execute
            arguments: Arguments to pass to the tool
            
        Returns:
            Tool execution result as string
            
        Raises:
            ValueError: If tool is not found
        """
        tool = self.get_tool(tool_name)
        
        if tool is None:
            error_msg = f"Unknown tool: {tool_name}"
            tools_logger.error(error_msg)
            return error_msg
        
        try:
            tools_logger.debug(f"Executing tool '{tool_name}' with args: {arguments}")
            result = await tool.execute(**arguments)
            tools_logger.debug(f"Tool '{tool_name}' completed successfully, result length: {len(result)} chars")
            return result
        except Exception as e:
            error_msg = f"Error executing {tool_name}: {str(e)}"
            tools_logger.error(error_msg, exc_info=True)
            return error_msg
    
    def __len__(self) -> int:
        """Return the number of registered tools."""
        return len(self._tools)
    
    def __contains__(self, tool_name: str) -> bool:
        """Check if a tool is registered."""
        return tool_name in self._tools
