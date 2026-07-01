"""Test script to demonstrate the category feature."""
import asyncio
from skills.walmart_orders.query_orders import (
    get_spending_by_category,
    get_items_by_category
)

async def main():
    print("=== Walmart Purchases by Category ===\n")
    
    # Get spending breakdown
    result = await get_spending_by_category()
    
    if result['success']:
        print(f"Total Spent: ${result['total_spent']}")
        print(f"Date Range: {result['date_range']}\n")
        
        print("Category Breakdown:")
        print("-" * 70)
        for cat in result['categories']:
            print(f"{cat['category']:20} ${cat['total_spent']:8.2f} ({cat['percentage']:5.1f}%)")
            print(f"                     {cat['item_count']} items, {cat['total_quantity']} total quantity")
        
        print("\n" + "=" * 70)
        
        # Show sample items from Food category
        print("\n=== Sample Food Items ===")
        food_result = await get_items_by_category('Food', limit=10)
        if food_result['success']:
            for item in food_result['items'][:10]:
                print(f"  ${item['total_price']:6.2f} - {item['name'][:60]}")
        
        # Show sample items from Household category
        print("\n=== Sample Household Items ===")
        household_result = await get_items_by_category('Household', limit=10)
        if household_result['success']:
            for item in household_result['items'][:10]:
                print(f"  ${item['total_price']:6.2f} - {item['name'][:60]}")

if __name__ == "__main__":
    asyncio.run(main())
