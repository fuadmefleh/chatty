"""Test the Rocket Money CSV parser."""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))
from rocketmoney_parser import RocketMoneyDB


def test_basic_parsing():
    """Test basic CSV parsing functionality."""
    print("=" * 60)
    print("TEST: Basic CSV Parsing")
    print("=" * 60)
    
    # Find a test CSV file
    csv_path = Path("data/rocketmoney/2026-02-01T01_19_51.598Z-transactions.csv")
    
    if not csv_path.exists():
        print(f"❌ Test CSV not found: {csv_path}")
        return False
    
    try:
        db = RocketMoneyDB()
        result = db.parse_csv(str(csv_path))
        
        print(f"✓ CSV parsed successfully")
        print(f"  File: {result['csv_filename']}")
        print(f"  Total transactions: {result['total_transactions']}")
        print(f"  Skipped: {result['skipped']}")
        
        if result['total_transactions'] > 0:
            print(f"\n  Sample transaction:")
            sample = result['transactions'][0]
            print(f"    Date: {sample['date']}")
            print(f"    Merchant: {sample['name']}")
            print(f"    Amount: ${sample['amount']:.2f}")
            print(f"    Category: {sample['category']}")
            print(f"    Account: {sample['account_name']}")
        
        db.close()
        return True
        
    except Exception as e:
        print(f"❌ Error parsing CSV: {e}")
        return False


def test_database_import():
    """Test importing CSV into database."""
    print("\n" + "=" * 60)
    print("TEST: Database Import")
    print("=" * 60)
    
    csv_path = Path("data/rocketmoney/2026-02-01T01_19_51.598Z-transactions.csv")
    
    if not csv_path.exists():
        print(f"❌ Test CSV not found: {csv_path}")
        return False
    
    try:
        # Use a test database
        db = RocketMoneyDB(db_path="data/rocketmoney/test_transactions.db")
        
        # Import the CSV
        result = db.import_csv(str(csv_path))
        
        print(f"✓ CSV imported successfully")
        print(f"  Added: {result['added']}")
        print(f"  Duplicates: {result['duplicates']}")
        print(f"  Skipped: {result['skipped']}")
        
        # Try importing again to test duplicate detection
        result2 = db.import_csv(str(csv_path))
        print(f"\n✓ Re-import test (should show all duplicates)")
        print(f"  Added: {result2['added']}")
        print(f"  Duplicates: {result2['duplicates']}")
        
        db.close()
        return True
        
    except Exception as e:
        print(f"❌ Error importing to database: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_queries():
    """Test database query functions."""
    print("\n" + "=" * 60)
    print("TEST: Database Queries")
    print("=" * 60)
    
    try:
        db = RocketMoneyDB(db_path="data/rocketmoney/test_transactions.db")
        
        # Test: Get statistics
        print("\n1. Database Statistics:")
        stats = db.get_statistics()
        print(f"   Total transactions: {stats['total_transactions']}")
        print(f"   Date range: {stats['date_range']['earliest']} to {stats['date_range']['latest']}")
        print(f"   Total amount: ${stats['total_amount']:,.2f}")
        print(f"   Unique categories: {stats['unique_categories']}")
        print(f"   Unique institutions: {stats['unique_institutions']}")
        
        # Test: Get recent transactions
        print("\n2. Recent Transactions (5):")
        recent = db.get_all_transactions(limit=5)
        for t in recent:
            print(f"   {t['date']} | {t['name'][:30]:30s} | ${t['amount']:>8.2f} | {t['category']}")
        
        # Test: Spending by category
        print("\n3. Spending by Category (Top 5):")
        categories = db.get_spending_by_category()
        for i, (category, amount) in enumerate(list(categories.items())[:5], 1):
            print(f"   {i}. {category:30s} ${amount:>10.2f}")
        
        # Test: Top merchants
        print("\n4. Top Merchants (Top 5):")
        merchants = db.get_spending_by_merchant(limit=5)
        for i, merchant in enumerate(merchants, 1):
            print(f"   {i}. {merchant['name'][:30]:30s} ${merchant['total']:>10.2f} ({merchant['transaction_count']} txns)")
        
        # Test: Search
        print("\n5. Search for 'Walmart':")
        results = db.search_transactions("Walmart")
        print(f"   Found {len(results)} transactions")
        for t in results[:3]:
            print(f"   {t['date']} | {t['name'][:30]:30s} | ${t['amount']:>8.2f}")
        
        # Test: Date range query
        print("\n6. December 2025 Transactions:")
        dec_transactions = db.get_transactions_by_date_range("2025-12-01", "2025-12-31")
        total_dec = sum(t['amount'] for t in dec_transactions)
        print(f"   Count: {len(dec_transactions)}")
        print(f"   Total: ${total_dec:,.2f}")
        
        db.close()
        return True
        
    except Exception as e:
        print(f"❌ Error running queries: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\n" + "🚀" * 30)
    print("ROCKET MONEY PARSER TEST SUITE")
    print("🚀" * 30 + "\n")
    
    results = []
    
    # Run tests
    results.append(("Basic Parsing", test_basic_parsing()))
    results.append(("Database Import", test_database_import()))
    results.append(("Database Queries", test_queries()))
    
    # Print summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASSED" if result else "❌ FAILED"
        print(f"{status} - {test_name}")
    
    print(f"\n{passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed!")
        return 0
    else:
        print("⚠️  Some tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
