"""Plaid banking skill tools for LLM function calling.

These tools are dynamically loaded by the framework when the skill is activated.
"""
import logging
import sys
import importlib.util
from pathlib import Path

# Add project root to path for src imports
project_root = str(Path(__file__).parent.parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.core.skill_tool import SkillTool

# Load the plaid_integration module from THIS skill folder explicitly
try:
    _integration_path = Path(__file__).parent / "plaid_integration.py"
    _spec = importlib.util.spec_from_file_location("plaid_integration_module", _integration_path)
    _integration_module = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_integration_module)
    get_plaid_integration = _integration_module.get_plaid_integration
    PLAID_AVAILABLE = True
except Exception as e:
    PLAID_AVAILABLE = False
    logging.warning(f"Plaid integration not available: {e}")


def _check_plaid_available() -> str:
    """Check if Plaid is available, return error message if not."""
    if not PLAID_AVAILABLE:
        return "Error: Plaid integration is not available. Please check the installation."
    return None


class GetBankBalances(SkillTool):
    """Get current balances for all linked bank accounts."""
    
    name = "get_bank_balances"
    description = "Get current balances for all linked bank accounts. Use this when user asks 'what's my bank balance', 'how much money do I have', or similar questions about account balances."
    parameters = {
        "type": "object",
        "properties": {},
        "required": []
    }
    
    async def execute(self) -> str:
        error = _check_plaid_available()
        if error:
            return error
        
        try:
            plaid = get_plaid_integration()
            result = plaid.get_balance_summary()
            return result
        except Exception as e:
            logging.error(f"Error getting bank balances: {e}")
            return f"Error retrieving bank balances: {str(e)}"


class GetRecentTransactions(SkillTool):
    """Get recent bank transactions."""
    
    name = "get_recent_transactions"
    description = "Get recent bank transactions from linked accounts. Use this when user asks about recent purchases, spending, or transactions."
    parameters = {
        "type": "object",
        "properties": {
            "days": {
                "type": "integer",
                "description": "Number of days to look back (default: 30, max: 730)"
            }
        },
        "required": []
    }
    
    async def execute(self, days: int = 30) -> str:
        error = _check_plaid_available()
        if error:
            return error
        
        try:
            plaid = get_plaid_integration()
            result = plaid.get_recent_transactions(days)
            return result
        except Exception as e:
            logging.error(f"Error getting recent transactions: {e}")
            return f"Error retrieving transactions: {str(e)}"


class GetSpendingByCategory(SkillTool):
    """Get spending breakdown by category."""
    
    name = "get_spending_by_category"
    description = "Get spending breakdown grouped by category. Use this when user asks 'how much did I spend on X', 'what are my spending categories', or similar budget/spending analysis questions."
    parameters = {
        "type": "object",
        "properties": {
            "days": {
                "type": "integer",
                "description": "Number of days to analyze (default: 30, max: 365)"
            }
        },
        "required": []
    }
    
    async def execute(self, days: int = 30) -> str:
        error = _check_plaid_available()
        if error:
            return error
        
        try:
            plaid = get_plaid_integration()
            result = plaid.get_spending_by_category(days)
            return result
        except Exception as e:
            logging.error(f"Error getting spending by category: {e}")
            return f"Error analyzing spending: {str(e)}"


class GetBankAccounts(SkillTool):
    """Get list of all linked bank accounts."""
    
    name = "get_bank_accounts"
    description = "Get detailed list of all linked bank accounts including account types and masked account numbers. Use when user asks 'what accounts do I have', 'show my accounts', or similar."
    parameters = {
        "type": "object",
        "properties": {},
        "required": []
    }
    
    async def execute(self) -> str:
        error = _check_plaid_available()
        if error:
            return error
        
        try:
            plaid = get_plaid_integration()
            accounts = plaid.get_accounts()
            
            if not accounts:
                return "No linked bank accounts found. Please link your bank account first."
            
            lines = ["=== Linked Bank Accounts ===\n"]
            for account in accounts:
                lines.append(
                    f"{account['institution']} - {account['name']} "
                    f"({account['type']}/{account['subtype']}) "
                    f"***{account['mask']}"
                )
            
            return "\n".join(lines)
        except Exception as e:
            logging.error(f"Error getting bank accounts: {e}")
            return f"Error retrieving accounts: {str(e)}"
