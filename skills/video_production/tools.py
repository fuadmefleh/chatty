"""Video production skill tools for LLM function calling."""
import importlib.util
import json
from pathlib import Path
from typing import Optional

from src.core.skill_tool import SkillTool

# Load the video_api module from this skill folder
_api_path = Path(__file__).parent / "video_api.py"
_spec = importlib.util.spec_from_file_location("video_production_api", _api_path)
_video_api = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_video_api)


class GenerateVideoTool(SkillTool):
    """Generate a short video clip from a text prompt using OpenMontage."""

    name = "generate_video"
    description = (
        "Generate a short video clip from a text description using OpenMontage's AI "
        "video production pipeline. Use this whenever the user asks you to create, "
        "generate, or make a video, clip, short film, or animation. Returns a URL "
        "for the generated video. You MUST embed it in your reply so the user can "
        "see it, e.g. as an HTML video tag `<video controls><source src=\"url\"></video>` "
        "or a markdown link — do not just describe the URL in words."
    )
    parameters = {
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": (
                    "Detailed description of the video to generate. Include style, "
                    "scene, camera movement, and any other creative direction."
                ),
            },
            "duration_seconds": {
                "type": "integer",
                "enum": [2, 4, 6, 8, 10, 15],
                "description": (
                    "Length of the video in seconds. Default is 4. "
                    "Valid values: 2, 4, 6, 8, 10, 15."
                ),
            },
            "resolution": {
                "type": "string",
                "enum": ["480p", "720p", "1080p", "auto"],
                "description": (
                    "Output resolution. 'auto' (default) lets OpenMontage choose "
                    "the best resolution for the prompt."
                ),
            },
        },
        "required": ["prompt"],
    }

    async def execute(
        self,
        prompt: str,
        duration_seconds: Optional[int] = None,
        resolution: str = "auto",
    ) -> str:
        try:
            result = await _video_api.generate_video(
                prompt,
                duration_seconds=duration_seconds,
                resolution=resolution,
            )
            return json.dumps(result)
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"Video generation failed: {str(e)}",
            })
