"""Webcams skill tools - listing known live webcam sources, and handing back
ready-to-embed markdown so Atlas can actually pull a stream up for the user
instead of just describing it.

Reads from the same WebcamSourcesManager/JSON file the dashboard's /webcams
page uses, instantiated directly here (rather than via an externally-injected
setter) so it works the same whether loaded by the Telegram bot's
SkillsManager (src/main.py) or the web dashboard's SkillsManager
(chatty_web_server.py).
"""
import json
from src.core.skill_tool import SkillTool
from src.managers.webcam_manager import WebcamSourcesManager

_sources_manager = WebcamSourcesManager()

# Kinds the frontend can actually play inline. "webpage" sources are tracked
# but can only ever be opened externally - never embedded.
_EMBEDDABLE_KINDS = ("snapshot", "mjpeg", "hls", "youtube")


class ListWebcamSourcesTool(SkillTool):
    """List the user's known live webcam sources."""

    name = "list_webcam_sources"
    description = (
        "List the user's approved/manually-added live webcam sources (name, location, kind, "
        "url, verify_status). verify_status is 'ok' (Atlas has confirmed it's actually playable), "
        "'broken' (last check failed), or 'unchecked'. Use when the user asks what webcams/live "
        "cams are available, optionally about a place. To actually show a stream to the user, "
        "use open_webcam_stream instead of building the embed yourself."
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
                    {
                        "name": s.name, "location": s.location, "kind": s.kind, "url": s.url,
                        "verify_status": s.verify_status,
                    }
                    for s in sources
                ]
            })
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"Failed to list webcam sources: {str(e)}"
            })


class OpenWebcamStreamTool(SkillTool):
    """Resolve a webcam by name/location and return ready-to-paste markdown
    that actually shows the live feed, rather than just a link."""

    name = "open_webcam_stream"
    description = (
        "Pull up a live webcam stream so the user can actually watch it, instead of just "
        "describing it. Matches by name or location substring against the user's known webcam "
        "sources and returns a 'markdown' field - paste that markdown verbatim into your reply "
        "(don't rewrite it, don't wrap the link text) and it will render as a live inline player "
        "for the user. Only offers sources Atlas has confirmed actually work "
        "(verify_status == 'ok'); if none match or the match is broken/unverified, say so instead "
        "of guessing. Use when the user asks to see/watch/pull up/show a specific cam."
    )
    parameters = {
        "type": "object",
        "properties": {
            "name_or_location": {
                "type": "string",
                "description": "Substring to match against a source's name or location, e.g. 'Times Square' or 'NYC'"
            }
        },
        "required": ["name_or_location"]
    }

    async def execute(self, name_or_location: str) -> str:
        try:
            needle = name_or_location.strip().lower()
            if not needle:
                return json.dumps({"success": False, "error": "name_or_location is required"})

            enabled = [s for s in _sources_manager.list() if s.enabled]
            match = next(
                (s for s in enabled if needle in s.name.lower() or needle in s.location.lower()),
                None,
            )
            if match is None:
                return json.dumps({
                    "success": False,
                    "error": f"No known webcam source matches '{name_or_location}'.",
                })

            if match.verify_status != "ok":
                return json.dumps({
                    "success": False,
                    "error": (
                        f"'{match.name}' is known but Atlas hasn't confirmed it's currently "
                        f"playable (verify_status: {match.verify_status})."
                    ),
                    "url": match.url,
                })

            if match.kind in ("snapshot", "mjpeg"):
                return json.dumps({
                    "success": True,
                    "embeddable": True,
                    "markdown": f"![{match.name}]({match.url})",
                })

            if match.kind in ("hls", "youtube"):
                return json.dumps({
                    "success": True,
                    "embeddable": True,
                    "markdown": f"[Watch {match.name} live](/webcams/watch/{match.id})",
                })

            # webpage - can't be embedded inline at all.
            return json.dumps({
                "success": True,
                "embeddable": False,
                "markdown": f"[{match.name}]({match.url})",
                "note": "This source is a webpage, not a media feed - it can't be shown inline, only opened.",
            })
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"Failed to open webcam stream: {str(e)}"
            })
