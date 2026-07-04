"""Walmart Orders skill tools for LLM function calling.

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
_spec = importlib.util.spec_from_file_location("walmart_query_orders", _query_orders_path)
_query_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_query_module)

# Import functions from the loaded module
get_monthly_spending = _query_module.get_monthly_spending
get_recent_orders = _query_module.get_recent_orders
search_walmart_items = _query_module.search_walmart_items
get_order_details = _query_module.get_order_details
get_spending_by_category = _query_module.get_spending_by_category
get_items_by_category = _query_module.get_items_by_category


class GetMonthlyWalmartSpending(SkillTool):
    """Get total amount spent at Walmart for a specific month."""
    
    name = "get_monthly_walmart_spending"
    description = "Get total amount spent at Walmart for a specific month. Use this when user asks 'how much have I spent at walmart this month' or similar questions about monthly Walmart spending."
    parameters = {
        "type": "object",
        "properties": {
            "year": {
                "type": "integer",
                "description": "Year (e.g., 2026)"
            },
            "month": {
                "type": "integer",
                "description": "Month number (1-12, where 1=January, 2=February, etc.)"
            }
        },
        "required": ["year", "month"]
    }
    
    async def execute(self, year: int, month: int) -> str:
        result = await get_monthly_spending(year, month)
        return json.dumps(result, indent=2)


class GetRecentWalmartOrders(SkillTool):
    """Get recent Walmart orders with dates and amounts."""
    
    name = "get_recent_walmart_orders"
    description = "Get recent Walmart orders with dates and amounts. Use this when user asks about their recent Walmart purchases."
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


class SearchWalmartItems(SkillTool):
    """Search for specific items purchased at Walmart by name."""
    
    name = "search_walmart_items"
    description = "Search for specific items purchased at Walmart by name. Use this when user asks about specific products they bought."
    parameters = {
        "type": "object",
        "properties": {
            "search_term": {
                "type": "string",
                "description": "Item name or keyword to search for"
            }
        },
        "required": ["search_term"]
    }
    
    async def execute(self, search_term: str) -> str:
        result = await search_walmart_items(search_term)
        return json.dumps(result, indent=2)


class GetWalmartOrderDetails(SkillTool):
    """Get details for a specific Walmart order."""
    
    name = "get_walmart_order_details"
    description = "Get detailed information about a specific Walmart order including all items."
    parameters = {
        "type": "object",
        "properties": {
            "order_id": {
                "type": "string",
                "description": "The Walmart order ID"
            }
        },
        "required": ["order_id"]
    }
    
    async def execute(self, order_id: str) -> str:
        result = await get_order_details(order_id)
        return json.dumps(result, indent=2)


class GetWalmartSpendingByCategory(SkillTool):
    """Get Walmart spending breakdown by category."""
    
    name = "get_walmart_spending_by_category"
    description = "Get spending breakdown by category for Walmart purchases. Categories include: Food, Beverages, Household, Kitchen Supplies, Personal Care, Pet Supplies, Health, Baby & Kids, and Other."
    parameters = {
        "type": "object",
        "properties": {
            "start_date": {
                "type": "string",
                "description": "Optional start date (e.g., 'Jan 1, 2026')"
            },
            "end_date": {
                "type": "string",
                "description": "Optional end date (e.g., 'Jan 31, 2026')"
            }
        },
        "required": []
    }
    
    async def execute(self, start_date: str = None, end_date: str = None) -> str:
        result = await get_spending_by_category(start_date, end_date)
        return json.dumps(result, indent=2)


class GetWalmartItemsByCategory(SkillTool):
    """Get all items purchased in a specific category from Walmart."""
    
    name = "get_walmart_items_by_category"
    description = "Get all items purchased in a specific category. Available categories: Food, Beverages, Household, Kitchen Supplies, Personal Care, Pet Supplies, Health, Baby & Kids, Other."
    parameters = {
        "type": "object",
        "properties": {
            "category": {
                "type": "string",
                "description": "Category name (e.g., 'Food', 'Beverages', 'Household')"
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
