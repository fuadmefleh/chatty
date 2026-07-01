#!/usr/bin/env python3
import sqlite3

conn = sqlite3.connect('data/walmart/walmart_orders.db')
cursor = conn.cursor()

# Get the most recently parsed order
cursor.execute('SELECT order_id FROM orders ORDER BY parsed_date DESC LIMIT 1')
recent_order = cursor.fetchone()

if recent_order:
    order_id = recent_order[0]
    print(f'Most recently imported order: {order_id}\n')
    
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
