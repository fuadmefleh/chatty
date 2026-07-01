"""Walmart order query tools for LLM function calling."""
import json
import logging
from typing import Dict, Any
from src.core.base_tool import BaseTool

# Import walmart order query tools
try:
    from skills.walmart_orders.query_orders import (
        get_monthly_spending,
        get_recent_orders,
        search_walmart_items,
        get_order_details,
        get_spending_by_category,
        get_items_by_category
    )
    WALMART_TOOLS_AVAILABLE = True
except ImportError as e:
    WALMART_TOOLS_AVAILABLE = False
    logging.warning(f"Walmart order tools not available: {e}")


class GetMonthlyWalmartSpendingTool(BaseTool):
    """Get total amount spent at Walmart for a specific month."""
    
    @property
    def name(self) -> str:
        return "get_monthly_walmart_spending"
    
    @property
    def description(self) -> str:
        return "Get total amount spent at Walmart for a specific month. Use this when user asks 'how much have I spent at walmart this month' or similar questions about monthly Walmart spending."
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
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
        if not WALMART_TOOLS_AVAILABLE:
            return "Walmart order tools are not available"
        
        result = await get_monthly_spending(year, month)
        return json.dumps(result, indent=2)


class GetRecentWalmartOrdersTool(BaseTool):
    """Get recent Walmart orders with dates and amounts."""
    
    @property
    def name(self) -> str:
        return "get_recent_walmart_orders"
    
    @property
    def description(self) -> str:
        return "Get recent Walmart orders with dates and amounts."
    
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
        if not WALMART_TOOLS_AVAILABLE:
            return "Walmart order tools are not available"
        
        result = await get_recent_orders(limit)
        return json.dumps(result, indent=2)


class SearchWalmartItemsTool(BaseTool):
    """Search for specific items purchased at Walmart by name."""
    
    @property
    def name(self) -> str:
        return "search_walmart_items"
    
    @property
    def description(self) -> str:
        return "Search for specific items purchased at Walmart by name."
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
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
        if not WALMART_TOOLS_AVAILABLE:
            return "Walmart order tools are not available"
        
        result = await search_walmart_items(search_term)
        return json.dumps(result, indent=2)


class GetWalmartSpendingByCategoryTool(BaseTool):
    """Get Walmart spending breakdown by category (Food, Beverages, Household, etc.)."""
    
    @property
    def name(self) -> str:
        return "get_walmart_spending_by_category"
    
    @property
    def description(self) -> str:
        return "Get spending breakdown by category for Walmart purchases. Categories include: Food, Beverages, Household, Kitchen Supplies, Personal Care, Pet Supplies, Health, Baby & Kids, and Other."
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
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
        if not WALMART_TOOLS_AVAILABLE:
            return "Walmart order tools are not available"
        
        result = await get_spending_by_category(start_date, end_date)
        return json.dumps(result, indent=2)


class GetWalmartItemsByCategoryTool(BaseTool):
    """Get all items purchased in a specific category from Walmart."""
    
    @property
    def name(self) -> str:
        return "get_walmart_items_by_category"
    
    @property
    def description(self) -> str:
        return "Get all items purchased in a specific category. Available categories: Food, Beverages, Household, Kitchen Supplies, Personal Care, Pet Supplies, Health, Baby & Kids, Other."
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Category name (e.g., 'Food', 'Beverages', 'Household', 'Kitchen Supplies', 'Personal Care', 'Pet Supplies', 'Health', 'Baby & Kids', 'Other')"
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
        if not WALMART_TOOLS_AVAILABLE:
            return "Walmart order tools are not available"
        
        result = await get_items_by_category(category, limit)
        return json.dumps(result, indent=2)

