"""Amazon Orders skill tools for LLM function calling.

These tools are dynamically loaded by the framework when the skill is activated.
"""
import json
import sys
import importlib.util
from pathlib import Path

# Add project root to path for src imports
project_root = str(Path(__file__).parent.parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.core.skill_tool import SkillTool

# Load the query_orders module from THIS skill folder explicitly
_query_orders_path = Path(__file__).parent / "query_orders.py"
_spec = importlib.util.spec_from_file_location("amazon_query_orders", _query_orders_path)
_query_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_query_module)

# Import functions from the loaded module
get_monthly_spending = _query_module.get_monthly_spending
get_recent_orders = _query_module.get_recent_orders
search_amazon_items = _query_module.search_amazon_items
get_spending_by_category = _query_module.get_spending_by_category
get_items_by_category = _query_module.get_items_by_category


class GetMonthlyAmazonSpending(SkillTool):
    """Get total amount spent on Amazon for a specific month."""
    
    name = "get_monthly_amazon_spending"
    description = "Get total amount spent on Amazon for a specific month. Use this when user asks 'how much did I spend on amazon in december' or similar questions about monthly Amazon spending."
    parameters = {
        "type": "object",
        "properties": {
            "year": {
                "type": "integer",
                "description": "Year (e.g., 2025)"
            },
            "month": {
                "type": "integer",
                "description": "Month number (1-12, where 1=January, 12=December)"
            }
        },
        "required": ["year", "month"]
    }
    
    async def execute(self, year: int, month: int) -> str:
        result = await get_monthly_spending(year, month)
        return json.dumps(result, indent=2)


class GetRecentAmazonOrders(SkillTool):
    """Get recent Amazon orders with dates and amounts."""
    
    name = "get_recent_amazon_orders"
    description = "Get recent Amazon orders with dates, order numbers, and total amounts. Useful for viewing order history."
    parameters = {
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "description": "Maximum number of orders to return (default: 10)"
            }
        },
        "required": []
    }
    
    async def execute(self, limit: int = 10) -> str:
        result = await get_recent_orders(limit)
        return json.dumps(result, indent=2)


class SearchAmazonItems(SkillTool):
    """Search for specific items purchased on Amazon by name."""
    
    name = "search_amazon_items"
    description = "Search for items purchased on Amazon by name. Useful when user wants to find specific products they bought."
    parameters = {
        "type": "object",
        "properties": {
            "search_term": {
                "type": "string",
                "description": "Term to search for in item names (e.g., 'laptop', 'vitamins', 'headphones')"
            }
        },
        "required": ["search_term"]
    }
    
    async def execute(self, search_term: str) -> str:
        result = await search_amazon_items(search_term)
        return json.dumps(result, indent=2)


class GetAmazonSpendingByCategory(SkillTool):
    """Get Amazon spending broken down by category."""
    
    name = "get_amazon_spending_by_category"
    description = "Get Amazon spending broken down by category (e.g., Electronics, Food, Health). Useful for analyzing spending patterns."
    parameters = {
        "type": "object",
        "properties": {
            "start_date": {
                "type": "string",
                "description": "Optional start date filter (format: 'January 1, 2025')"
            },
            "end_date": {
                "type": "string",
                "description": "Optional end date filter (format: 'December 31, 2025')"
            }
        },
        "required": []
    }
    
    async def execute(self, start_date: str = None, end_date: str = None) -> str:
        result = await get_spending_by_category(start_date, end_date)
        return json.dumps(result, indent=2)


class GetAmazonItemsByCategory(SkillTool):
    """Get all items purchased on Amazon in a specific category."""
    
    name = "get_amazon_items_by_category"
    description = "Get all items purchased on Amazon in a specific category (e.g., 'Electronics', 'Food', 'Health', 'Home', 'Books')."
    parameters = {
        "type": "object",
        "properties": {
            "category": {
                "type": "string",
                "description": "Category name (e.g., 'Electronics', 'Food', 'Health', 'Home', 'Books')"
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of items to return (default: 50)"
            }
        },
        "required": ["category"]
    }
    
    async def execute(self, category: str, limit: int = 50) -> str:
        result = await get_items_by_category(category, limit)
        return json.dumps(result, indent=2)
