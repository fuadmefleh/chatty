"""VS Code Bridge skill tools for Chatty bot.

Allows the bot to queue code change requests that are picked up
by the VS Code Copilot agent extension.
"""
import json
from src.core.skill_tool import SkillTool
from skills.vscode_bridge.queue_manager import VSCodeRequestQueue


queue = VSCodeRequestQueue()


class SendVSCodeRequestTool(SkillTool):
    """Queue a code change request for the VS Code agent."""

    name = "send_vscode_request"
    description = (
        "Send a code change request to the VS Code Copilot agent. "
        "Use this when the user wants to modify, update, fix, or improve the chatbot's code. "
        "The request will be queued and picked up by the VS Code extension running Copilot in agent mode."
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
        try:
            request = queue.add_request(message, user_id)
            return json.dumps({
                "success": True,
                "request_id": request["id"],
                "status": "pending",
                "message": f"Code request queued (ID: {request['id'][:8]}...). "
                           f"The VS Code agent will pick this up automatically."
            })
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"Failed to queue request: {str(e)}"
            })


class CheckVSCodeRequestsTool(SkillTool):
    """Check the status of VS Code code change requests."""

    name = "check_vscode_requests"
    description = (
        "Check the status of code change requests sent to the VS Code agent. "
        "Can filter by status: pending, in_progress, completed, failed."
    )
    parameters = {
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "description": "Filter by status. Leave empty for all requests.",
                "enum": ["pending", "in_progress", "completed", "failed"]
            }
        },
        "required": []
    }

    async def execute(self, status: str = None) -> str:
        try:
            requests = queue.get_requests(status=status)
            summary = []
            for req in requests:
                summary.append({
                    "id": req["id"][:8] + "...",
                    "message": req["message"][:100] + ("..." if len(req["message"]) > 100 else ""),
                    "status": req["status"],
                    "created_at": req["created_at"],
                    "result": req.get("result")
                })
            return json.dumps({
                "success": True,
                "total": len(summary),
                "requests": summary
            }, indent=2)
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"Failed to check requests: {str(e)}"
            })
