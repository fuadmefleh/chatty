"""Test script for Walmart order parser."""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from skills.walmart_orders.walmart_parser import execute


async def test_parser():
    """Test the Walmart order parser."""
    
    print("=" * 60)
    print("Testing Walmart Order Parser")
    print("=" * 60)
    
    # Test 1: Parse a single PDF
    print("\n1. Parsing single PDF file...")
    result = await execute(pdf_path="2000143-78966231.pdf", action="parse")
    print(f"Result: {result.get('message')}")
    if result.get('items'):
        print(f"\nItems found ({len(result['items'])}):")
        for i, item in enumerate(result['items'][:5], 1):  # Show first 5
            print(f"  {i}. {item['name']}")
            print(f"     Qty: {item['quantity']} @ ${item['unit_price']:.2f} each = ${item['total_price']:.2f}")
        if len(result['items']) > 5:
            print(f"  ... and {len(result['items']) - 5} more items")
    
    # Test 2: List all orders
    print("\n2. Listing all orders in database...")
    result = await execute(action="list")
    print(f"Found {result.get('count', 0)} orders")
    if result.get('orders'):
        for order in result['orders'][:3]:  # Show first 3
            print(f"  - Order {order['order_id']}: ${order['total_amount']} on {order['order_date']}")
    
    # Test 4: View all items
    print("\n4. Viewing all purchased items...")
    result = await execute(action="items")
    if result.get('items'):
        print(f"Total items in database: {len(result['items'])}")
        print("\nRecent items:")
        for i, item in enumerate(result['items'][:10], 1):
            print(f"  {i}. {item['name'][:50]}")
            print(f"     Qty: {item['quantity']} @ ${item['unit_price']:.2f} = ${item['total_price']:.2f}")
    
    # Test 5: Query specific order
    print("\n5. Querying specific order details...")
    result = await execute(pdf_path="2000143-78966231", action="query")
    if result.get('order'):
        order = result['order']
        print(f"Order: {order['order_id']}")
        print(f"Total: ${order['total_amount']:.2f} ({len(order['items'])} items)")
    
    # Test 3: Get statistics
    print("\n3. Getting statistics...")
    result = await execute(action="stats")
    print(f"Total spent: ${result.get('total_spent', 0):.2f}")
    print(f"Total orders: {result.get('total_orders', 0)}")
    print(f"Average order: ${result.get('average_order', 0):.2f}")
    
    print("\n" + "=" * 60)
    print("Test completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_parser())
