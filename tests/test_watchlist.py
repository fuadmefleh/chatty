"""Test script for the watchlist system."""
import sys
import asyncio
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from skills.watchlist.watchlist_manager import WatchlistManager
from skills.watchlist.tools import (
    AddWatchTopicTool,
    RemoveWatchTopicTool,
    ListWatchTopicsTool,
    set_watchlist_manager,
)


async def test_watchlist_system():
    """Test the watchlist system functionality."""
    print("🧪 Testing Watchlist System\n")

    with tempfile.TemporaryDirectory() as tmp_dir:
        manager = WatchlistManager(tmp_dir)
        set_watchlist_manager(manager)

        test_user_id = "test_user_123"

        # Test 1: Add a topic
        print("🔭 Test 1: Adding a watch topic...")
        add_tool = AddWatchTopicTool()
        result = await add_tool.execute(test_user_id, "SpaceX Starship launches")
        print(f"Result: {result}\n")

        await add_tool.execute(test_user_id, "Bitcoin price")

        # Test 2: List topics
        print("📋 Test 2: Listing watch topics...")
        list_tool = ListWatchTopicsTool()
        result = await list_tool.execute(test_user_id)
        print(f"Result: {result}\n")

        topics = manager.get_topics(test_user_id)
        assert len(topics) == 2

        # Test 3: Remove by substring match
        print("🗑️ Test 3: Removing a topic by text match...")
        remove_tool = RemoveWatchTopicTool()
        result = await remove_tool.execute(test_user_id, "bitcoin")
        print(f"Result: {result}\n")

        remaining = manager.get_topics(test_user_id)
        assert len(remaining) == 1
        assert remaining[0].topic == "SpaceX Starship launches"

        # Test 4: Removing a topic that doesn't exist fails cleanly
        print("🗑️ Test 4: Removing a non-existent topic...")
        result = await remove_tool.execute(test_user_id, "nonexistent topic xyz")
        print(f"Result: {result}\n")

        print("✅ All tests completed!")


if __name__ == "__main__":
    asyncio.run(test_watchlist_system())
