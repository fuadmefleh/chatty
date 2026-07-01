"""Weather skill tools for LLM function calling."""
import json
import importlib.util
from pathlib import Path

from src.core.skill_tool import SkillTool

# Load the weather_api module from this skill folder
_api_path = Path(__file__).parent / "weather_api.py"
_spec = importlib.util.spec_from_file_location("weather_api_module", _api_path)
_weather_api = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_weather_api)


class GetWeatherTool(SkillTool):
    """Get current weather and forecast for a location."""

    name = "get_weather"
    description = (
        "Get the current weather conditions and a 3-day forecast for any location. "
        "Returns temperature, humidity, wind, conditions, and daily highs/lows. "
        "Use this when the user asks about weather, temperature, or forecasts."
    )
    parameters = {
        "type": "object",
        "properties": {
            "location": {
                "type": "string",
                "description": "City or place name (e.g. 'New York', 'London', 'Tokyo')"
            }
        },
        "required": ["location"]
    }

    async def execute(self, location: str) -> str:
        try:
            result = await _weather_api.fetch_weather(location)
            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"Weather lookup failed: {str(e)}"
            })
