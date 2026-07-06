"""Image generation skill tools for LLM function calling."""
import json
import importlib.util
from pathlib import Path

from src.core.skill_tool import SkillTool

# Load the image_api module from this skill folder
_api_path = Path(__file__).parent / "image_api.py"
_spec = importlib.util.spec_from_file_location("image_generation_api", _api_path)
_image_api = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_image_api)


class GenerateImageTool(SkillTool):
    """Generate an image from a text prompt using OpenAI's gpt-image-1 model."""

    name = "generate_image"
    description = (
        "Generate an image from a text description using OpenAI's gpt-image-1 model. "
        "Use this whenever the user asks you to create, draw, generate, or make an "
        "image/picture/illustration. Returns a URL for the generated image. You MUST embed "
        "it in your reply as a markdown image so the user actually sees it, e.g. "
        "`![](<url>)` - do not just describe the URL in words."
    )
    parameters = {
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "Detailed description of the image to generate.",
            },
            "size": {
                "type": "string",
                "enum": ["auto", "1024x1024", "1536x1024", "1024x1536"],
                "description": (
                    "Image dimensions. 'auto' (default) lets the model choose; 1536x1024 "
                    "for landscape, 1024x1536 for portrait, 1024x1024 for square."
                ),
            },
        },
        "required": ["prompt"],
    }

    async def execute(self, prompt: str, size: str = "auto") -> str:
        try:
            result = await _image_api.generate_image(prompt, size=size)
            return json.dumps(result)
        except Exception as e:
            return json.dumps({"success": False, "error": f"Image generation failed: {str(e)}"})
