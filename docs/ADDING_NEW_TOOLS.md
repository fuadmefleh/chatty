# Example: Adding a New Tool

This example demonstrates how easy it is to add a new tool to the system.

## Scenario: Add a Weather Tool

Let's say you want to add a tool that fetches weather information.

### Step 1: Create the Tool Class

Create `src/tools/weather_tools.py`:

```python
"""Weather-related tools for LLM function calling."""
import httpx
from typing import Dict, Any
from src.core.base_tool import BaseTool


class GetCurrentWeatherTool(BaseTool):
    """Get current weather for a location."""
    
    @property
    def name(self) -> str:
        return "get_current_weather"
    
    @property
    def description(self) -> str:
        return "Get the current weather for a specific location. Use this when the user asks about weather conditions."
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "The city and state/country, e.g. 'San Francisco, CA' or 'London, UK'"
                },
                "unit": {
                    "type": "string",
                    "enum": ["celsius", "fahrenheit"],
                    "description": "Temperature unit (default: celsius)",
                    "default": "celsius"
                }
            },
            "required": ["location"]
        }
    
    async def execute(self, location: str, unit: str = "celsius") -> str:
        """Fetch weather data from an API."""
        # In a real implementation, you'd call a weather API
        # For this example, we'll return mock data
        
        # Example with a real API:
        # async with httpx.AsyncClient() as client:
        #     response = await client.get(
        #         "https://api.openweathermap.org/data/2.5/weather",
        #         params={"q": location, "units": "metric" if unit == "celsius" else "imperial"}
        #     )
        #     data = response.json()
        #     return f"Temperature in {location}: {data['main']['temp']}°{unit[0].upper()}"
        
        return f"Current weather in {location}: 22°{unit[0].upper()}, partly cloudy"


class GetWeatherForecastTool(BaseTool):
    """Get weather forecast for the next few days."""
    
    @property
    def name(self) -> str:
        return "get_weather_forecast"
    
    @property
    def description(self) -> str:
        return "Get the weather forecast for the next 5 days for a specific location."
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "The city and state/country"
                },
                "days": {
                    "type": "integer",
                    "description": "Number of days to forecast (1-5, default: 3)",
                    "minimum": 1,
                    "maximum": 5,
                    "default": 3
                }
            },
            "required": ["location"]
        }
    
    async def execute(self, location: str, days: int = 3) -> str:
        """Fetch weather forecast."""
        # Mock implementation
        forecast = []
        for i in range(days):
            forecast.append(f"Day {i+1}: 20-25°C, sunny")
        
        return f"Weather forecast for {location}:\n" + "\n".join(forecast)
```

### Step 2: Register the Tools

Update `src/tools/__init__.py`:

```python
"""Tools package - LLM function calling tools."""
from src.core.tool_registry import ToolRegistry
from src.core.memory_tools import MemoryTools
from src.core.skills import SkillsManager

# Import all tool classes
from src.tools.memory_tools import (
    SearchMemoryGrepTool,
    SearchRecentMentionsTool,
    ReadMemoryFileTool,
    ListMemoryFilesTool,
    GetMemorySummaryTool,
    SaveImportantFactTool
)
from src.tools.walmart_tools import (
    GetMonthlyWalmartSpendingTool,
    GetRecentWalmartOrdersTool,
    SearchWalmartItemsTool
)
from src.tools.skills_tools import CreateNewSkillTool
from src.tools.weather_tools import (  # ← ADD THIS
    GetCurrentWeatherTool,
    GetWeatherForecastTool
)


def create_tool_registry(memory_tools: MemoryTools, skills_manager: SkillsManager) -> ToolRegistry:
    """Create and populate a tool registry with all available tools."""
    registry = ToolRegistry()
    
    # Register memory tools
    registry.register_multiple([
        SearchMemoryGrepTool(memory_tools),
        SearchRecentMentionsTool(memory_tools),
        ReadMemoryFileTool(memory_tools),
        ListMemoryFilesTool(memory_tools),
        GetMemorySummaryTool(memory_tools),
        SaveImportantFactTool(memory_tools)
    ])
    
    # Register Walmart tools
    registry.register_multiple([
        GetMonthlyWalmartSpendingTool(),
        GetRecentWalmartOrdersTool(),
        SearchWalmartItemsTool()
    ])
    
    # Register skills tools
    registry.register(CreateNewSkillTool(skills_manager))
    
    # Register weather tools  ← ADD THIS
    registry.register_multiple([
        GetCurrentWeatherTool(),
        GetWeatherForecastTool()
    ])
    
    return registry


__all__ = [
    'ToolRegistry',
    'create_tool_registry',
    # ... existing exports ...
    'GetCurrentWeatherTool',  # ← ADD THIS
    'GetWeatherForecastTool'  # ← ADD THIS
]
```

