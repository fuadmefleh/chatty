"""Reminder skill tools.

These tools allow the LLM to set, list, and cancel reminders.
The ReminderManager must be set via set_reminder_manager() before using.
"""
import json
from datetime import datetime
from typing import Optional
from src.core.skill_tool import SkillTool

# Module-level reference to ReminderManager - set by main.py
_reminder_manager = None


def set_reminder_manager(manager):
    """Set the reminder manager instance for tools to use.
    
    Args:
        manager: ReminderManager instance
    """
    global _reminder_manager
    _reminder_manager = manager


def get_reminder_manager():
    """Get the reminder manager instance.
    
    Returns:
        ReminderManager instance or None if not set
    """
    return _reminder_manager


class SetReminderTool(SkillTool):
    """Set a new reminder for the user."""
    
    name = "set_reminder"
    description = "Set a reminder that will notify the user at a specific time. Supports natural language time expressions like 'in 5 minutes', 'tomorrow at 3pm', 'in 2 hours'."
    parameters = {
        "type": "object",
        "properties": {
            "user_id": {
                "type": "string",
                "description": "The user's ID (from the conversation context)"
            },
            "message": {
                "type": "string",
                "description": "The reminder message to show the user"
            },
            "time_expression": {
                "type": "string",
                "description": "When to remind (e.g., 'in 5 minutes', 'tomorrow at 3pm', '2pm today', 'in 2 hours')"
            }
        },
        "required": ["user_id", "message", "time_expression"]
    }
    
    async def execute(self, user_id: str, message: str, time_expression: str) -> str:
        manager = get_reminder_manager()
        if not manager:
            return json.dumps({
                "success": False,
                "error": "Reminder system not initialized"
            })
        
        # Parse the time expression
        scheduled_time = manager.parse_time_expression(time_expression)
        
        if not scheduled_time:
            return json.dumps({
                "success": False,
                "error": f"Could not understand time expression: '{time_expression}'. Try formats like 'in 5 minutes', 'tomorrow at 3pm', 'at 2pm'."
            })
        
        # Don't allow reminders in the past
        if scheduled_time < datetime.now():
            return json.dumps({
                "success": False,
                "error": f"The specified time ({scheduled_time.strftime('%Y-%m-%d %H:%M')}) is in the past."
            })
        
        # Add the reminder
        reminder_id = await manager.add_reminder(user_id, message, scheduled_time)
        
        return json.dumps({
            "success": True,
            "reminder_id": reminder_id,
            "message": message,
            "scheduled_for": scheduled_time.strftime("%Y-%m-%d %H:%M:%S"),
            "time_until": str(scheduled_time - datetime.now()).split('.')[0]  # Remove microseconds
        })


class ListRemindersTool(SkillTool):
    """List all active reminders for a user."""
    
    name = "list_reminders"
    description = "Get a list of all active (not yet triggered) reminders for the user."
    parameters = {
        "type": "object",
        "properties": {
            "user_id": {
                "type": "string",
                "description": "The user's ID"
            }
        },
        "required": ["user_id"]
    }
    
    async def execute(self, user_id: str) -> str:
        manager = get_reminder_manager()
        if not manager:
            return json.dumps({
                "success": False,
                "error": "Reminder system not initialized"
            })
        
        reminders = await manager.get_user_reminders(user_id, include_sent=False)
        
        if not reminders:
            return json.dumps({
                "success": True,
                "count": 0,
                "reminders": [],
                "message": "No active reminders found."
            })
        
        reminder_list = []
        for r in reminders:
            scheduled = datetime.fromisoformat(r.scheduled_time)
            reminder_list.append({
                "id": r.id,
                "message": r.message,
                "scheduled_for": scheduled.strftime("%Y-%m-%d %H:%M"),
                "time_until": str(scheduled - datetime.now()).split('.')[0] if scheduled > datetime.now() else "overdue"
            })
        
        return json.dumps({
            "success": True,
            "count": len(reminder_list),
            "reminders": reminder_list
        })


class CancelReminderTool(SkillTool):
    """Cancel a specific reminder."""
    
    name = "cancel_reminder"
    description = "Cancel a reminder by its ID. Use list_reminders first to get the reminder ID."
    parameters = {
        "type": "object",
        "properties": {
            "user_id": {
                "type": "string",
                "description": "The user's ID"
            },
            "reminder_id": {
                "type": "string",
                "description": "The ID of the reminder to cancel"
            }
        },
        "required": ["user_id", "reminder_id"]
    }
    
    async def execute(self, user_id: str, reminder_id: str) -> str:
        manager = get_reminder_manager()
        if not manager:
            return json.dumps({
                "success": False,
                "error": "Reminder system not initialized"
            })
        
        cancelled = await manager.cancel_reminder(user_id, reminder_id)
        
        if cancelled:
            return json.dumps({
                "success": True,
                "message": f"Reminder {reminder_id} has been cancelled."
            })
        else:
            return json.dumps({
                "success": False,
                "error": f"Could not find reminder with ID {reminder_id}. Use list_reminders to see active reminders."
            })
