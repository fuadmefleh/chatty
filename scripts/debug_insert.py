#!/usr/bin/env python3
import sys
sys.path.insert(0, '/home/edgeworks-server/chatty/skills/walmart_orders')

from walmart_parser import WalmartPDFParser, WalmartOrderDB

xlsx_path = '/home/edgeworks-server/chatty/data/walmart/Walmart_Orders (3).xlsx'

parser = WalmartPDFParser()
db = WalmartOrderDB()

try:
    orders_list = parser.parse_multirow_xlsx(xlsx_path)
    print(f'Parsed {len(orders_list)} orders\n')
    
    for order_data, items in orders_list:
        print(f"Inserting order: {order_data['order_id']}")
        db.insert_order(order_data, items)
        print(f"✓ Successfully inserted\n")
        
        # Verify it's in the database
        retrieved = db.get_order(order_data['order_id'])
        if retrieved:
            print(f"✓ Verified in database")
            print(f"  Items count: {len(retrieved['items'])}")
            print(f"  First item: {retrieved['items'][0]['name'][:50]}")
            print(f"  First item delivery status: {retrieved['items'][0].get('delivery_status', 'N/A')}")
        else:
            print(f"✗ NOT found in database after insertion!")
            
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
