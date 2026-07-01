#!/usr/bin/env python3
import sqlite3

conn = sqlite3.connect('data/walmart/walmart_orders.db')
cursor = conn.cursor()

# Get all unique filenames
cursor.execute('''
    SELECT DISTINCT pdf_filename 
    FROM orders 
    ORDER BY pdf_filename DESC
    LIMIT 20
''')

print('Recent filenames in database:')
for row in cursor.fetchall():
    print(f'  "{row[0]}"')

# Get most recently updated orders by parsed_date
cursor.execute('''
    SELECT order_id, order_date, pdf_filename, parsed_date
    FROM orders 
    ORDER BY parsed_date DESC 
    LIMIT 5
''')

print('\n\nMost recently updated orders:')
for row in cursor.fetchall():
    print(f'  {row[0]} | {row[1]} | {row[2]} | {row[3]}')

conn.close()
