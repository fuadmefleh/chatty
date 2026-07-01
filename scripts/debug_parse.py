#!/usr/bin/env python3
import sys
sys.path.insert(0, '/home/edgeworks-server/chatty/skills/walmart_orders')

from walmart_parser import WalmartPDFParser

xlsx_path = '/home/edgeworks-server/chatty/data/walmart/Walmart_Orders (3).xlsx'

parser = WalmartPDFParser()

try:
    orders_list = parser.parse_multirow_xlsx(xlsx_path)
    print(f'Parsed {len(orders_list)} orders\n')
    
    for order_data, items in orders_list:
        print(f"Order ID: {order_data['order_id']}")
        print(f"Order Date: {order_data['order_date']}")
        print(f"Total: ${order_data['total_amount']:.2f}")
        print(f"Filename: {order_data['pdf_filename']}")
        print(f"Items count: {len(items)}")
        print(f"\nFirst 5 items:")
        for i, item in enumerate(items[:5]):
            print(f"  {i+1}. {item['name'][:50]}")
            print(f"     Qty: {item['quantity']}, Price: ${item['total_price']:.2f}, Status: {item.get('delivery_status', 'N/A')}")
        
        if len(items) > 5:
            print(f"  ... and {len(items) - 5} more items")
            
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
