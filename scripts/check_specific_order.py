#!/usr/bin/env python3
import sqlite3

conn = sqlite3.connect('data/walmart/walmart_orders.db')
cursor = conn.cursor()

# Get orders from the specific file
cursor.execute('''
    SELECT order_id, order_date, total_amount 
    FROM orders 
    WHERE pdf_filename = "Walmart_Orders (3).xlsx"
    ORDER BY order_date DESC
''')

print('Orders from Walmart_Orders (3).xlsx:')
for row in cursor.fetchall():
    print(f'  {row[0]} - {row[1]} - ${row[2]:.2f}')

# Pick the first one
cursor.execute('''
    SELECT order_id 
    FROM orders 
    WHERE pdf_filename = "Walmart_Orders (3).xlsx"
    LIMIT 1
''')

recent_order = cursor.fetchone()

if recent_order:
    order_id = recent_order[0]
    print(f'\nChecking order: {order_id}\n')
    
    cursor.execute('''
        SELECT item_name, quantity, total_price, delivery_status 
        FROM order_items 
        WHERE order_id = ?
        LIMIT 10
    ''', (order_id,))
    
    print('Items with delivery status:')
    for row in cursor.fetchall():
        print(f'  • {row[0][:50]:<50} | Qty: {row[1]} | ${row[2]:.2f} | Status: {row[3] or "N/A"}')
    
    # Count items with delivery status
    cursor.execute('SELECT COUNT(*) FROM order_items WHERE order_id = ? AND delivery_status IS NOT NULL', (order_id,))
    count_with_status = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM order_items WHERE order_id = ?', (order_id,))
    total_items = cursor.fetchone()[0]
    
    print(f'\n{count_with_status} out of {total_items} items have delivery status')

conn.close()
