# Walmart Orders Import Script

Quick guide for importing new Walmart order XLSX files into the database.

## Usage

### Import all XLSX files from a directory
```bash
./skills/walmart_orders/import_walmart_orders.sh -d data/walmart
```

### Import with verbose output
```bash
./skills/walmart_orders/import_walmart_orders.sh -d data/walmart -v
```

### Import specific files
```bash
./skills/walmart_orders/import_walmart_orders.sh file1.xlsx file2.xlsx
```

### Show help
```bash
./skills/walmart_orders/import_walmart_orders.sh -h
```

## Supported Formats

The script automatically detects and handles multiple XLSX formats:

1. **Single-order format**: One XLSX file per order with summary and items sections
2. **Multi-row format (Type 1)**: Multiple orders with one row per item
   - Columns: Order Number, Order Date, Subtotal, Order Total, Product Name, Quantity, Price, Delivery Status
3. **Multi-row format (Type 2)**: Multiple orders with additional fields
   - Columns: Order Number, Order Date, Shipping Address, Payment Method, Subtotal, Order Total, Product Name, Quantity, Price

## What It Does

- Automatically categorizes items (Food, Beverages, Household, etc.)
- Converts dates to ISO format (YYYY-MM-DD) for proper sorting
- Calculates unit prices from quantity and total price
- Updates existing orders if re-imported (uses order ID as primary key)
- Stores all data in SQLite database: `data/walmart/walmart_orders.db`

## Examples

```bash
# Import newly downloaded orders
./skills/walmart_orders/import_walmart_orders.sh -d ~/Downloads -v

# Re-import to update existing orders
./skills/walmart_orders/import_walmart_orders.sh data/walmart/Walmart_Orders.xlsx
```
