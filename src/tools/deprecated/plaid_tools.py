"""Plaid bank account tools for LLM function calling."""
import logging
from typing import Dict, Any
from src.core.base_tool import BaseTool

# Import Plaid integration
try:
    from skills.plaid.plaid_integration import get_plaid_integration
    PLAID_TOOLS_AVAILABLE = True
except ImportError as e:
    PLAID_TOOLS_AVAILABLE = False
    logging.warning(f"Plaid tools not available: {e}")


class GetBankBalancesTool(BaseTool):
    """Get current balances for all linked bank accounts."""
    
    @property
    def name(self) -> str:
        return "get_bank_balances"
    
    @property
    def description(self) -> str:
        return "Get current balances for all linked bank accounts. Use this when user asks 'what's my bank balance', 'how much money do I have', or similar questions about account balances."
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "required": []
        }
    
    async def execute(self) -> str:
        """Get bank account balances."""
        if not PLAID_TOOLS_AVAILABLE:
            return "Error: Plaid integration is not available. Please check the installation."
        
        try:
            plaid = get_plaid_integration()
            result = plaid.get_balance_summary()
            return result
        except Exception as e:
            logging.error(f"Error getting bank balances: {e}")
            return f"Error retrieving bank balances: {str(e)}"


class GetRecentTransactionsTool(BaseTool):
    """Get recent bank transactions."""
    
    @property
    def name(self) -> str:
        return "get_recent_transactions"
    
    @property
    def description(self) -> str:
        return "Get recent bank transactions from linked accounts. Use this when user asks about recent purchases, spending, or transactions."
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "days": {
                    "type": "integer",
                    "description": "Number of days to look back (default: 30, max: 730)",
                    "default": 30,
                    "minimum": 1,
                    "maximum": 730
                }
            },
            "required": []
        }
    
    async def execute(self, days: int = 30) -> str:
        """Get recent transactions."""
        if not PLAID_TOOLS_AVAILABLE:
            return "Error: Plaid integration is not available. Please check the installation."
        
        try:
            plaid = get_plaid_integration()
            result = plaid.get_recent_transactions(days)
            return result
        except Exception as e:
            logging.error(f"Error getting recent transactions: {e}")
            return f"Error retrieving transactions: {str(e)}"


class GetSpendingByCategoryTool(BaseTool):
    """Get spending breakdown by category."""
    
    @property
    def name(self) -> str:
        return "get_spending_by_category"
    
    @property
    def description(self) -> str:
        return "Get spending breakdown grouped by category. Use this when user asks 'how much did I spend on X', 'what are my spending categories', or similar budget/spending analysis questions."
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "days": {
                    "type": "integer",
                    "description": "Number of days to analyze (default: 30, max: 365)",
                    "default": 30,
                    "minimum": 1,
                    "maximum": 365
                }
            },
            "required": []
        }
    
    async def execute(self, days: int = 30) -> str:
        """Get spending by category."""
        if not PLAID_TOOLS_AVAILABLE:
            return "Error: Plaid integration is not available. Please check the installation."
        
        try:
            plaid = get_plaid_integration()
            result = plaid.get_spending_by_category(days)
            return result
        except Exception as e:
            logging.error(f"Error getting spending by category: {e}")
            return f"Error analyzing spending: {str(e)}"


class GetBankAccountsTool(BaseTool):
    """Get list of all linked bank accounts."""
    
    @property
    def name(self) -> str:
        return "get_bank_accounts"
    
    @property
    def description(self) -> str:
        return "Get detailed list of all linked bank accounts including account types and masked account numbers. Use when user asks 'what accounts do I have', 'show my accounts', or similar."
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "required": []
        }
    
    async def execute(self) -> str:
        """Get bank accounts list."""
        if not PLAID_TOOLS_AVAILABLE:
            return "Error: Plaid integration is not available. Please check the installation."
        
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


# Export all Plaid tools
def get_plaid_tools():
    """Get all Plaid-related tools."""
    if not PLAID_TOOLS_AVAILABLE:
        logging.warning("Plaid tools not available")
        return []
    
    return [
        GetBankBalancesTool(),
        GetRecentTransactionsTool(),
        GetSpendingByCategoryTool(),
        GetBankAccountsTool()
    ]
