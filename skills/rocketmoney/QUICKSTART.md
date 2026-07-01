# Rocket Money Parser - Quick Reference

## 📁 Files Created

```
skills/rocketmoney/
├── rocketmoney_parser.py    # Main parser and database manager
├── query_transactions.py    # Query functions for analysis
├── rocketmoney.md          # Skill definition for the bot
├── test_parser.py          # Test suite
└── README.md               # Full documentation
```

## 🚀 Quick Start

### Import a CSV file:
```bash
python3 skills/rocketmoney/rocketmoney_parser.py data/rocketmoney/YOUR_FILE.csv
```

### Run tests:
```bash
python3 skills/rocketmoney/test_parser.py
```

## 📊 Your Data Summary

From `2026-02-01T01_19_51.598Z-transactions.csv`:
- **164 transactions** imported
- Date range: **December 1-31, 2025**
- Total spending: **$11,589.46**
- **20 unique categories**
- **3 institutions** (Capital One, Wells Fargo, Chase)

### Top Spending Categories:
1. Loan Payment: $4,415.18
2. Amazon Shopping: $1,531.85
3. Groceries: $1,467.25
4. Shopping: $811.28
5. Travel & Vacation: $649.37

### Top Merchants:
1. Mortgage/Loan: $3,716.56
2. Walmart: $905.39 (24 transactions)
3. Air Canada: $649.37
4. Auto Finance: $504.21
5. Amazon: $475.87

## 💬 Bot Commands

Once integrated, you can ask the bot:
- "Import this Rocket Money CSV"
- "Show me my December spending"
- "How much did I spend on groceries?"
- "What are my top spending categories?"
- "Show me all Walmart transactions"
- "How much did I spend at Amazon?"
- "What's my total spending for 2025?"

## 🗄️ Database Location

- Production: `data/rocketmoney/rocketmoney_transactions.db`
- Test: `data/rocketmoney/test_transactions.db`

## 🔍 Key Features

✅ Automatic duplicate detection  
✅ Multi-account support (Credit Cards, Checking, Savings)  
✅ Category-based spending analysis  
✅ Merchant tracking  
✅ Date range queries  
✅ Full-text search  
✅ Monthly/yearly summaries  
✅ Top expenses tracking  

## 📝 Next Steps

1. **Regular Imports**: Export CSV from Rocket Money monthly
2. **Bot Integration**: The bot can now parse these CSVs automatically
3. **Analysis**: Use query functions to analyze spending patterns
4. **Tracking**: Monitor categories, merchants, and accounts over time

## 🛠️ Python Usage

```python
from skills.rocketmoney.rocketmoney_parser import RocketMoneyDB

# Initialize
db = RocketMoneyDB()

# Import CSV
result = db.import_csv("data/rocketmoney/transactions.csv")

# Query recent transactions
transactions = db.get_all_transactions(limit=10)

# Get spending by category
categories = db.get_spending_by_category()

# Search transactions
walmart = db.search_transactions("Walmart")

# Get monthly total
total = db.get_total_spending("2025-12-01", "2025-12-31")

db.close()
```

## ✨ What's Different from Other Parsers?

Unlike Amazon/Walmart parsers that parse PDFs:
- This parser handles **CSV exports** from Rocket Money
- Supports **multiple accounts** across institutions
- Includes **pre-categorized** transactions
- Tracks **all spending** (not just one retailer)
- No PDF parsing required - clean CSV format
