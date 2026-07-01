"""Script to update all existing items in the database with categories."""

from skills.walmart_orders.walmart_parser import WalmartOrderDB

def main():
    print("Updating categories for all items in the database...")
    
    db = WalmartOrderDB()
    try:
        # Update all categories
        count = db.update_all_categories()
        print(f"✓ Updated {count} items with categories")
        
        # Show spending by category
        print("\n=== Spending by Category ===")
        categories = db.get_spending_by_category()
        
        for cat in categories:
            print(f"{cat['category']:20} ${cat['total_spent']:8.2f} ({cat['percentage']:5.1f}%) - {cat['item_count']} items")
        
        print(f"\nTotal: ${sum(c['total_spent'] for c in categories):.2f}")
        
        # Show sample items from each category
        print("\n=== Sample Items by Category ===")
        for cat in categories[:5]:  # Top 5 categories
            category_name = cat['category']
            items = db.get_items_by_category(category_name, limit=3)
            print(f"\n{category_name}:")
            for item in items:
                print(f"  - {item['name']} (${item['total_price']:.2f})")
        
    finally:
        db.close()
    
    print("\n✓ Category update complete!")

if __name__ == "__main__":
    main()
