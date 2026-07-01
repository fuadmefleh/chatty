# Amazon Orders

## Description
Read and parse Amazon order PDFs, extracting order information and storing it in a SQLite database. Tracks individual items purchased with quantities, prices, and sellers for future reference and queries.

## Usage
Use this skill when you need to:
- Read an Amazon order PDF
- Extract order details (items, prices, dates, order numbers)
- Store order information and item details in the database
- Query past orders and items
- Search for specific items purchased
- Get statistics about purchases
- View spending by category

## Examples
- "Read the Amazon order PDF Order Details.pdf"
- "Parse all Amazon order PDFs in the data/amazon folder"
- "Show me my recent Amazon orders"
- "What items did I buy in my last Amazon order?"
- "How much have I spent on Amazon this month?"
- "Search for melatonin in my Amazon orders"
- "Show me all items I've purchased on Amazon"
- "What's my Amazon spending by category?"

## Features
- Automatic categorization of items (Food, Electronics, Health, etc.)
- Tracks seller information for each item
- Supports Subscribe & Save and discount tracking
- SQLite database for persistent storage
- Search and query capabilities
- Spending analytics by category
