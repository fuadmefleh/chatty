#!/usr/bin/env python3
import sqlite3

conn = sqlite3.connect('data/walmart/walmart_orders.db')
cursor = conn.cursor()

cursor.execute('SELECT COUNT(*) FROM orders')
print(f'Total orders: {cursor.fetchone()[0]}')

cursor.execute('SELECT order_id, order_date, total_amount, delivery_status FROM orders ORDER BY parsed_date DESC LIMIT 5')
print('\nRecent orders:')
for row in cursor.fetchall():
    print(f'  {row}')

cursor.execute('SELECT COUNT(*) FROM order_items')
print(f'\nTotal items: {cursor.fetchone()[0]}')

conn.close()
