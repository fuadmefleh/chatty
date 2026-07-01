"""Notes Manager - handles note storage and retrieval."""
import json
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
import uuid


class Note:
    """Represents a single note."""
    
    def __init__(self, note_id: str, content: str, created_at: str, user_id: str):
        self.id = note_id
        self.content = content
        self.created_at = created_at
        self.user_id = user_id
    
    def to_dict(self) -> Dict:
        """Convert note to dictionary."""
        return {
            "id": self.id,
            "content": self.content,
            "created_at": self.created_at,
            "user_id": self.user_id
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Note':
        """Create note from dictionary."""
        return cls(
            note_id=data["id"],
            content=data["content"],
            created_at=data["created_at"],
            user_id=data["user_id"]
        )


class NotesManager:
    """Manages user notes with persistent storage."""
    
    def __init__(self, data_dir: str = "/home/edgeworks-server/chatty/data/notes"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_user_file(self, user_id: str) -> Path:
        """Get the notes file path for a user."""
        return self.data_dir / f"{user_id}.json"
    
    def _load_notes(self, user_id: str) -> List[Note]:
        """Load all notes for a user."""
        file_path = self._get_user_file(user_id)
        
        if not file_path.exists():
            return []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return [Note.from_dict(note_data) for note_data in data]
        except Exception as e:
            print(f"Error loading notes for user {user_id}: {e}")
            return []
    
    def _save_notes(self, user_id: str, notes: List[Note]) -> None:
        """Save all notes for a user."""
        file_path = self._get_user_file(user_id)
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump([note.to_dict() for note in notes], f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving notes for user {user_id}: {e}")
            raise
    
    def add_note(self, user_id: str, content: str) -> Note:
        """Add a new note for a user."""
        notes = self._load_notes(user_id)
        
        new_note = Note(
            note_id=str(uuid.uuid4()),
            content=content,
            created_at=datetime.now().isoformat(),
            user_id=user_id
        )
        
        notes.append(new_note)
        self._save_notes(user_id, notes)
        
        return new_note
    
    def get_notes(self, user_id: str) -> List[Note]:
        """Get all notes for a user, sorted by creation date (newest first)."""
        notes = self._load_notes(user_id)
        return sorted(notes, key=lambda n: n.created_at, reverse=True)
    
    def get_note_by_id(self, user_id: str, note_id: str) -> Optional[Note]:
        """Get a specific note by ID."""
        notes = self._load_notes(user_id)
        for note in notes:
            if note.id == note_id:
                return note
        return None
    
    def update_note(self, user_id: str, note_id: str, new_content: str) -> Optional[Note]:
        """Update the content of an existing note."""
        notes = self._load_notes(user_id)
        
        for note in notes:
            if note.id == note_id:
                note.content = new_content
                self._save_notes(user_id, notes)
                return note
        
        return None
    
    def delete_note(self, user_id: str, note_id: str) -> bool:
        """Delete a specific note."""
        notes = self._load_notes(user_id)
        original_count = len(notes)
        notes = [n for n in notes if n.id != note_id]
        
        if len(notes) < original_count:
            self._save_notes(user_id, notes)
            return True
        return False
    
    def search_notes(self, user_id: str, query: str) -> List[Note]:
        """Search notes by content."""
        notes = self._load_notes(user_id)
        query_lower = query.lower()
        matching_notes = [n for n in notes if query_lower in n.content.lower()]
        return sorted(matching_notes, key=lambda n: n.created_at, reverse=True)
    
    def get_note_count(self, user_id: str) -> int:
        """Get the total number of notes for a user."""
        return len(self._load_notes(user_id))
