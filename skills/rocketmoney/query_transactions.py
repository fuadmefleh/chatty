"""Query tools for Rocket Money transactions database."""
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from pathlib import Path
import sys

# Add parent directory to path to import rocketmoney_parser
sys.path.insert(0, str(Path(__file__).parent))
from rocketmoney_parser import RocketMoneyDB


async def get_monthly_spending(year: int, month: int) -> Dict[str, Any]:
    """Get total spending for a specific month.
    
    Args:
        year: Year (e.g., 2026)
        month: Month number (1-12)
    
    Returns:
        Dictionary with total spent, transaction count, and breakdown by category
    """
    db = RocketMoneyDB()
    try:
        # Format dates for the query
        start_date = f"{year}-{month:02d}-01"
        
        # Calculate end date (last day of month)
        if month == 12:
            end_date = f"{year}-12-31"
        else:
            next_month = datetime(year, month + 1, 1)
            last_day = (next_month - timedelta(days=1)).day
            end_date = f"{year}-{month:02d}-{last_day}"
        
        # Get transactions for the month
        transactions = db.get_transactions_by_date_range(start_date, end_date)
        
        # Calculate totals
        total_spent = sum(t['amount'] for t in transactions)
        
        # Get category breakdown
        category_spending = {}
        for t in transactions:
            category = t['category'] or 'Uncategorized'
            category_spending[category] = category_spending.get(category, 0) + t['amount']
        
        # Sort categories by spending
        sorted_categories = sorted(category_spending.items(), key=lambda x: x[1], reverse=True)
        
        return {
            'month': f"{year}-{month:02d}",
            'total_spent': total_spent,
            'transaction_count': len(transactions),
            'category_breakdown': dict(sorted_categories),
            'transactions': transactions[:50]  # Return first 50 for detail
        }
    finally:
        db.close()


async def get_spending_by_category(category: str, start_date: Optional[str] = None, 
                                   end_date: Optional[str] = None) -> Dict[str, Any]:
    """Get spending for a specific category.
    
    Args:
        category: Category name (e.g., "Groceries", "Dining & Drinks")
        start_date: Optional start date in YYYY-MM-DD format
        end_date: Optional end date in YYYY-MM-DD format
    
    Returns:
        Dictionary with total spent and transaction details
    """
    db = RocketMoneyDB()
    try:
        transactions = db.get_transactions_by_category(category)
        
        # Filter by date range if provided
        if start_date and end_date:
            transactions = [t for t in transactions 
                          if start_date <= t['date'] <= end_date]
        
        total_spent = sum(t['amount'] for t in transactions)
        
        # Get merchant breakdown
        merchant_spending = {}
        for t in transactions:
            merchant = t['name'] or 'Unknown'
            merchant_spending[merchant] = merchant_spending.get(merchant, 0) + t['amount']
        
        sorted_merchants = sorted(merchant_spending.items(), key=lambda x: x[1], reverse=True)
        
        return {
            'category': category,
            'total_spent': total_spent,
            'transaction_count': len(transactions),
            'top_merchants': dict(sorted_merchants[:10]),
            'transactions': transactions[:50]
        }
    finally:
        db.close()


async def get_merchant_spending(merchant_name: str, start_date: Optional[str] = None,
                               end_date: Optional[str] = None) -> Dict[str, Any]:
    """Get spending at a specific merchant.
    
    Args:
        merchant_name: Merchant name (e.g., "Walmart", "Amazon")
        start_date: Optional start date in YYYY-MM-DD format
        end_date: Optional end date in YYYY-MM-DD format
    
    Returns:
        Dictionary with total spent and transaction details
    """
    db = RocketMoneyDB()
    try:
        # Search for transactions with this merchant
        transactions = db.search_transactions(merchant_name)
        
        # Filter by date range if provided
        if start_date and end_date:
            transactions = [t for t in transactions 
                          if start_date <= t['date'] <= end_date]
        
        total_spent = sum(t['amount'] for t in transactions)
        
        # Get category breakdown
        category_spending = {}
        for t in transactions:
            category = t['category'] or 'Uncategorized'
            category_spending[category] = category_spending.get(category, 0) + t['amount']
        
        return {
            'merchant': merchant_name,
            'total_spent': total_spent,
            'transaction_count': len(transactions),
            'category_breakdown': category_spending,
            'transactions': transactions[:50]
        }
    finally:
        db.close()


