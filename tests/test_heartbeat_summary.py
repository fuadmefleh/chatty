#!/usr/bin/env python3
"""Test script for heartbeat summary functionality."""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from src.managers.heartbeat_manager import HeartbeatManager
from src.core.skills_manager import SkillsManager


async def test_heartbeat_summary():
    """Test the heartbeat summary functionality."""
    print("Testing heartbeat summary functionality...")
    print("=" * 60)
    
    # Create skills manager
    skills_manager = SkillsManager()
    await skills_manager.initialize()
    
    # Create heartbeat manager
    heartbeat_manager = HeartbeatManager(skills_manager)
    
    # Create mock callbacks
    def get_user_agents():
        return {}
    
    def get_user_memories():
        return {}
    
    async def send_message(user_id, message):
        print("\n" + "=" * 60)
        print(f"📱 TELEGRAM MESSAGE TO USER {user_id}:")
        print("=" * 60)
        print(message)
        print("=" * 60 + "\n")
    
    # Set callbacks
    heartbeat_manager.set_user_agents_callback(get_user_agents)
    heartbeat_manager.set_user_memories_callback(get_user_memories)
    heartbeat_manager.set_send_message_callback(send_message)
    
    # Execute heartbeat
    print("Executing heartbeat cycle...\n")
    await heartbeat_manager.execute_heartbeat()
    
    print("\n✅ Heartbeat test completed!")


if __name__ == "__main__":
    asyncio.run(test_heartbeat_summary())
