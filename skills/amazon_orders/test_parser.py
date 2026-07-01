"""Test script for Amazon order parser."""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from skills.amazon_orders.amazon_parser import execute


async def test_parser():
    """Test the Amazon order parser."""
    
    print("=" * 60)
    print("Testing Amazon Order Parser")
    print("=" * 60)
    
    # Test 1: Parse a single PDF
    print("\n1. Parsing single PDF file...")
    result = await execute(pdf_path="Order Details.pdf", action="parse")
    print(f"Result: {result.get('message')}")
    if result.get('items'):
        print(f"\nItems found ({len(result['items'])}):")
        for i, item in enumerate(result['items'][:5], 1):  # Show first 5
            print(f"  {i}. {item['name'][:60]}")
            print(f"     ${item['unit_price']:.2f} (Total: ${item['total_price']:.2f})")
            print(f"     Seller: {item.get('seller', 'Unknown')}")
        if len(result['items']) > 5:
            print(f"  ... and {len(result['items']) - 5} more items")
    
    # Test 2: List all orders
    print("\n2. Listing all orders in database...")
    result = await execute(action="list")
    print(f"Found {result.get('count', 0)} orders")
    if result.get('orders'):
        for order in result['orders'][:3]:  # Show first 3
            print(f"  - Order {order['order_id']}: ${order['total_amount']} on {order['order_date']}")
    
    # Test 3: View all items
    print("\n3. Viewing all purchased items...")
    result = await execute(action="items")
    if result.get('items'):
        print(f"Total items in database: {len(result['items'])}")
        print("\nRecent items:")
        for i, item in enumerate(result['items'][:10], 1):
            print(f"  {i}. {item['name'][:60]}")
            print(f"     ${item['unit_price']:.2f} - Category: {item.get('category', 'Other')}")
    
    # Test 4: Get statistics
    print("\n4. Getting statistics...")
    result = await execute(action="stats")
    print(f"Total spent: ${result.get('total_spent', 0):.2f}")
    print(f"Total orders: {result.get('total_orders', 0)}")
    print(f"Average order: ${result.get('average_order', 0):.2f}")
    
    print("\n" + "=" * 60)
    print("Test completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_parser())
