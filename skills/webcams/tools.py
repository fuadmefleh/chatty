"""Webcams skill tools - read-only listing of known live webcam sources.

Does not fetch or analyze any image/video content; that's a separate,
not-yet-built feature. Reads from the same WebcamSourcesManager/JSON file the
dashboard's /webcams page uses, instantiated directly here (rather than via
an externally-injected setter) so it works the same whether loaded by the
Telegram bot's SkillsManager (src/main.py) or the web dashboard's
SkillsManager (chatty_web_server.py).
"""
import json
from src.core.skill_tool import SkillTool
from src.managers.webcam_manager import WebcamSourcesManager

_sources_manager = WebcamSourcesManager()


class ListWebcamSourcesTool(SkillTool):
    """List the user's known live webcam sources."""

    name = "list_webcam_sources"
    description = (
        "List the user's approved/manually-added live webcam sources (name, location, kind, "
        "url). Read-only - does not fetch or analyze any image/video content. Use when the "
        "user asks what webcams/live cams are available, optionally about a place."
    )
    parameters = {
        "type": "object",
        "properties": {
            "location_filter": {
                "type": "string",
                "description": "Optional substring to filter by location or name (e.g. 'NYC')"
            }
        },
        "required": []
    }

    async def execute(self, location_filter: str = "") -> str:
        try:
            sources = [s for s in _sources_manager.list() if s.enabled]
            if location_filter:
                needle = location_filter.lower()
                sources = [
                    s for s in sources
                    if needle in s.location.lower() or needle in s.name.lower()
                ]

            return json.dumps({
                "success": True,
                "count": len(sources),
                "sources": [
                    {"name": s.name, "location": s.location, "kind": s.kind, "url": s.url}
                    for s in sources
                ]
            })
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"Failed to list webcam sources: {str(e)}"
            })
