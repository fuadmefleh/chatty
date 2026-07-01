#!/usr/bin/env python3
"""Test script for memory tools in ReACT agent."""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.memory_tools import MemoryTools
from src.core.memory import MemoryManager


async def test_memory_tools():
    """Test the memory tools functionality."""
    
    # Initialize for test user
    user_id = "1234567890"
    memory_tools = MemoryTools(user_id)
    
    print("=" * 70)
    print("TESTING MEMORY TOOLS")
    print("=" * 70)
    
    # Test 1: Get memory summary
    print("\n1. Getting memory summary...")
    print("-" * 70)
    result = await memory_tools.get_memory_summary()
    print(result)
    
    # Test 2: List memory files
    print("\n\n2. Listing all memory files...")
    print("-" * 70)
    result = await memory_tools.list_memory_files("all")
    print(result)
    
    # Test 3: Read a specific file
    print("\n\n3. Reading today's memory file (2026-01-30.md)...")
    print("-" * 70)
    result = await memory_tools.read_memory_file("2026-01-30.md", "short_term")
    print(result[:500] + "..." if len(result) > 500 else result)
    
    # Test 4: Search using grep
    print("\n\n4. Searching for 'memory' using grep...")
    print("-" * 70)
    result = await memory_tools.search_memory_grep("memory", context_lines=1)
    print(result[:500] + "..." if len(result) > 500 else result)
    
    # Test 5: Search recent mentions
    print("\n\n5. Searching for recent mentions of 'tools'...")
    print("-" * 70)
    result = await memory_tools.search_recent_mentions("tools", days=7)
    print(result[:500] + "..." if len(result) > 500 else result)
    
    print("\n" + "=" * 70)
    print("TESTS COMPLETED")
    print("=" * 70)


async def add_test_data():
    """Add some test data to demonstrate the tools."""
    user_id = "1234567890"
    memory_manager = MemoryManager(user_id)
    
    print("Adding test conversation data...")
    
    await memory_manager.add_interaction(
        "Can you search through our past conversations?",
        "Yes! I now have memory search tools. I can use grep to search for keywords, "
        "read specific memory files, search by date range, use regex patterns, "
        "and find recent mentions of topics."
    )
    
    await memory_manager.add_interaction(
        "What kind of searches can you do?",
        "I have 7 different memory tools: search_memory_grep for keyword search, "
        "list_memory_files to see what's available, read_memory_file to read specific files, "
        "search_by_date_range for time-based queries, search_pattern for regex, "
        "get_memory_summary for an overview, and search_recent_mentions for topic tracking."
    )
    
    print("Test data added successfully!")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test memory tools")
    parser.add_argument("--add-data", action="store_true", help="Add test conversation data first")
    args = parser.parse_args()
    
    if args.add_data:
        asyncio.run(add_test_data())
        print("\n")
    
    asyncio.run(test_memory_tools())
