"""Query tools for Walmart orders database."""
from typing import Dict, Any
from pathlib import Path
import sys

# Add parent directory to path to import walmart_parser
sys.path.insert(0, str(Path(__file__).parent))
from walmart_parser import WalmartOrderDB


async def get_monthly_spending(year: int, month: int) -> Dict[str, Any]:
    """Get total spending for a specific month.
    
    Args:
        year: Year (e.g., 2026)
        month: Month number (1-12)
    
    Returns:
        Dictionary with total spent, order count, and order details
    """
    db = WalmartOrderDB()
    try:
        # Get all orders and filter by month
        all_orders = db.get_all_orders(limit=1000)
        
        # Filter orders for the specified month
        month_orders = []
        total_spent = 0.0
        
        for order in all_orders:
            order_date = order['order_date']
            # Parse date (format: "Jan 29, 2026" or similar)
            try:
                # Try parsing the date
                if order_date:
                    # Check if it matches our target month/year
                    if f"{year}" in order_date:
                        # Parse month name
                        month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                                      'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
                        if month <= len(month_names):
                            month_name = month_names[month - 1]
                            if order_date.startswith(month_name):
                                month_orders.append(order)
                                total_spent += order['total_amount'] or 0.0
            except Exception as e:
                print(f"Error parsing date {order_date}: {e}")
                continue
        
        return {
            "success": True,
            "month": f"{month}/{year}",
            "total_spent": round(total_spent, 2),
            "order_count": len(month_orders),
            "orders": month_orders
        }
    finally:
        db.close()


async def get_recent_orders(limit: int = 10) -> Dict[str, Any]:
    """Get recent Walmart orders.
    
    Args:
        limit: Maximum number of orders to return
    
    Returns:
        Dictionary with recent orders
    """
    db = WalmartOrderDB()
    try:
        orders = db.get_all_orders(limit=limit)
        total = sum(o['total_amount'] or 0 for o in orders)
        
        return {
            "success": True,
            "orders": orders,
            "count": len(orders),
            "total_spent": round(total, 2)
        }
    finally:
        db.close()


async def search_walmart_items(search_term: str) -> Dict[str, Any]:
    """Search for items purchased at Walmart.
    
    Args:
        search_term: Term to search for in item names
    
    Returns:
        Dictionary with matching items and purchase history
    """
    db = WalmartOrderDB()
    try:
        items = db.search_items(search_term)
        
        return {
            "success": True,
            "search_term": search_term,
            "items": items,
            "count": len(items)
        }
    finally:
        db.close()


async def get_order_details(order_id: str) -> Dict[str, Any]:
    """Get details for a specific order including all items.
    
    Args:
        order_id: Walmart order ID
    
    Returns:
        Dictionary with complete order details and items
    """
    db = WalmartOrderDB()
    try:
        order = db.get_order(order_id)
        
        if order:
            return {
                "success": True,
                "order": order
            }
        else:
            return {
                "success": False,
                "error": f"Order {order_id} not found"
            }
    finally:
        db.close()


async def get_spending_by_category(start_date: str = None, end_date: str = None) -> Dict[str, Any]:
    """Get spending breakdown by category.
    
    Args:
        start_date: Optional start date (e.g., "Jan 1, 2026")
        end_date: Optional end date (e.g., "Jan 31, 2026")
    
    Returns:
        Dictionary with spending by category
    """
    db = WalmartOrderDB()
    try:
        categories = db.get_spending_by_category(start_date, end_date)
        total_spent = sum(cat['total_spent'] for cat in categories)
        
        return {
            "success": True,
            "categories": categories,
            "total_spent": round(total_spent, 2),
            "date_range": f"{start_date or 'beginning'} to {end_date or 'now'}"
        }
    finally:
        db.close()


async def get_items_by_category(category: str, limit: int = 50) -> Dict[str, Any]:
    """Get all items in a specific category.
    
    Args:
        category: Category name (Food, Beverages, Household, Kitchen Supplies, 
                 Personal Care, Pet Supplies, Health, Baby & Kids, Other)
        limit: Maximum number of items to return
    
    Returns:
        Dictionary with items in the category
    """
    db = WalmartOrderDB()
    try:
        items = db.get_items_by_category(category, limit)
        total_spent = sum(item['total_price'] or 0 for item in items)
        
        return {
            "success": True,
            "category": category,
            "items": items,
            "count": len(items),
            "total_spent": round(total_spent, 2)
        }
    finally:
        db.close()