async def get_spending_trends(months: int = 6) -> Dict[str, Any]:
    """Get spending trends over the last N months.
    
    Args:
        months: Number of months to analyze (default: 6)
    
    Returns:
        Dictionary with monthly spending breakdown
    """
    db = RocketMoneyDB()
    try:
        # Get current date
        now = datetime.now()
        
        monthly_data = []
        
        for i in range(months):
            # Calculate month/year
            month = now.month - i
            year = now.year
            
            while month <= 0:
                month += 12
                year -= 1
            
            # Get spending for this month
            result = await get_monthly_spending(year, month)
            monthly_data.append({
                'month': result['month'],
                'total_spent': result['total_spent'],
                'transaction_count': result['transaction_count'],
                'top_categories': dict(list(result['category_breakdown'].items())[:5])
            })
        
        return {
            'period': f"Last {months} months",
            'monthly_data': monthly_data
        }
    finally:
        db.close()


async def search_transactions(query: str, limit: int = 50) -> Dict[str, Any]:
    """Search transactions by name, description, or category.
    
    Args:
        query: Search query string
        limit: Maximum number of results to return
    
    Returns:
        Dictionary with matching transactions
    """
    db = RocketMoneyDB()
    try:
        transactions = db.search_transactions(query)[:limit]
        
        total_amount = sum(t['amount'] for t in transactions)
        
        return {
            'query': query,
            'result_count': len(transactions),
            'total_amount': total_amount,
            'transactions': transactions
        }
    finally:
        db.close()


async def get_account_summary() -> Dict[str, Any]:
    """Get summary of all accounts and their activity.
    
    Returns:
        Dictionary with account information
    """
    db = RocketMoneyDB()
    try:
        all_transactions = db.get_all_transactions(limit=10000)
        
        # Group by account
        accounts = {}
        for t in all_transactions:
            key = (t['institution_name'], t['account_name'])
            if key not in accounts:
                accounts[key] = {
                    'institution': t['institution_name'],
                    'account_name': t['account_name'],
                    'account_type': t['account_type'],
                    'account_number': t['account_number'],
                    'total_spent': 0,
                    'transaction_count': 0
                }
            accounts[key]['total_spent'] += t['amount']
            accounts[key]['transaction_count'] += 1
        
        sorted_accounts = sorted(accounts.values(), 
                               key=lambda x: x['total_spent'], 
                               reverse=True)
        
        return {
            'total_accounts': len(accounts),
            'accounts': sorted_accounts
        }
    finally:
        db.close()


async def get_top_expenses(start_date: Optional[str] = None, 
                          end_date: Optional[str] = None, 
                          limit: int = 20) -> Dict[str, Any]:
    """Get top individual expenses.
    
    Args:
        start_date: Optional start date in YYYY-MM-DD format
        end_date: Optional end date in YYYY-MM-DD format
        limit: Number of top expenses to return
    
    Returns:
        Dictionary with top expenses
    """
    db = RocketMoneyDB()
    try:
        if start_date and end_date:
            transactions = db.get_transactions_by_date_range(start_date, end_date)
        else:
            transactions = db.get_all_transactions(limit=10000)
        
        # Sort by amount (descending)
        sorted_transactions = sorted(transactions, key=lambda x: x['amount'], reverse=True)
        
        return {
            'period': f"{start_date or 'All time'} to {end_date or 'present'}",
            'top_expenses': sorted_transactions[:limit]
        }
    finally:
        db.close()


async def get_database_stats() -> Dict[str, Any]:
    """Get overall database statistics.
    
    Returns:
        Dictionary with database statistics
    """
    db = RocketMoneyDB()
    try:
        return db.get_statistics()
    finally:
        db.close()
