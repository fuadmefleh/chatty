"""Per-in-flight-request context.

Set by the single agent.think() call site in src/main.py's handle_message,
read by skill tools that need to act on the current Telegram chat directly
(the bot/chat_id aren't otherwise reachable from SkillTool.execute() - see
skills/tts/tools.py).
"""
from contextvars import ContextVar
from typing import Optional

current_chat_id: ContextVar[Optional[int]] = ContextVar("current_chat_id", default=None)
