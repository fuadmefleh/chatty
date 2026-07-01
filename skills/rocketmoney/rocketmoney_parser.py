"""Rocket Money CSV parser with SQLite database storage."""

import sqlite3
import csv
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
from decimal import Decimal


class RocketMoneyDB:
    """SQLite database manager for Rocket Money transactions."""
    
    def __init__(self, db_path: str = "data/rocketmoney/rocketmoney_transactions.db"):
        """Initialize database connection."""
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = None
        self.cursor = None
        self._connect()
        self._create_tables()
    
    def _connect(self):
        """Connect to the database."""
        self.conn = sqlite3.connect(str(self.db_path))
        self.cursor = self.conn.cursor()
    
    def _create_tables(self):
        """Create database tables if they don't exist."""
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                original_date TEXT,
                account_type TEXT,
                account_name TEXT,
                account_number TEXT,
                institution_name TEXT,
                name TEXT,
                custom_name TEXT,
                amount REAL,
                description TEXT,
                category TEXT,
                note TEXT,
                ignored_from TEXT,
                tax_deductible TEXT,
                transaction_tags TEXT,
                csv_filename TEXT,
                imported_date TEXT,
                UNIQUE(date, account_name, account_number, name, amount, description)
            )
        """)
        
        # Create indexes for common queries
        self.cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_date ON transactions(date)
        """)
        self.cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_category ON transactions(category)
        """)
        self.cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_institution ON transactions(institution_name)
        """)
        self.cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_account ON transactions(account_name)
        """)
        
        self.conn.commit()
    
    def parse_csv(self, csv_path: str) -> Dict[str, Any]:
        """Parse a Rocket Money CSV file and return transaction data.
        
        Args:
            csv_path: Path to the CSV file
            
        Returns:
            Dictionary containing parsed data and statistics
        """
        csv_file = Path(csv_path)
        if not csv_file.exists():
            raise FileNotFoundError(f"CSV file not found: {csv_path}")
        
        transactions = []
        skipped = 0
        
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                try:
                    # Parse amount
                    amount_str = row.get('Amount', '0').strip()
                    try:
                        amount = float(amount_str) if amount_str else 0.0
                    except ValueError:
                        amount = 0.0
                    
                    transaction = {
                        'date': row.get('Date', '').strip(),
                        'original_date': row.get('Original Date', '').strip(),
                        'account_type': row.get('Account Type', '').strip(),
                        'account_name': row.get('Account Name', '').strip(),
                        'account_number': row.get('Account Number', '').strip(),
                        'institution_name': row.get('Institution Name', '').strip(),
                        'name': row.get('Name', '').strip(),
                        'custom_name': row.get('Custom Name', '').strip(),
                        'amount': amount,
                        'description': row.get('Description', '').strip(),
                        'category': row.get('Category', '').strip(),
                        'note': row.get('Note', '').strip(),
                        'ignored_from': row.get('Ignored From', '').strip(),
                        'tax_deductible': row.get('Tax Deductible', '').strip(),
                        'transaction_tags': row.get('Transaction Tags', '').strip(),
                    }
                    
                    transactions.append(transaction)
                    
                except Exception as e:
                    print(f"Error parsing row: {e}")
                    skipped += 1
                    continue
        
        return {
            'csv_filename': csv_file.name,
            'total_transactions': len(transactions),
            'skipped': skipped,
            'transactions': transactions
        }
    
    def add_transaction(self, transaction: Dict[str, Any], csv_filename: str) -> bool:
        """Add a single transaction to the database.
        
        Args:
            transaction: Dictionary containing transaction data
            csv_filename: Name of the source CSV file
            
        Returns:
            True if added, False if duplicate
        """
        try:
            self.cursor.execute("""
                INSERT INTO transactions (
                    date, original_date, account_type, account_name, account_number,
                    institution_name, name, custom_name, amount, description,
                    category, note, ignored_from, tax_deductible, transaction_tags,
                    csv_filename, imported_date
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                transaction['date'],
                transaction['original_date'],
                transaction['account_type'],
                transaction['account_name'],
                transaction['account_number'],
                transaction['institution_name'],
                transaction['name'],
                transaction['custom_name'],
                transaction['amount'],
                transaction['description'],
                transaction['category'],
                transaction['note'],
                transaction['ignored_from'],
                transaction['tax_deductible'],
                transaction['transaction_tags'],
                csv_filename,
                datetime.now().isoformat()
            ))
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            # Duplicate transaction
            return False
    
    def import_csv(self, csv_path: str) -> Dict[str, Any]:
        """Parse and import a CSV file into the database.
        
        Args:
            csv_path: Path to the CSV file
            
        Returns:
            Dictionary with import statistics
        """
        result = self.parse_csv(csv_path)
        
        added = 0
        duplicates = 0
        
        for transaction in result['transactions']:
            if self.add_transaction(transaction, result['csv_filename']):
                added += 1
            else:
                duplicates += 1
        
        return {
            'csv_filename': result['csv_filename'],
            'total_in_file': result['total_transactions'],
            'added': added,
            'duplicates': duplicates,
            'skipped': result['skipped']
        }
    
    def get_all_transactions(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Get all transactions from the database.
        
        Args:
            limit: Maximum number of transactions to return
            offset: Number of transactions to skip
            
        Returns:
            List of transaction dictionaries
        """
        self.cursor.execute("""
            SELECT * FROM transactions
            ORDER BY date DESC, id DESC
            LIMIT ? OFFSET ?
        """, (limit, offset))
        
        columns = [desc[0] for desc in self.cursor.description]
        transactions = []
        
        for row in self.cursor.fetchall():
            transaction = dict(zip(columns, row))
            transactions.append(transaction)
        
        return transactions
    
    def get_transactions_by_date_range(self, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """Get transactions within a date range.
        
        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            
        Returns:
            List of transaction dictionaries
        """
        self.cursor.execute("""
            SELECT * FROM transactions
            WHERE date BETWEEN ? AND ?
            ORDER BY date DESC, id DESC
        """, (start_date, end_date))
        
        columns = [desc[0] for desc in self.cursor.description]
        transactions = []
        
        for row in self.cursor.fetchall():
            transaction = dict(zip(columns, row))
            transactions.append(transaction)
        
        return transactions
    
    def get_transactions_by_category(self, category: str) -> List[Dict[str, Any]]:
        """Get all transactions for a specific category.
        
        Args:
            category: Category name
            
        Returns:
            List of transaction dictionaries
        """
        self.cursor.execute("""
            SELECT * FROM transactions
            WHERE category = ?
            ORDER BY date DESC, id DESC
        """, (category,))
        
        columns = [desc[0] for desc in self.cursor.description]
        transactions = []
        
        for row in self.cursor.fetchall():
            transaction = dict(zip(columns, row))
            transactions.append(transaction)
        
        return transactions
    
    def get_spending_by_category(self, start_date: Optional[str] = None, 
                                 end_date: Optional[str] = None) -> Dict[str, float]:
        """Get total spending grouped by category.
        
        Args:
            start_date: Optional start date in YYYY-MM-DD format
            end_date: Optional end date in YYYY-MM-DD format
            
        Returns:
            Dictionary mapping category names to total amounts
        """
        if start_date and end_date:
            self.cursor.execute("""
                SELECT category, SUM(amount) as total
                FROM transactions
                WHERE date BETWEEN ? AND ?
                GROUP BY category
                ORDER BY total DESC
            """, (start_date, end_date))
        else:
            self.cursor.execute("""
                SELECT category, SUM(amount) as total
                FROM transactions
                GROUP BY category
                ORDER BY total DESC
            """)
        
        return {row[0]: row[1] for row in self.cursor.fetchall()}
    
    def get_spending_by_merchant(self, start_date: Optional[str] = None,
                                end_date: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
        """Get top merchants by spending.
        
        Args:
            start_date: Optional start date in YYYY-MM-DD format
            end_date: Optional end date in YYYY-MM-DD format
            limit: Maximum number of merchants to return
            
        Returns:
            List of dictionaries with merchant name and total spending
        """
        if start_date and end_date:
            self.cursor.execute("""
                SELECT name, SUM(amount) as total, COUNT(*) as transaction_count
                FROM transactions
                WHERE date BETWEEN ? AND ?
                GROUP BY name
                ORDER BY total DESC
                LIMIT ?
            """, (start_date, end_date, limit))
        else:
            self.cursor.execute("""
                SELECT name, SUM(amount) as total, COUNT(*) as transaction_count
                FROM transactions
                GROUP BY name
                ORDER BY total DESC
                LIMIT ?
            """, (limit,))
        
        merchants = []
        for row in self.cursor.fetchall():
            merchants.append({
                'name': row[0],
                'total': row[1],
                'transaction_count': row[2]
            })
        
        return merchants
    
    def get_total_spending(self, start_date: Optional[str] = None,
                          end_date: Optional[str] = None) -> float:
        """Get total spending for a date range.
        
        Args:
            start_date: Optional start date in YYYY-MM-DD format
            end_date: Optional end date in YYYY-MM-DD format
            
        Returns:
            Total amount spent
        """
        if start_date and end_date:
            self.cursor.execute("""
                SELECT SUM(amount) FROM transactions
                WHERE date BETWEEN ? AND ?
            """, (start_date, end_date))
        else:
            self.cursor.execute("""
                SELECT SUM(amount) FROM transactions
            """)
        
        result = self.cursor.fetchone()[0]
        return result if result else 0.0
    
    def search_transactions(self, query: str) -> List[Dict[str, Any]]:
        """Search transactions by name, description, or category.
        
        Args:
            query: Search query string
            
        Returns:
            List of matching transaction dictionaries
        """
        search_pattern = f"%{query}%"
        self.cursor.execute("""
            SELECT * FROM transactions
            WHERE name LIKE ? OR description LIKE ? OR category LIKE ?
            ORDER BY date DESC, id DESC
            LIMIT 100
        """, (search_pattern, search_pattern, search_pattern))
        
        columns = [desc[0] for desc in self.cursor.description]
        transactions = []
        
        for row in self.cursor.fetchall():
            transaction = dict(zip(columns, row))
            transactions.append(transaction)
        
        return transactions
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get database statistics.
        
        Returns:
            Dictionary with various statistics
        """
        # Total transactions
        self.cursor.execute("SELECT COUNT(*) FROM transactions")
        total_count = self.cursor.fetchone()[0]
        
        # Date range
        self.cursor.execute("SELECT MIN(date), MAX(date) FROM transactions")
        date_range = self.cursor.fetchone()
        
        # Total amount
        self.cursor.execute("SELECT SUM(amount) FROM transactions")
        total_amount = self.cursor.fetchone()[0] or 0.0
        
        # Number of categories
        self.cursor.execute("SELECT COUNT(DISTINCT category) FROM transactions WHERE category != ''")
        category_count = self.cursor.fetchone()[0]
        
        # Number of institutions
        self.cursor.execute("SELECT COUNT(DISTINCT institution_name) FROM transactions WHERE institution_name != ''")
        institution_count = self.cursor.fetchone()[0]
        
        return {
            'total_transactions': total_count,
            'date_range': {
                'earliest': date_range[0],
                'latest': date_range[1]
            },
            'total_amount': total_amount,
            'unique_categories': category_count,
            'unique_institutions': institution_count
        }
    
    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


def main():
    """Example usage."""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python rocketmoney_parser.py <csv_file>")
        sys.exit(1)
    
    csv_path = sys.argv[1]
    
    db = RocketMoneyDB()
    result = db.import_csv(csv_path)
    
    print(f"\nImport Results:")
    print(f"  CSV File: {result['csv_filename']}")
    print(f"  Total in file: {result['total_in_file']}")
    print(f"  Added: {result['added']}")
    print(f"  Duplicates: {result['duplicates']}")
    print(f"  Skipped: {result['skipped']}")
    
    stats = db.get_statistics()
    print(f"\nDatabase Statistics:")
    print(f"  Total transactions: {stats['total_transactions']}")
    print(f"  Date range: {stats['date_range']['earliest']} to {stats['date_range']['latest']}")
    print(f"  Total amount: ${stats['total_amount']:,.2f}")
    print(f"  Unique categories: {stats['unique_categories']}")
    print(f"  Unique institutions: {stats['unique_institutions']}")
    
    db.close()


if __name__ == "__main__":
    main()
