# Notes Skill

This skill allows you to save and manage notes through natural conversation with the bot.

## Features

- **Save Notes**: Tell the bot to "take note" or "write down" something, and it will save it
- **List Notes**: Use `/notes` command to view all your notes
- **Delete Notes**: Remove specific notes through the UI
- **Search Notes**: Find notes by keyword
- **Categorize**: Notes are automatically timestamped

## Usage Examples

**Saving notes:**
- "Take note that I need to call the dentist"
- "Write down that my favorite pizza is pepperoni"
- "Remember to note that the meeting is at 3pm tomorrow"

**Viewing notes:**
- Use `/notes` command in Telegram

## Tools

### take_note
Saves a note for the user.

**Parameters:**
- `user_id` (string, required): The user's ID
- `note_content` (string, required): The content of the note to save

**Returns:** Success status and note ID

### list_user_notes
Lists all notes for a user.

**Parameters:**
- `user_id` (string, required): The user's ID

**Returns:** List of notes with IDs and timestamps

### delete_note
Deletes a specific note.

**Parameters:**
- `user_id` (string, required): The user's ID
- `note_id` (string, required): The ID of the note to delete

**Returns:** Success status

### search_notes
Searches notes by keyword.

**Parameters:**
- `user_id` (string, required): The user's ID
- `query` (string, required): Search query

**Returns:** Matching notes
