"""Query tools for Amazon orders database."""
from typing import Dict, Any
from pathlib import Path
import sys

# Add parent directory to path to import amazon_parser
sys.path.insert(0, str(Path(__file__).parent))
from amazon_parser import AmazonOrderDB


async def get_monthly_spending(year: int, month: int) -> Dict[str, Any]:
    """Get total spending for a specific month.
    
    Args:
        year: Year (e.g., 2026)
        month: Month number (1-12)
    
    Returns:
        Dictionary with total spent, order count, and order details
    """
    db = AmazonOrderDB()
    try:
        # Get all orders and filter by month
        all_orders = db.get_all_orders(limit=1000)
        
        # Filter orders for the specified month
        month_orders = []
        total_spent = 0.0
        
        for order in all_orders:
            order_date = order['order_date']
            # Parse date (format: "January 16, 2026" or similar)
            try:
                if order_date:
                    # Check if it matches our target month/year
                    if f"{year}" in order_date:
                        # Parse month name
                        month_names = ['January', 'February', 'March', 'April', 'May', 'June',
                                      'July', 'August', 'September', 'October', 'November', 'December']
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
    """Get recent Amazon orders.
    
    Args:
        limit: Maximum number of orders to return
    
    Returns:
        Dictionary with recent orders
    """
    db = AmazonOrderDB()
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


async def search_amazon_items(search_term: str) -> Dict[str, Any]:
    """Search for items purchased on Amazon.
    
    Args:
        search_term: Term to search for in item names
    
    Returns:
        Dictionary with matching items and purchase history
    """
    db = AmazonOrderDB()
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


async def get_spending_by_category(start_date: str = None, end_date: str = None) -> Dict[str, Any]:
    """Get Amazon spending broken down by category.
    
    Args:
        start_date: Optional start date filter (format: "January 1, 2026")
        end_date: Optional end date filter
    
    Returns:
        Dictionary with spending by category
    """
    db = AmazonOrderDB()
    try:
        categories = db.get_spending_by_category(start_date, end_date)
        total = sum(c['total_spent'] for c in categories)
        
        return {
            "success": True,
            "categories": categories,
            "total_spent": round(total, 2),
            "date_range": {"start": start_date, "end": end_date} if start_date else None
        }
    finally:
        db.close()


async def get_items_by_category(category: str, limit: int = 50) -> Dict[str, Any]:
    """Get all items in a specific category.
    
    Args:
        category: Category name
        limit: Maximum number of items to return
    
    Returns:
        Dictionary with items in the category
    """
    db = AmazonOrderDB()
    try:
        items = db.get_items_by_category(category, limit)
        
        return {
            "success": True,
            "category": category,
            "items": items,
            "count": len(items)
        }
    finally:
        db.close()
