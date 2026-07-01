#!/usr/bin/env python3
"""Script to import new Walmart XLSX order files into the database."""

import sys
import argparse
from pathlib import Path
from walmart_parser import WalmartPDFParser, WalmartOrderDB


def import_orders(file_paths, verbose=False):
    """Import order files into the database.
    
    Args:
        file_paths: List of file paths to import
        verbose: Print detailed progress
        
    Returns:
        Dictionary with import results
    """
    parser = WalmartPDFParser()
    db = WalmartOrderDB()
    
    results = {
        'success': [],
        'failed': [],
        'total_orders': 0,
        'total_items': 0
    }
    
    for file_path in file_paths:
        path = Path(file_path)
        
        # Convert to absolute path if relative
        if not path.is_absolute():
            path = path.resolve()
        
        if not path.exists():
            results['failed'].append({
                'file': str(file_path),
                'error': 'File not found'
            })
            continue
        
        if path.suffix.lower() != '.xlsx':
            results['failed'].append({
                'file': str(path),
                'error': 'Not an XLSX file'
            })
            continue
        
        try:
            # Check if it's a multi-row format by looking at the first row
            import openpyxl
            wb = openpyxl.load_workbook(str(path))
            ws = wb.active
            first_row = [cell.value for cell in ws[1]]
            
            # Multi-row format has these specific headers
            # Format 1: Order Number, Order Date, Subtotal, Order Total, Product Name...
            is_multirow_format1 = (
                first_row[0] == 'Order Number' and
                first_row[1] == 'Order Date' and
                first_row[4] == 'Product Name'
            )
            
            # Format 2: Order Number, Order Date, Shipping Address, Payment Method, Subtotal, Order Total, Product Name...
            is_multirow_format2 = (
                first_row[0] == 'Order Number' and
                first_row[1] == 'Order Date' and
                len(first_row) > 6 and
                first_row[6] == 'Product Name'
            )
            
            is_multirow = is_multirow_format1 or is_multirow_format2
            
            if is_multirow:
                # Parse multi-row format
                if verbose:
                    print(f"Parsing multi-row file: {path.name}")
                
                orders_list = parser.parse_multirow_xlsx(str(path))
                
                for order_data, items in orders_list:
                    db.insert_order(order_data, items)
                    results['total_items'] += len(items)
                
                results['success'].append({
                    'file': path.name,
                    'orders': len(orders_list),
                    'items': sum(len(items) for _, items in orders_list)
                })
                results['total_orders'] += len(orders_list)
                
                if verbose:
                    print(f"  ✓ Imported {len(orders_list)} orders")
            else:
                # Parse single-order format
                if verbose:
                    print(f"Parsing single order file: {path.name}")
                
                order_data, items = parser.parse_xlsx(str(path))
                
                if not order_data['order_id']:
                    results['failed'].append({
                        'file': path.name,
                        'error': 'Could not extract order ID'
                    })
                    continue
                
                db.insert_order(order_data, items)
                
                results['success'].append({
                    'file': path.name,
                    'orders': 1,
                    'items': len(items),
                    'order_id': order_data['order_id']
                })
                results['total_orders'] += 1
                results['total_items'] += len(items)
                
                if verbose:
                    print(f"  ✓ Imported order {order_data['order_id']} with {len(items)} items")
                
        except Exception as e:
            results['failed'].append({
                'file': path.name,
                'error': str(e)
            })
            if verbose:
                print(f"  ✗ Failed: {e}")
    
    db.close()
    return results


def main():
    parser = argparse.ArgumentParser(
        description='Import Walmart order XLSX files into the database',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Import a single file
  python import_orders.py /path/to/Order_123.xlsx
  
  # Import multiple files
  python import_orders.py order1.xlsx order2.xlsx order3.xlsx
  
  # Import all XLSX files in a directory
  python import_orders.py -d data/walmart
  
  # Import with verbose output
  python import_orders.py -v Walmart_Orders.xlsx
        """
    )
    
    parser.add_argument(
        'files',
        nargs='*',
        help='XLSX file(s) to import'
    )
    
    parser.add_argument(
        '-d', '--dir',
        help='Import all XLSX files from this directory (recursively)'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Print detailed progress information'
    )
    
    args = parser.parse_args()
    
    # Collect files to import
    files_to_import = []
    
    if args.dir:
        # Find all XLSX files in directory
        dir_path = Path(args.dir)
        if not dir_path.exists():
            print(f"Error: Directory not found: {args.dir}")
            sys.exit(1)
        
        files_to_import = list(dir_path.glob('**/*.xlsx'))
        
        if not files_to_import:
            print(f"No XLSX files found in {args.dir}")
            sys.exit(0)
        
        if args.verbose:
            print(f"Found {len(files_to_import)} XLSX files in {args.dir}")
    elif args.files:
        files_to_import = args.files
    else:
        parser.print_help()
        sys.exit(1)
    
    print(f"Importing {len(files_to_import)} file(s)...\n")
    
    results = import_orders(files_to_import, verbose=args.verbose)
    
    # Print summary
    print("\n" + "="*50)
    print("IMPORT SUMMARY")
    print("="*50)
    
    if results['success']:
        print(f"\n✓ Successfully imported {len(results['success'])} file(s):")
        for item in results['success']:
            if 'order_id' in item:
                print(f"  • {item['file']}: Order {item['order_id']} ({item['items']} items)")
            else:
                print(f"  • {item['file']}: {item['orders']} orders ({item['items']} items)")
    
    if results['failed']:
        print(f"\n✗ Failed to import {len(results['failed'])} file(s):")
        for item in results['failed']:
            print(f"  • {item['file']}: {item['error']}")
    
    print(f"\nTotal: {results['total_orders']} orders, {results['total_items']} items")
    print("="*50)
    
    # Exit with error code if any failures
    sys.exit(0 if not results['failed'] else 1)


if __name__ == '__main__':
    main()
