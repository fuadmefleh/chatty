# Rocket Money Transaction Parser

Parse Rocket Money CSV transaction exports and store them in a SQLite database for easy querying and analysis.

## Features

- 📊 Parse Rocket Money CSV exports
- 💾 Store transactions in SQLite database
- 🔍 Query by date, category, merchant, or account
- 📈 Analyze spending patterns and trends
- 🔄 Automatic duplicate detection
- 🏦 Multi-account support
- 🏷️ Category-based spending analysis

## Installation

No additional dependencies required beyond the base project requirements.

## Quick Start

### 1. Import a CSV File

```bash
# From the project root
python skills/rocketmoney/rocketmoney_parser.py data/rocketmoney/2026-02-01T01_19_51.598Z-transactions.csv
```

This will:
- Parse the CSV file
- Import all transactions into the database
- Skip duplicates automatically
- Display import statistics

### 2. Run Tests

```bash
python skills/rocketmoney/test_parser.py
```

## Usage Examples

### Import from Python

```python
from skills.rocketmoney.rocketmoney_parser import RocketMoneyDB

# Initialize database
db = RocketMoneyDB()

# Import a CSV file
result = db.import_csv("data/rocketmoney/transactions.csv")
print(f"Added {result['added']} transactions")
print(f"Skipped {result['duplicates']} duplicates")

# Get recent transactions
transactions = db.get_all_transactions(limit=10)

# Search for transactions
walmart_txns = db.search_transactions("Walmart")

# Get spending by category
categories = db.get_spending_by_category(
    start_date="2025-12-01", 
    end_date="2025-12-31"
)

# Get top merchants
top_merchants = db.get_spending_by_merchant(limit=10)

# Get total spending for a period
total = db.get_total_spending(
    start_date="2025-12-01",
    end_date="2025-12-31"
)

db.close()
```

### Query Functions

```python
from skills.rocketmoney.query_transactions import *

# Get monthly spending summary
result = await get_monthly_spending(2025, 12)
print(f"December 2025: ${result['total_spent']:,.2f}")

# Get spending by category
groceries = await get_spending_by_category("Groceries")
print(f"Grocery spending: ${groceries['total_spent']:,.2f}")

# Get merchant analysis
walmart = await get_merchant_spending("Walmart")
print(f"Walmart total: ${walmart['total_spent']:,.2f}")

# Get spending trends (last 6 months)
trends = await get_spending_trends(months=6)

# Search transactions
results = await search_transactions("Amazon")

# Get account summary
accounts = await get_account_summary()

# Get top expenses
top = await get_top_expenses(limit=20)

# Get database statistics
stats = await get_database_stats()
```

## CSV Format

The parser expects Rocket Money CSV exports with these columns:

| Column | Description |
|--------|-------------|
| Date | Transaction date (YYYY-MM-DD) |
| Original Date | Original transaction date |
| Account Type | Type of account (Credit Card, Cash, etc.) |
| Account Name | Name of the account |
| Account Number | Last 4 digits of account |
| Institution Name | Bank/institution name |
| Name | Merchant name |
| Custom Name | User-defined merchant name |
| Amount | Transaction amount |
| Description | Transaction description |
| Category | Rocket Money category |
| Note | User notes |
| Ignored From | Whether ignored from budgets |
| Tax Deductible | Tax deductible flag |
| Transaction Tags | User-defined tags |

## Database Schema

### Transactions Table

```sql
CREATE TABLE transactions (
    id INTEGER PRIMARY KEY,
    date TEXT NOT NULL,
    original_date TEXT,
    account_type TEXT,
    account_name TEXT,
    account_number TEXT,
    institution_name TEXT,
    name TEXT,                    -- Merchant name
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
);
```

## Database Location

- Default: `data/rocketmoney/rocketmoney_transactions.db`
- Test: `data/rocketmoney/test_transactions.db`

## Query Examples

### Monthly spending
```python
db.get_transactions_by_date_range("2025-12-01", "2025-12-31")
```

### Category analysis
```python
db.get_transactions_by_category("Groceries")
db.get_spending_by_category()  # All categories
```

### Merchant search
```python
db.search_transactions("Walmart")
db.get_spending_by_merchant(limit=10)  # Top 10 merchants
```

### Statistics
```python
stats = db.get_statistics()
# Returns: total_transactions, date_range, total_amount, 
#          unique_categories, unique_institutions
```

## Integration with Bot

The bot can use this parser when you send CSV files:

- "Import this Rocket Money CSV"
- "Show me my spending for December"
- "How much did I spend on groceries?"
- "What are my top merchants?"
- "Find all Amazon transactions"

## Error Handling

- **Duplicate Detection**: Transactions are uniquely identified by (date, account, merchant, amount, description)
- **Missing Fields**: Empty fields are stored as empty strings or 0.0 for amounts
- **Invalid Amounts**: Non-numeric amounts default to 0.0
- **File Not Found**: Raises FileNotFoundError with clear message

## Performance

- Batch imports are transaction-safe (rollback on error)
- Indexed on: date, category, institution_name, account_name
- Handles thousands of transactions efficiently
- Duplicate checking uses unique constraint (fast)

## Tips

1. **Regular Imports**: Import your CSV exports regularly to keep data up-to-date
2. **Backup**: The database file is just a file - back it up regularly
3. **Date Format**: Ensure dates are in YYYY-MM-DD format in CSVs
4. **Categories**: Use Rocket Money's categories for consistent tracking
5. **Search**: Use partial names when searching (e.g., "Wal" finds "Walmart")

## Troubleshooting

### Import shows 0 added transactions
- Check if transactions were already imported (duplicates)
- Verify CSV file format matches expected columns

### Database locked error
- Make sure to close database connections: `db.close()`
- Only one connection should write at a time

### Wrong totals
- Check date ranges in queries
- Verify amount field is numeric in CSV

## Future Enhancements

Possible additions:
- Budget tracking against categories
- Recurring transaction detection
- Anomaly detection for unusual spending
- Export to different formats
- Category auto-correction
- Bill payment tracking
- Subscription detection
