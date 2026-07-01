"""Math Calculator skill tools for LLM function calling.

These tools are dynamically loaded by the framework when the skill is activated.
"""
import json
import sys
import importlib.util
from pathlib import Path

# Add project root to path for src imports
project_root = str(Path(__file__).parent.parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.core.skill_tool import SkillTool

# Load the calculate module from THIS skill folder explicitly
_calc_path = Path(__file__).parent / "calculate.py"
_spec = importlib.util.spec_from_file_location("math_calculate", _calc_path)
_calc_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_calc_module)


class CalculateMath(SkillTool):
    """Evaluate mathematical expressions safely."""
    
    name = "calculate_math"
    description = "Evaluate mathematical expressions safely. Supports +, -, *, /, and ** (power). Use this when the user asks to calculate or compute something numerical."
    parameters = {
        "type": "object",
        "properties": {
            "expression": {
                "type": "string",
                "description": "The mathematical expression to evaluate (e.g., '2 + 2', '10 * 5', '2 ** 8')"
            }
        },
        "required": ["expression"]
    }
    
    async def execute(self, expression: str) -> str:
        try:
            result = await _calc_module.execute(expression)
            return json.dumps({
                "success": True,
                "expression": expression,
                "result": result
            }, indent=2)
        except Exception as e:
            return json.dumps({
                "success": False,
                "expression": expression,
                "error": str(e)
            }, indent=2)
