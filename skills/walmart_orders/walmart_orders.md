# Walmart Orders

## Description
Read and parse Walmart order PDFs, extracting order information and storing it in a SQLite database. Tracks individual items purchased with quantities, unit prices, totals, and **categories** (Food, Beverages, Household, etc.) for future reference and queries.

## Categories
All items are automatically categorized into one of the following:
- **Food**: Groceries, snacks, frozen food, fresh produce, meat, dairy, bakery items
- **Beverages**: Water, juice, soda, milk, coffee, tea, drinks
- **Household**: Cleaning products, paper products, trash bags, laundry supplies
- **Kitchen Supplies**: Cookware, disposable items, foil, storage containers, utensils
- **Personal Care**: Toiletries, hygiene products, cosmetics, hair care
- **Pet Supplies**: Pet food, treats, pet care items
- **Health**: Vitamins, supplements, medications, first aid
- **Baby & Kids**: Baby products, diapers, kid-specific items, toys
- **Other**: Everything else (cards, decorations, electronics, etc.)

## Usage
Use this skill when you need to:
- Read a Walmart order PDF
- Extract order details (items, prices, dates, order numbers)
- Store order information and item details in the database
- Query past orders and items
- Search for specific items purchased
- Get statistics about purchases
- **View spending breakdown by category**
- **Find all items in a specific category**

## Examples
- "Read the Walmart order PDF 2000143-78966231.pdf"
- "Parse all Walmart order PDFs in the data/walmart folder"
- "Show me my recent Walmart orders"
- "What items did I buy in my last Walmart order?"
- "How much have I spent at Walmart this month?"
- "Search for yogurt in my orders"
- "Show me all items I've purchased"
- **"How much did I spend on food vs household items?"**
- **"Show me my spending breakdown by category"**
- **"What beverages have I bought?"**
- **"Show me all the kitchen supplies I purchased"**
