# Tool Architecture

## Overview

The project uses a modular, plugin-based architecture for LLM tool calling. Tools are decoupled from the ReACT agent, making the system more maintainable and extensible.

## Architecture Components

### 1. Base Tool Interface (`src/core/base_tool.py`)

All tools inherit from `BaseTool`, which defines the standard interface:

```python
from src.core.base_tool import BaseTool

class MyCustomTool(BaseTool):
    @property
    def name(self) -> str:
        return "my_tool_name"
    
    @property
    def description(self) -> str:
        return "What this tool does"
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "param1": {
                    "type": "string",
                    "description": "First parameter"
                }
            },
            "required": ["param1"]
        }
    
    async def execute(self, param1: str) -> str:
        # Tool implementation
        return f"Result: {param1}"
```

### 2. Tool Registry (`src/core/tool_registry.py`)

The `ToolRegistry` manages all available tools:

- **Register tools**: Add tools to the registry
- **Convert to OpenAI format**: Automatically converts tools to OpenAI function calling format
- **Execute tools**: Generic execution with error handling

```python
from src.core.tool_registry import ToolRegistry

registry = ToolRegistry()
registry.register(MyCustomTool())

# Get OpenAI-compatible tool definitions
tools = registry.get_openai_tools()

# Execute a tool
result = await registry.execute("my_tool_name", {"param1": "value"})
```

### 3. Tool Modules (`src/tools/`)

Tools are organized into modules by functionality:

- **`memory_tools.py`**: Memory search and management tools
- **`walmart_tools.py`**: Walmart order query tools
- **`skills_tools.py`**: Skill creation and management tools

Each module contains tool classes that inherit from `BaseTool`.

### 4. Tool Factory (`src/tools/__init__.py`)

The `create_tool_registry()` function creates a fully-configured registry:

```python
from src.tools import create_tool_registry

registry = create_tool_registry(memory_tools, skills_manager)
```

### 5. ReACT Agent (`src/agents/react_agent.py`)

The agent now delegates tool management to the registry:

```python
def __init__(self, memory_manager, skills_manager):
    self.tool_registry = create_tool_registry(
        MemoryTools(memory_manager.user_id),
        skills_manager
    )

def _get_tools_definition(self):
    return self.tool_registry.get_openai_tools()

async def _execute_function(self, function_name, arguments):
    return await self.tool_registry.execute(function_name, arguments)
```

## Adding New Tools

### Step 1: Create Tool Class

Create a new file in `src/tools/` or add to an existing module:

```python
from src.core.base_tool import BaseTool

class MyNewTool(BaseTool):
    def __init__(self, some_dependency):
        super().__init__()
        self.dependency = some_dependency
    
    @property
    def name(self) -> str:
        return "my_new_tool"
    
    @property
    def description(self) -> str:
        return "Description for the LLM"
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "arg1": {"type": "string", "description": "..."}
            },
            "required": ["arg1"]
        }
    
    async def execute(self, arg1: str) -> str:
        # Implementation
        return "result"
```

### Step 2: Register Tool

Add to `src/tools/__init__.py`:

```python
from src.tools.my_module import MyNewTool

def create_tool_registry(memory_tools, skills_manager):
    registry = ToolRegistry()
    
    # ... existing tools ...
    
    # Add your new tool
    registry.register(MyNewTool(some_dependency))
    
    return registry
```

That's it! The agent will automatically discover and use the new tool.

## Benefits

1. **Separation of Concerns**: Tools are independent of the agent
2. **Testability**: Each tool can be tested in isolation
3. **Extensibility**: Easy to add new tools without modifying the agent
4. **Reusability**: Tools can be used by multiple agents or contexts
5. **Type Safety**: Strong typing with Python type hints
6. **Error Handling**: Centralized error handling in the registry

## Tool Categories

### Memory Tools
- `search_memory_grep`: Search all memory with grep
- `search_recent_mentions`: Find recent topic mentions
- `read_memory_file`: Read complete memory files
- `list_memory_files`: List available memory files
- `get_memory_summary`: Get memory overview
- `save_important_fact`: Save to long-term memory

### Walmart Tools
- `get_monthly_walmart_spending`: Monthly spending totals
- `get_recent_walmart_orders`: Recent order history
- `search_walmart_items`: Search purchased items

### Skills Tools
- `create_new_skill`: Create new capabilities

## Future Enhancements

- **Dynamic tool loading**: Load tools from configuration files
- **Tool versioning**: Support multiple versions of the same tool
- **Tool permissions**: Control which tools are available in different contexts
- **Tool analytics**: Track tool usage and performance
- **Tool composition**: Combine multiple tools into workflows
