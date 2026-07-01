"""Notes skill tools.

These tools allow the LLM to save and manage notes for users.
The NotesManager must be set via set_notes_manager() before using.
"""
import json
from typing import Optional
from src.core.skill_tool import SkillTool

# Module-level reference to NotesManager - set by main.py
_notes_manager = None


def set_notes_manager(manager):
    """Set the notes manager instance for tools to use.
    
    Args:
        manager: NotesManager instance
    """
    global _notes_manager
    _notes_manager = manager


def get_notes_manager():
    """Get the notes manager instance.
    
    Returns:
        NotesManager instance or None if not set
    """
    return _notes_manager


class TakeNoteTool(SkillTool):
    """Save a note for the user."""
    
    name = "take_note"
    description = "Save a note for the user. Use this when the user asks you to 'take note', 'write down', 'remember', or 'note that'. The note will be saved with a timestamp."
    parameters = {
        "type": "object",
        "properties": {
            "user_id": {
                "type": "string",
                "description": "The user's ID (from the conversation context)"
            },
            "note_content": {
                "type": "string",
                "description": "The content of the note to save"
            }
        },
        "required": ["user_id", "note_content"]
    }
    
    async def execute(self, user_id: str, note_content: str) -> str:
        manager = get_notes_manager()
        if not manager:
            return json.dumps({
                "success": False,
                "error": "Notes system not initialized"
            })
        
        try:
            note = manager.add_note(user_id, note_content)
            
            return json.dumps({
                "success": True,
                "note_id": note.id,
                "content": note.content,
                "created_at": note.created_at,
                "message": "Note saved successfully"
            })
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"Failed to save note: {str(e)}"
            })


class ListUserNotesTool(SkillTool):
    """List all notes for a user."""
    
    name = "list_user_notes"
    description = "Get a list of all notes for the user. Returns notes sorted by creation date (newest first)."
    parameters = {
        "type": "object",
        "properties": {
            "user_id": {
                "type": "string",
                "description": "The user's ID (from the conversation context)"
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of notes to return (default: 50)",
                "default": 50
            }
        },
        "required": ["user_id"]
    }
    
    async def execute(self, user_id: str, limit: int = 50) -> str:
        manager = get_notes_manager()
        if not manager:
            return json.dumps({
                "success": False,
                "error": "Notes system not initialized"
            })
        
        try:
            notes = manager.get_notes(user_id)[:limit]
            
            return json.dumps({
                "success": True,
                "count": len(notes),
                "notes": [
                    {
                        "id": note.id,
                        "content": note.content,
                        "created_at": note.created_at
                    }
                    for note in notes
                ]
            })
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"Failed to list notes: {str(e)}"
            })


class DeleteNoteTool(SkillTool):
    """Delete a specific note."""
    
    name = "delete_note"
    description = "Delete a specific note by its ID. Use this when the user asks to remove or delete a note."
    parameters = {
        "type": "object",
        "properties": {
            "user_id": {
                "type": "string",
                "description": "The user's ID (from the conversation context)"
            },
            "note_id": {
                "type": "string",
                "description": "The ID of the note to delete"
            }
        },
        "required": ["user_id", "note_id"]
    }
    
    async def execute(self, user_id: str, note_id: str) -> str:
        manager = get_notes_manager()
        if not manager:
            return json.dumps({
                "success": False,
                "error": "Notes system not initialized"
            })
        
        try:
            deleted = manager.delete_note(user_id, note_id)
            
            if deleted:
                return json.dumps({
                    "success": True,
                    "message": "Note deleted successfully"
                })
            else:
                return json.dumps({
                    "success": False,
                    "error": "Note not found"
                })
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"Failed to delete note: {str(e)}"
            })


class SearchNotesTool(SkillTool):
    """Search notes by keyword."""
    
    name = "search_notes"
    description = "Search through the user's notes for a specific keyword or phrase. Returns matching notes."
    parameters = {
        "type": "object",
        "properties": {
            "user_id": {
                "type": "string",
                "description": "The user's ID (from the conversation context)"
            },
            "query": {
                "type": "string",
                "description": "The search query (keyword or phrase)"
            }
        },
        "required": ["user_id", "query"]
    }
    
    async def execute(self, user_id: str, query: str) -> str:
        manager = get_notes_manager()
        if not manager:
            return json.dumps({
                "success": False,
                "error": "Notes system not initialized"
            })
        
        try:
            notes = manager.search_notes(user_id, query)
            
            return json.dumps({
                "success": True,
                "count": len(notes),
                "query": query,
                "notes": [
                    {
                        "id": note.id,
                        "content": note.content,
                        "created_at": note.created_at
                    }
                    for note in notes
                ]
            })
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"Failed to search notes: {str(e)}"
            })
