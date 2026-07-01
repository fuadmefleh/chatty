#!/usr/bin/env python3
"""
Import Amazon order history CSV files into the database.

Usage:
    python import_amazon_csv.py                          # Import all CSV files in data/amazon/
    python import_amazon_csv.py <file.csv>               # Import specific CSV file
    python import_amazon_csv.py --skip-archive           # Import without moving to archived/
"""

import sys
import asyncio
from pathlib import Path
from typing import List


def get_csv_files(directory: Path) -> List[Path]:
    """Get all CSV files in a directory."""
    return [f for f in directory.glob("*.csv") if f.is_file()]


async def import_csv(csv_path: Path, skip_archive: bool = False):
    """Import a single CSV file."""
    # Import here to avoid circular dependencies
    sys.path.insert(0, str(Path(__file__).parent))
    from skills.amazon_orders.amazon_parser import execute
    
    print(f"\n{'='*60}")
    print(f"Importing: {csv_path.name}")
    print(f"{'='*60}")
    
    # Convert to absolute path to avoid path resolution issues
    csv_path_abs = csv_path.resolve()
    
    # Use the existing execute function with CSV support
    result = await execute(
        pdf_path=str(csv_path_abs),
        action="parse",
        use_vision=False  # CSV doesn't need vision API
    )
    
    if result.get("success"):
        print(f"✓ Successfully imported {result.get('orders_parsed', 0)} orders")
        
        if result.get('errors'):
            print(f"\n⚠ Warnings/Errors ({len(result['errors'])} items):")
            for error in result['errors'][:5]:  # Show first 5 errors
                print(f"  - Order {error.get('order_id', 'unknown')}: {error.get('error', 'unknown error')}")
            if len(result['errors']) > 5:
                print(f"  ... and {len(result['errors']) - 5} more")
        
        if result.get('archived_path'):
            print(f"✓ File moved to: {result['archived_path']}")
    else:
        print(f"✗ Import failed: {result.get('error', 'Unknown error')}")
        return False
    
    return True


async def main():
    """Main import function."""
    skip_archive = "--skip-archive" in sys.argv
    args = [arg for arg in sys.argv[1:] if not arg.startswith("--")]
    
    # Determine what to import
    if args:
        # Import specific file(s)
        csv_files = []
        for arg in args:
            path = Path(arg)
            if not path.is_absolute():
                # Try relative to current directory
                if not path.exists():
                    # Try relative to data/amazon/
                    path = Path("data/amazon") / arg
            
            if not path.exists():
                print(f"✗ File not found: {arg}")
                continue
            
            if path.suffix.lower() != '.csv':
                print(f"✗ Not a CSV file: {arg}")
                continue
            
            csv_files.append(path)
    else:
        # Import all CSV files in data/amazon/
        amazon_dir = Path("data/amazon")
        if not amazon_dir.exists():
            print(f"✗ Directory not found: {amazon_dir}")
            print("\nPlease ensure the data/amazon directory exists and contains CSV files.")
            return 1
        
        csv_files = get_csv_files(amazon_dir)
        
        if not csv_files:
            print(f"No CSV files found in {amazon_dir}")
            print("\nPlace your Amazon order history CSV files in the data/amazon/ directory.")
            return 1
        
        print(f"Found {len(csv_files)} CSV file(s) to import:")
        for f in csv_files:
            print(f"  - {f.name}")
        
        # Ask for confirmation
        response = input("\nProceed with import? (y/n): ").strip().lower()
        if response not in ['y', 'yes']:
            print("Import cancelled.")
            return 0
    
    # Import each file
    success_count = 0
    fail_count = 0
    
    for csv_file in csv_files:
        try:
            if await import_csv(csv_file, skip_archive):
                success_count += 1
            else:
                fail_count += 1
        except Exception as e:
            print(f"✗ Error importing {csv_file.name}: {e}")
            fail_count += 1
    
    # Summary
    print(f"\n{'='*60}")
    print(f"Import Summary")
    print(f"{'='*60}")
    print(f"Successfully imported: {success_count} file(s)")
    if fail_count > 0:
        print(f"Failed: {fail_count} file(s)")
    print()
    
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