### Step 3: Done!

That's it! The agent now automatically has access to weather tools. When the user asks "What's the weather in London?", the LLM will:

1. See the `get_current_weather` tool in its available functions
2. Decide to call it with `{"location": "London, UK"}`
3. The `ToolRegistry` will execute `GetCurrentWeatherTool.execute(location="London, UK")`
4. The result is returned to the LLM
5. The LLM formulates a natural response to the user

## Testing Your New Tool

Create `tests/test_weather_tools.py`:

```python
"""Tests for weather tools."""
import pytest
from src.tools.weather_tools import GetCurrentWeatherTool, GetWeatherForecastTool


@pytest.mark.asyncio
async def test_get_current_weather():
    """Test current weather tool."""
    tool = GetCurrentWeatherTool()
    
    # Test the tool interface
    assert tool.name == "get_current_weather"
    assert "weather" in tool.description.lower()
    assert "location" in tool.parameters["properties"]
    
    # Test execution
    result = await tool.execute(location="London, UK")
    assert "London" in result
    assert "°" in result


@pytest.mark.asyncio
async def test_get_weather_forecast():
    """Test weather forecast tool."""
    tool = GetWeatherForecastTool()
    
    # Test execution
    result = await tool.execute(location="Paris, France", days=3)
    assert "Paris" in result
    assert "Day 1" in result
    assert "Day 3" in result


@pytest.mark.asyncio
async def test_weather_tool_in_registry():
    """Test that weather tools work in the registry."""
    from src.core.tool_registry import ToolRegistry
    
    registry = ToolRegistry()
    registry.register(GetCurrentWeatherTool())
    
    # Tool is discoverable
    assert "get_current_weather" in registry
    
    # Tool can be executed via registry
    result = await registry.execute("get_current_weather", {"location": "Tokyo, Japan"})
    assert "Tokyo" in result
```

Run tests:
```bash
pytest tests/test_weather_tools.py -v
```

## Example Conversation

**User:** "What's the weather like in Paris?"

**LLM (internal):** *Sees get_current_weather tool, decides to call it*

**Function Call:**
```json
{
  "name": "get_current_weather",
  "arguments": {
    "location": "Paris, France",
    "unit": "celsius"
  }
}
```

**Tool Result:** "Current weather in Paris, France: 22°C, partly cloudy"

**LLM Response:** "The current weather in Paris is 22°C and partly cloudy. It's a nice day!"

## Key Takeaways

1. **No changes to react_agent.py** - The agent doesn't know or care about weather tools
2. **Clean separation** - Weather logic is isolated in its own module
3. **Easy testing** - Each tool can be tested independently
4. **Type safety** - Full type hints throughout
5. **Automatic integration** - Registry handles everything

## Advanced: Tool with Dependencies

If your tool needs external dependencies (API clients, database connections, etc.):

```python
class WeatherToolWithClient(BaseTool):
    def __init__(self, api_key: str):
        super().__init__()
        self.api_key = api_key
    
    # ... rest of implementation
```

Then in `create_tool_registry()`:

```python
def create_tool_registry(memory_tools, skills_manager, weather_api_key=None):
    registry = ToolRegistry()
    
    # ... other tools ...
    
    if weather_api_key:
        registry.register(WeatherToolWithClient(weather_api_key))
    
    return registry
```

## Conditional Tool Registration

You can conditionally register tools based on configuration:

```python
def create_tool_registry(memory_tools, skills_manager, config=None):
    registry = ToolRegistry()
    
    # Always register core tools
    registry.register_multiple([...])
    
    # Conditionally register optional tools
    if config and config.get("enable_weather"):
        registry.register_multiple([
            GetCurrentWeatherTool(),
            GetWeatherForecastTool()
        ])
    
    if config and config.get("enable_calendar"):
        registry.register_multiple([...])
    
    return registry
```

---

That's how easy it is to extend the system! The plugin architecture makes adding new capabilities straightforward and maintainable.
