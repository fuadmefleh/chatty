#!/usr/bin/env python3
"""
Script to recategorize existing items in the Amazon and Walmart databases
using the updated categorization logic.
"""

import sqlite3
import os


def categorize_item_amazon(item_name: str) -> str:
    """Categorize an Amazon item based on its name."""
    item_lower = item_name.lower()
    
    # Electronics - Check FIRST for Apple products and other electronics
    electronics_keywords = [
        'imac', 'macbook', 'ipad', 'iphone', 'airpods', 'apple watch',
        'mac mini', 'apple tv', 'apple pencil', 'apple m1', 'apple m2', 'apple m3', 'apple m4',
        'laptop', 'computer', 'tablet', 'smartphone', 'desktop',
        'cable', 'charger', 'adapter', 'usb', 'hdmi', 'bluetooth',
        'headphone', 'earbud', 'speaker', 'mouse', 'keyboard',
        'phone case', 'screen protector', 'battery', 'power bank',
        'monitor', 'webcam', 'carplay'
    ]
    
    if any(keyword in item_lower for keyword in electronics_keywords):
        return 'Electronics'
    
    # Health
    health_keywords = [
        'vitamin', 'supplement', 'melatonin', 'probiotic', 'omega',
        'medicine', 'medication', 'pill', 'tablet', 'capsule',
        'bandage', 'first aid', 'aspirin', 'pain relief', 'antacid'
    ]
    
    if any(keyword in item_lower for keyword in health_keywords):
        return 'Health'
    
    # High priority food
    high_priority_food = [
        'fresh ', 'ice cream', 'frozen', 'refrigerated', 'yogurt', 'cheese',
        'cereal', 'snack', 'candy', 'chocolate', 'cookie', 'cracker',
        'apple', 'banana', 'orange', 'strawberr', 'berry', 'grape',
        'chicken', 'beef', 'pork', 'meat', 'bacon', 'pizza', 'pasta'
    ]
    
    if any(keyword in item_lower for keyword in high_priority_food):
        return 'Food'
    
    # Other quick checks
    if any(kw in item_lower for kw in ['beverage', 'juice', 'water', 'soda', 'drink']):
        return 'Beverages'
    if any(kw in item_lower for kw in ['shampoo', 'soap', 'toothpaste', 'lotion']):
        return 'Personal Care'
    if any(kw in item_lower for kw in ['detergent', 'cleaner', 'paper towel', 'toilet paper']):
        return 'Household'
    if any(kw in item_lower for kw in ['book', 'novel', 'dvd', 'blu-ray']):
        return 'Books & Media'
    if any(kw in item_lower for kw in ['shirt', 'pants', 'shoes', 'clothing']):
        return 'Clothing'
    
    return 'Other'


def categorize_item_walmart(item_name: str) -> str:
    """Categorize a Walmart item based on its name."""
    item_lower = item_name.lower()
    
    # Electronics - Check FIRST for Apple products
    electronics_keywords = [
        'imac', 'macbook', 'ipad', 'iphone', 'airpods', 'apple watch',
        'mac mini', 'apple tv', 'apple pencil', 'apple m1', 'apple m2', 'apple m3', 'apple m4',
        'laptop', 'computer', 'tablet', 'smartphone', 'desktop',
        'cable', 'charger', 'adapter', 'usb', 'hdmi', 'bluetooth',
        'headphone', 'earbud', 'speaker', 'mouse', 'keyboard',
        'carplay', 'playstation', 'xbox', 'nintendo'
    ]
    
    if any(keyword in item_lower for keyword in electronics_keywords):
        return 'Electronics'
    
    # High priority food
    high_priority_food = [
        'fresh ', 'ice cream', 'frozen', 'yogurt', 'cheese',
        'cereal', 'cookie', 'cracker', 'chip',
        'apple', 'banana', 'orange', 'strawberr', 'berry',
        'chicken', 'beef', 'pork', 'meat', 'bacon', 'pizza', 'pasta'
    ]
    
    if any(keyword in item_lower for keyword in high_priority_food):
        # But not if it's actually electronics or kitchen items
        if 'bowl' in item_lower or 'pan' in item_lower:
            pass
        else:
            return 'Food'
    
    # Other quick checks
    if any(kw in item_lower for kw in ['beverage', 'juice', 'water', 'soda', 'drink']):
        return 'Beverages'
    if any(kw in item_lower for kw in ['shampoo', 'soap', 'toothpaste', 'lotion']):
        return 'Personal Care'
    if any(kw in item_lower for kw in ['detergent', 'cleaner', 'paper towel', 'toilet paper']):
        return 'Household'
    
    return 'Other'


def recategorize_database(db_path: str, categorize_func):
    """Recategorize all items in a database."""
    if not os.path.exists(db_path):
        print(f"Database not found: {db_path}")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get all items
    cursor.execute("SELECT id, item_name, category FROM order_items")
    items = cursor.fetchall()
    
    print(f"\nProcessing {len(items)} items from {os.path.basename(db_path)}...")
    
    updated_count = 0
    changes = []
    
    for item_id, item_name, old_category in items:
        # Get new category
        new_category = categorize_func(item_name)
        
        # Update if category changed
        if new_category != old_category:
            cursor.execute(
                "UPDATE order_items SET category = ? WHERE id = ?",
                (new_category, item_id)
            )
            updated_count += 1
            changes.append((item_name, old_category, new_category))
            print(f"  {old_category:20} -> {new_category:20} | {item_name[:60]}")
    
    conn.commit()
    conn.close()
    
    print(f"\nUpdated {updated_count} items in {os.path.basename(db_path)}")
    
    return updated_count, changes


def main():
    """Recategorize items in all databases."""
    print("=" * 80)
    print("RECATEGORIZING ORDER ITEMS")
    print("=" * 80)
    
    # Amazon database
    amazon_db = "/home/edgeworks-server/chatty/data/amazon/amazon_orders.db"
    amazon_count, amazon_changes = recategorize_database(
        amazon_db, 
        categorize_item_amazon
    )
    
    # Walmart database
    walmart_db = "/home/edgeworks-server/chatty/data/walmart/walmart_orders.db"
    walmart_count, walmart_changes = recategorize_database(
        walmart_db,
        categorize_item_walmart
    )
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total items recategorized:")
    print(f"  Amazon:  {amazon_count} items")
    print(f"  Walmart: {walmart_count} items")
    print(f"  TOTAL:   {amazon_count + walmart_count} items")
    print("=" * 80)
    
    # Show specific Apple product fixes
    print("\nApple products that were fixed:")
    all_changes = amazon_changes + walmart_changes
    apple_fixes = [
        (name, old, new) for name, old, new in all_changes 
        if 'apple' in name.lower() and 'imac' in name.lower() or 'ipad' in name.lower() or 'macbook' in name.lower()
    ]
    
    if apple_fixes:
        for name, old_cat, new_cat in apple_fixes:
            print(f"  {old_cat:15} -> {new_cat:15} | {name[:60]}")
    else:
        print("  (Checking broader list...)")
        apple_fixes = [
            (name, old, new) for name, old, new in all_changes 
            if new == 'Electronics' and old == 'Food'
        ]
        for name, old_cat, new_cat in apple_fixes[:10]:
            print(f"  {old_cat:15} -> {new_cat:15} | {name[:60]}")


if __name__ == "__main__":
    main()
