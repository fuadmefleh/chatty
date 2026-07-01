"""Amazon order query tools for LLM function calling."""
import json
import logging
from typing import Dict, Any
from src.core.base_tool import BaseTool

# Import Amazon order query tools
try:
    from skills.amazon_orders.query_orders import (
        get_monthly_spending,
        get_recent_orders,
        search_amazon_items,
        get_spending_by_category,
        get_items_by_category
    )
    AMAZON_TOOLS_AVAILABLE = True
except ImportError as e:
    AMAZON_TOOLS_AVAILABLE = False
    logging.warning(f"Amazon order tools not available: {e}")


class GetMonthlyAmazonSpendingTool(BaseTool):
    """Get total amount spent on Amazon for a specific month."""
    
    @property
    def name(self) -> str:
        return "get_monthly_amazon_spending"
    
    @property
    def description(self) -> str:
        return "Get total amount spent on Amazon for a specific month. Use this when user asks 'how much did I spend on amazon in december' or similar questions about monthly Amazon spending. Returns total spent, order count, and order details."
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "year": {
                    "type": "integer",
                    "description": "Year (e.g., 2025)"
                },
                "month": {
                    "type": "integer",
                    "description": "Month number (1-12, where 1=January, 2=February, ..., 12=December)"
                }
            },
            "required": ["year", "month"]
        }
    
    async def execute(self, year: int, month: int) -> str:
        if not AMAZON_TOOLS_AVAILABLE:
            return "Amazon order tools are not available"
        
        result = await get_monthly_spending(year, month)
        return json.dumps(result, indent=2)


class GetRecentAmazonOrdersTool(BaseTool):
    """Get recent Amazon orders with dates and amounts."""
    
    @property
    def name(self) -> str:
        return "get_recent_amazon_orders"
    
    @property
    def description(self) -> str:
        return "Get recent Amazon orders with dates, order numbers, and total amounts. Useful for viewing order history."
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of orders to return (default: 10)",
                    "default": 10
                }
            },
            "required": []
        }
    
    async def execute(self, limit: int = 10) -> str:
        if not AMAZON_TOOLS_AVAILABLE:
            return "Amazon order tools are not available"
        
        result = await get_recent_orders(limit)
        return json.dumps(result, indent=2)


class SearchAmazonItemsTool(BaseTool):
    """Search for specific items purchased on Amazon by name."""
    
    @property
    def name(self) -> str:
        return "search_amazon_items"
    
    @property
    def description(self) -> str:
        return "Search for items purchased on Amazon by name. Useful when user wants to find specific products they bought."
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
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
        if not AMAZON_TOOLS_AVAILABLE:
            return "Amazon order tools are not available"
        
        result = await search_amazon_items(search_term)
        return json.dumps(result, indent=2)


class GetAmazonSpendingByCategoryTool(BaseTool):
    """Get Amazon spending broken down by category."""
    
    @property
    def name(self) -> str:
        return "get_amazon_spending_by_category"
    
    @property
    def description(self) -> str:
        return "Get Amazon spending broken down by category (e.g., Electronics, Food, Health). Useful for analyzing spending patterns."
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "start_date": {
                    "type": "string",
                    "description": "Optional start date filter (format: 'January 1, 2025')",
                },
                "end_date": {
                    "type": "string",
                    "description": "Optional end date filter (format: 'December 31, 2025')",
                }
            },
            "required": []
        }
    
    async def execute(self, start_date: str = None, end_date: str = None) -> str:
        if not AMAZON_TOOLS_AVAILABLE:
            return "Amazon order tools are not available"
        
        result = await get_spending_by_category(start_date, end_date)
        return json.dumps(result, indent=2)


class GetAmazonItemsByCategoryTool(BaseTool):
    """Get all items purchased on Amazon in a specific category."""
    
    @property
    def name(self) -> str:
        return "get_amazon_items_by_category"
    
    @property
    def description(self) -> str:
        return "Get all items purchased on Amazon in a specific category (e.g., 'Electronics', 'Food', 'Health')."
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Category name (e.g., 'Electronics', 'Food', 'Health', 'Home', 'Books')"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of items to return (default: 50)",
                    "default": 50
                }
            },
            "required": ["category"]
        }
    
    async def execute(self, category: str, limit: int = 50) -> str:
        if not AMAZON_TOOLS_AVAILABLE:
            return "Amazon order tools are not available"
        
        result = await get_items_by_category(category, limit)
        return json.dumps(result, indent=2)


def get_amazon_tools():
    """Get all Amazon order tools.
    
    Returns:
        List of Amazon tool instances
    """
    return [
        GetMonthlyAmazonSpendingTool(),
        GetRecentAmazonOrdersTool(),
        SearchAmazonItemsTool(),
        GetAmazonSpendingByCategoryTool(),
        GetAmazonItemsByCategoryTool()
    ]
