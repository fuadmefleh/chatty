# Amazon Orders Parser

This skill parses Amazon order PDFs and stores order information in a SQLite database.

## Files

- **amazon_parser.py**: Main parser with database operations
  - `AmazonOrderDB`: Database manager class
  - `AmazonPDFParser`: PDF parsing class
  - `execute()`: Main execution function

- **query_orders.py**: Query functions for the database
  - `get_monthly_spending()`: Get spending for a specific month
  - `get_recent_orders()`: Get recent orders
  - `search_amazon_items()`: Search for specific items
  - `get_spending_by_category()`: Get spending breakdown by category
  - `get_items_by_category()`: Get items in a specific category

- **test_parser.py**: Test script to verify parser functionality

- **amazon_orders.md**: Skill documentation

## Database Schema

### orders table
- order_id (PRIMARY KEY)
- order_date
- total_amount
- subtotal
- tax
- shipping
- discounts
- pdf_filename
- parsed_date
- raw_text

### order_items table
- id (PRIMARY KEY)
- order_id (FOREIGN KEY)
- item_name
- quantity
- unit_price
- total_price
- category
- seller

## Categories

Items are automatically categorized into:
- Food
- Beverages
- Health
- Baby & Kids
- Personal Care
- Household
- Kitchen Supplies
- Pet Supplies
- Electronics
- Books & Media
- Clothing
- Home & Garden
- Sports & Outdoors
- Other

## Usage

```python
from skills.amazon_orders.amazon_parser import execute

# Parse a PDF
result = await execute(pdf_path="Order Details.pdf", action="parse")

# List all orders
result = await execute(action="list")

# Get statistics
result = await execute(action="stats")

# Search items
result = await execute(pdf_path="search term", action="items")

# Query specific order
result = await execute(pdf_path="111-4885763-3841027", action="query")
```

## Testing

Run the test script:
```bash
python3 skills/amazon_orders/test_parser.py
```
