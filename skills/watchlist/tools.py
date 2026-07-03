"""Watchlist skill tools.

These tools let the LLM manage the user's watched topics. The
WatchlistManager must be set via set_watchlist_manager() before using.
"""
import json
from src.core.skill_tool import SkillTool

# Module-level reference to WatchlistManager - set by main.py
_watchlist_manager = None


def set_watchlist_manager(manager):
    """Set the watchlist manager instance for tools to use.

    Args:
        manager: WatchlistManager instance
    """
    global _watchlist_manager
    _watchlist_manager = manager


def get_watchlist_manager():
    """Get the watchlist manager instance.

    Returns:
        WatchlistManager instance or None if not set
    """
    return _watchlist_manager


class AddWatchTopicTool(SkillTool):
    """Add a topic to the user's watchlist."""

    name = "add_watch_topic"
    description = (
        "Add a topic to the user's watchlist so the bot can proactively watch for and surface "
        "updates about it. Use this when the user asks to 'keep an eye on', 'watch for', or "
        "'follow' something. Three kinds are supported: "
        "'news' (default) - topic is a free-text search query, checked against web news; "
        "'stock' - topic is a ticker symbol (e.g. 'AAPL'), alerts on a large single-day price move; "
        "'github' - topic is an 'owner/repo' string (e.g. 'anthropics/claude-code'), alerts on a new release or commit."
    )
    parameters = {
        "type": "object",
        "properties": {
            "user_id": {
                "type": "string",
                "description": "The user's ID (from the conversation context)"
            },
            "topic": {
                "type": "string",
                "description": "The search query (news), ticker symbol (stock), or 'owner/repo' string (github) to watch"
            },
            "kind": {
                "type": "string",
                "enum": ["news", "stock", "github"],
                "description": "What kind of thing to watch - defaults to 'news'",
                "default": "news"
            }
        },
        "required": ["user_id", "topic"]
    }

    async def execute(self, user_id: str, topic: str, kind: str = "news") -> str:
        manager = get_watchlist_manager()
        if not manager:
            return json.dumps({
                "success": False,
                "error": "Watchlist system not initialized"
            })

        try:
            watch_topic = manager.add_topic(user_id, topic, kind=kind)

            return json.dumps({
                "success": True,
                "topic_id": watch_topic.id,
                "topic": watch_topic.topic,
                "kind": watch_topic.kind,
                "message": "Now watching this topic - I'll surface updates as they come in."
            })
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"Failed to add watch topic: {str(e)}"
            })


class RemoveWatchTopicTool(SkillTool):
    """Remove a topic from the user's watchlist."""

    name = "remove_watch_topic"
    description = "Stop watching a topic. Use this when the user asks to 'stop watching', 'unwatch', or 'remove' something from their watchlist. You can pass either the topic's exact text or its ID."
    parameters = {
        "type": "object",
        "properties": {
            "user_id": {
                "type": "string",
                "description": "The user's ID (from the conversation context)"
            },
            "topic_or_id": {
                "type": "string",
                "description": "The topic text (or its ID) to stop watching"
            }
        },
        "required": ["user_id", "topic_or_id"]
    }

    async def execute(self, user_id: str, topic_or_id: str) -> str:
        manager = get_watchlist_manager()
        if not manager:
            return json.dumps({
                "success": False,
                "error": "Watchlist system not initialized"
            })

        try:
            match = manager.find_topic(user_id, topic_or_id)
            if not match:
                current = [t.topic for t in manager.get_topics(user_id)]
                return json.dumps({
                    "success": False,
                    "error": f"No matching watched topic found for '{topic_or_id}'.",
                    "currently_watching": current
                })

            manager.remove_topic(user_id, match.id)
            return json.dumps({
                "success": True,
                "message": f"Stopped watching '{match.topic}'"
            })
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"Failed to remove watch topic: {str(e)}"
            })


class ListWatchTopicsTool(SkillTool):
    """List all watched topics for a user."""

    name = "list_watch_topics"
    description = "List all topics currently being watched for the user. Use this when the user asks what they're watching or following."
    parameters = {
        "type": "object",
        "properties": {
            "user_id": {
                "type": "string",
                "description": "The user's ID (from the conversation context)"
            }
        },
        "required": ["user_id"]
    }

    async def execute(self, user_id: str) -> str:
        manager = get_watchlist_manager()
        if not manager:
            return json.dumps({
                "success": False,
                "error": "Watchlist system not initialized"
            })

        try:
            topics = manager.get_topics(user_id)

            return json.dumps({
                "success": True,
                "count": len(topics),
                "topics": [
                    {
                        "id": t.id,
                        "topic": t.topic,
                        "kind": t.kind,
                        "created_at": t.created_at,
                        "last_run_at": t.last_run_at,
                    }
                    for t in topics
                ]
            })
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"Failed to list watch topics: {str(e)}"
            })
