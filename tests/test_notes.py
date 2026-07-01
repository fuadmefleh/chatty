"""Test script for the notes system."""
import sys
import asyncio
from pathlib import Path

# Add the parent directory to the path
sys.path.insert(0, str(Path(__file__).parent))

from skills.notes.notes_manager import NotesManager
from skills.notes.tools import TakeNoteTool, ListUserNotesTool, DeleteNoteTool, SearchNotesTool, set_notes_manager


async def test_notes_system():
    """Test the notes system functionality."""
    print("🧪 Testing Notes System\n")
    
    # Initialize the notes manager
    manager = NotesManager("/home/edgeworks-server/chatty/data/notes")
    set_notes_manager(manager)
    
    test_user_id = "test_user_123"
    
    # Test 1: Create a note
    print("📝 Test 1: Creating a note...")
    take_note_tool = TakeNoteTool()
    result = await take_note_tool.execute(test_user_id, "Remember to buy milk and eggs")
    print(f"Result: {result}\n")
    
    # Test 2: Create more notes
    print("📝 Test 2: Creating more notes...")
    await take_note_tool.execute(test_user_id, "Meeting with Sarah on Friday at 3pm")
    await take_note_tool.execute(test_user_id, "Check the oven temperature setting")
    await take_note_tool.execute(test_user_id, "Call dentist for appointment")
    print("✅ Created 3 more notes\n")
    
    # Test 3: List notes
    print("📋 Test 3: Listing notes...")
    list_notes_tool = ListUserNotesTool()
    result = await list_notes_tool.execute(test_user_id)
    print(f"Result: {result}\n")
    
    # Test 4: Search notes
    print("🔍 Test 4: Searching notes...")
    search_tool = SearchNotesTool()
    result = await search_tool.execute(test_user_id, "appointment")
    print(f"Result: {result}\n")
    
    # Test 5: Get a note ID and delete it
    print("🗑️ Test 5: Deleting a note...")
    notes = manager.get_notes(test_user_id)
    if notes:
        note_to_delete = notes[0]
        print(f"Deleting note: {note_to_delete.content}")
        delete_tool = DeleteNoteTool()
        result = await delete_tool.execute(test_user_id, note_to_delete.id)
        print(f"Result: {result}\n")
    
    # Test 6: List notes again to confirm deletion
    print("📋 Test 6: Listing notes after deletion...")
    result = await list_notes_tool.execute(test_user_id)
    print(f"Result: {result}\n")
    
    # Test 7: Check note count
    print("📊 Test 7: Note count...")
    count = manager.get_note_count(test_user_id)
    print(f"Total notes for {test_user_id}: {count}\n")
    
    print("✅ All tests completed!")


if __name__ == "__main__":
    asyncio.run(test_notes_system())
