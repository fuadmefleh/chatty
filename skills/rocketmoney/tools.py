"""Rocket Money Transactions skill tools for LLM function calling.

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

# Load the query_transactions module from THIS skill folder explicitly
_query_path = Path(__file__).parent / "query_transactions.py"
_spec = importlib.util.spec_from_file_location("rocketmoney_query", _query_path)
_query_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_query_module)

# Import functions from the loaded module
get_monthly_spending = _query_module.get_monthly_spending
get_spending_by_category = _query_module.get_spending_by_category
get_merchant_spending = _query_module.get_merchant_spending
get_spending_trends = _query_module.get_spending_trends
search_transactions = _query_module.search_transactions
get_account_summary = _query_module.get_account_summary
get_top_expenses = _query_module.get_top_expenses
get_database_stats = _query_module.get_database_stats


class GetMonthlyRocketMoneySpending(SkillTool):
    """Get total spending for a specific month from Rocket Money data."""
    
    name = "get_monthly_rocketmoney_spending"
    description = "Get total spending for a specific month from Rocket Money transaction data. Shows breakdown by category and individual transactions."
    parameters = {
        "type": "object",
        "properties": {
            "year": {
                "type": "integer",
                "description": "Year (e.g., 2026)"
            },
            "month": {
                "type": "integer",
                "description": "Month number (1-12, where 1=January)"
            }
        },
        "required": ["year", "month"]
    }
    
    async def execute(self, year: int, month: int) -> str:
        result = await get_monthly_spending(year, month)
        return json.dumps(result, indent=2, default=str)


class GetRocketMoneySpendingByCategory(SkillTool):
    """Get spending for a specific category."""
    
    name = "get_rocketmoney_spending_by_category"
    description = "Get spending breakdown for a specific category (e.g., Groceries, Dining & Drinks, Shopping). Shows top merchants and transactions."
    parameters = {
        "type": "object",
        "properties": {
            "category": {
                "type": "string",
                "description": "Category name (e.g., 'Groceries', 'Dining & Drinks', 'Shopping', 'Entertainment')"
            },
            "start_date": {
                "type": "string",
                "description": "Optional start date in YYYY-MM-DD format"
            },
            "end_date": {
                "type": "string",
                "description": "Optional end date in YYYY-MM-DD format"
            }
        },
        "required": ["category"]
    }
    
    async def execute(self, category: str, start_date: str = None, end_date: str = None) -> str:
        result = await get_spending_by_category(category, start_date, end_date)
        return json.dumps(result, indent=2, default=str)


class GetMerchantSpending(SkillTool):
    """Get spending at a specific merchant."""
    
    name = "get_merchant_spending"
    description = "Get all spending at a specific merchant (e.g., Walmart, Amazon, Target). Shows total amount and transaction history."
    parameters = {
        "type": "object",
        "properties": {
            "merchant_name": {
                "type": "string",
                "description": "Merchant name (e.g., 'Walmart', 'Amazon', 'Target')"
            },
            "start_date": {
                "type": "string",
                "description": "Optional start date in YYYY-MM-DD format"
            },
            "end_date": {
                "type": "string",
                "description": "Optional end date in YYYY-MM-DD format"
            }
        },
        "required": ["merchant_name"]
    }
    
    async def execute(self, merchant_name: str, start_date: str = None, end_date: str = None) -> str:
        result = await get_merchant_spending(merchant_name, start_date, end_date)
        return json.dumps(result, indent=2, default=str)


class GetSpendingTrends(SkillTool):
    """Get spending trends over time."""
    
    name = "get_spending_trends"
    description = "Get spending trends over the last N months. Shows monthly totals and top categories for each month."
    parameters = {
        "type": "object",
        "properties": {
            "months": {
                "type": "integer",
                "description": "Number of months to analyze (default: 6)"
            }
        },
        "required": []
    }
    
    async def execute(self, months: int = 6) -> str:
        result = await get_spending_trends(months)
        return json.dumps(result, indent=2, default=str)


class SearchRocketMoneyTransactions(SkillTool):
    """Search transactions by name, description, or category."""
    
    name = "search_rocketmoney_transactions"
    description = "Search all Rocket Money transactions by name, description, or category. Useful for finding specific purchases."
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query (merchant name, description, or category)"
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of results (default: 50)"
            }
        },
        "required": ["query"]
    }
    
    async def execute(self, query: str, limit: int = 50) -> str:
        result = await search_transactions(query, limit)
        return json.dumps(result, indent=2, default=str)


class GetAccountSummary(SkillTool):
    """Get summary of all accounts."""
    
    name = "get_rocketmoney_account_summary"
    description = "Get summary of all accounts in Rocket Money including total spending and transaction counts per account."
    parameters = {
        "type": "object",
        "properties": {},
        "required": []
    }
    
    async def execute(self) -> str:
        result = await get_account_summary()
        return json.dumps(result, indent=2, default=str)


class GetTopExpenses(SkillTool):
    """Get top individual expenses."""
    
    name = "get_top_expenses"
    description = "Get the largest individual expenses. Useful for finding big purchases."
    parameters = {
        "type": "object",
        "properties": {
            "start_date": {
                "type": "string",
                "description": "Optional start date in YYYY-MM-DD format"
            },
            "end_date": {
                "type": "string",
                "description": "Optional end date in YYYY-MM-DD format"
            },
            "limit": {
                "type": "integer",
                "description": "Number of top expenses to return (default: 20)"
            }
        },
        "required": []
    }
    
    async def execute(self, start_date: str = None, end_date: str = None, limit: int = 20) -> str:
        result = await get_top_expenses(start_date, end_date, limit)
        return json.dumps(result, indent=2, default=str)


class GetRocketMoneyStats(SkillTool):
    """Get overall database statistics."""
    
    name = "get_rocketmoney_stats"
    description = "Get overall statistics from the Rocket Money database including total transactions, date ranges, and spending totals."
    parameters = {
        "type": "object",
        "properties": {},
        "required": []
    }
    
    async def execute(self) -> str:
        result = await get_database_stats()
        return json.dumps(result, indent=2, default=str)
