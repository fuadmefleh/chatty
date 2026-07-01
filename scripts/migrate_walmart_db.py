#!/usr/bin/env python3
"""Migrate existing Walmart database to add delivery_status column to order_items."""
import sqlite3
import sys

db_path = 'data/walmart/walmart_orders.db'

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if column exists in order_items
    cursor.execute("PRAGMA table_info(order_items)")
    columns = [row[1] for row in cursor.fetchall()]
    
    if 'delivery_status' in columns:
        print("✓ delivery_status column already exists in order_items")
    else:
        print("Adding delivery_status column to order_items...")
        cursor.execute("ALTER TABLE order_items ADD COLUMN delivery_status TEXT")
        conn.commit()
        print("✓ Successfully added delivery_status column to order_items")
    
    # Verify
    cursor.execute("PRAGMA table_info(order_items)")
    print("\nCurrent order_items table schema:")
    for row in cursor.fetchall():
        print(f"  {row[1]} - {row[2]}")
    
    conn.close()
    print("\n✓ Migration complete")
    
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
