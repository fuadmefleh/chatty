"""Test script for Walmart order processing in heartbeat."""
import asyncio
import logging
from pathlib import Path
from src.managers.heartbeat_manager import HeartbeatManager
from src.core.skills import SkillsManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def test_walmart_processing():
    """Test the Walmart order processing functionality."""
    print("=" * 60)
    print("Testing Walmart Order Processing")
    print("=" * 60)
    
    # Create skills manager and heartbeat manager
    skills_manager = SkillsManager()
    heartbeat_manager = HeartbeatManager(skills_manager)
    
    # Check initial state
    walmart_dir = Path("data/walmart")
    pdf_files = list(walmart_dir.glob("*.pdf"))
    print(f"\nInitial state: {len(pdf_files)} PDFs in data/walmart")
    
    # Run the Walmart processing
    print("\nProcessing Walmart orders...")
    await heartbeat_manager._process_walmart_orders()
    
    # Check final state
    pdf_files_after = list(walmart_dir.glob("*.pdf"))
    archived_files = list((walmart_dir / "archived").glob("*.pdf"))
    
    print(f"\nFinal state:")
    print(f"  - PDFs remaining in data/walmart: {len(pdf_files_after)}")
    print(f"  - PDFs in archived: {len(archived_files)}")
    print(f"  - PDFs processed: {len(pdf_files) - len(pdf_files_after)}")
    
    print("\n" + "=" * 60)
    print("Test completed!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_walmart_processing())
