"""OpenCode skill tools for Chatty bot.

Allows the bot to run the OpenCode AI coding agent to make
code changes directly via subprocess.
"""
import json
from src.core.skill_tool import SkillTool
from skills.opencode.runner import is_running


class RunOpenCodeTool(SkillTool):
    """Run the OpenCode agent to make code changes."""

    name = "run_opencode"
    description = (
        "Run the OpenCode AI coding agent to make code changes. "
        "Use this when the user wants to modify, update, fix, or improve the chatbot's code. "
        "The request launches OpenCode which directly edits the codebase. "
        "Only one request can run at a time."
    )
    parameters = {
        "type": "object",
        "properties": {
            "message": {
                "type": "string",
                "description": "The code change request. Be specific: what to change, where, and why."
            },
            "user_id": {
                "type": "string",
                "description": "The user's ID"
            }
        },
        "required": ["message", "user_id"]
    }

    async def execute(self, message: str, user_id: str) -> str:
        if is_running():
            return json.dumps({
                "success": False,
                "error": "OpenCode is already running a request. Please wait for it to finish."
            })

        # The actual execution happens in the /code command handler
        # which calls runner.run_opencode() and streams output.
        # This tool signals the agent to use the /code command flow.
        return json.dumps({
            "success": True,
            "status": "launching",
            "message": (
                "OpenCode agent is launching with your request. "
                "Progress will be streamed to you in real-time."
            )
        })


class CheckOpenCodeStatusTool(SkillTool):
    """Check if OpenCode is currently running."""

    name = "check_opencode_status"
    description = (
        "Check whether the OpenCode AI coding agent is currently running a task."
    )
    parameters = {
        "type": "object",
        "properties": {},
        "required": []
    }

    async def execute(self) -> str:
        running = is_running()
        return json.dumps({
            "success": True,
            "running": running,
            "message": "OpenCode is currently processing a request." if running
                       else "OpenCode is idle - no active requests."
        })
