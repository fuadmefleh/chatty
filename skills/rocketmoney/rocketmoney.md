# Rocket Money Transactions

## Description
Parse Rocket Money CSV transaction exports and store them in a SQLite database. Track all transactions across multiple accounts and institutions with detailed categorization, merchant information, and spending analysis.

## Usage
Use this skill when you need to:
- Import Rocket Money CSV transaction exports
- Store transaction data in a searchable database
- Query transactions by date, category, merchant, or account
- Analyze spending patterns and trends
- Get monthly/yearly spending summaries
- Track expenses by category
- Find transactions from specific merchants
- Get account-level spending summaries

## Examples
- "Import the Rocket Money CSV file 2026-02-01T01_19_51.598Z-transactions.csv"
- "Show me my spending for December 2025"
- "How much did I spend on groceries last month?"
- "What are my top 5 spending categories?"
- "Show me all Walmart transactions"
- "How much have I spent at Amazon this year?"
- "What's my total spending by account?"
- "Find all transactions over $100"
- "Show me my dining expenses for the last 3 months"
- "Get a summary of my spending trends"

## Database Location
Transactions are stored in: `data/rocketmoney/rocketmoney_transactions.db`

## CSV Format
The parser expects Rocket Money CSV exports with the following columns:
- Date
- Original Date
- Account Type
- Account Name
- Account Number
- Institution Name
- Name (Merchant)
- Custom Name
- Amount
- Description
- Category
- Note
- Ignored From
- Tax Deductible
- Transaction Tags

## Features
- Automatic duplicate detection
- Transaction categorization by Rocket Money categories
- Multi-account support
- Date range queries
- Category and merchant analytics
- Spending trends analysis
- Full-text search across transactions
