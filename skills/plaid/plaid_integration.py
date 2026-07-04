"""Plaid integration for accessing bank account information."""
import os
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from plaid.api import plaid_api
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.products import Products
from plaid.model.country_code import CountryCode
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.accounts_get_request import AccountsGetRequest
from plaid.model.transactions_get_request import TransactionsGetRequest
import plaid

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PlaidIntegration:
    """Handles Plaid API integration for bank account access."""
    
    def __init__(self):
        """Initialize Plaid client with credentials from environment."""
        self.client_id = os.getenv('PLAID_CLIENT_ID')
        self.secret = os.getenv('PLAID_SECRET')
        self.environment = os.getenv('PLAID_ENV', 'sandbox')  # sandbox, development, or production
        
        if not self.client_id or not self.secret:
            raise ValueError(
                "Missing Plaid credentials. Set PLAID_CLIENT_ID and PLAID_SECRET "
                "environment variables."
            )
        
        # Configure Plaid client
        configuration = plaid.Configuration(
            host=self._get_plaid_host(),
            api_key={
                'clientId': self.client_id,
                'secret': self.secret,
            }
        )
        
        api_client = plaid.ApiClient(configuration)
        self.client = plaid_api.PlaidApi(api_client)
        
        # Store access tokens (in production, use a secure database)
        self.access_tokens_file = 'data/plaid_tokens.json'
        self.access_tokens = self._load_access_tokens()
    
    def _get_plaid_host(self) -> str:
        """Get the appropriate Plaid API host based on environment."""
        if self.environment == 'sandbox':
            return 'https://sandbox.plaid.com'
        else:
            # Both development and production use the production host
            return 'https://production.plaid.com'
    
    def _load_access_tokens(self) -> Dict[str, str]:
        """Load stored access tokens from file."""
        try:
            if os.path.exists(self.access_tokens_file):
                with open(self.access_tokens_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error loading access tokens: {e}")
        return {}
    
    def _save_access_tokens(self):
        """Save access tokens to file."""
        try:
            os.makedirs(os.path.dirname(self.access_tokens_file), exist_ok=True)
            with open(self.access_tokens_file, 'w') as f:
                json.dump(self.access_tokens, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving access tokens: {e}")
    
    def create_link_token(self, user_id: str) -> str:
        """
        Create a Link token for Plaid Link initialization.
        
        Args:
            user_id: Unique identifier for the user
            
        Returns:
            Link token string
        """
        try:
            request = LinkTokenCreateRequest(
                products=[Products("transactions"), Products("auth")],
                client_name="Chatty Bot",
                country_codes=[CountryCode('US')],
                language='en',
                user=LinkTokenCreateRequestUser(
                    client_user_id=user_id
                )
            )
            response = self.client.link_token_create(request)
            return response['link_token']
        except Exception as e:
            logger.error(f"Error creating link token: {e}")
            raise
    
    def exchange_public_token(self, public_token: str, institution_name: str = "bank") -> str:
        """
        Exchange a public token for an access token.
        
        Args:
            public_token: Public token from Plaid Link
            institution_name: Name to identify this bank connection
            
        Returns:
            Access token
        """
        try:
            request = ItemPublicTokenExchangeRequest(
                public_token=public_token
            )
            response = self.client.item_public_token_exchange(request)
            access_token = response['access_token']
            
            # Store the access token
            self.access_tokens[institution_name] = access_token
            self._save_access_tokens()
            
            logger.info(f"Successfully linked {institution_name}")
            return access_token
        except Exception as e:
            logger.error(f"Error exchanging public token: {e}")
            raise
    
    def get_accounts(self, institution_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all linked bank accounts.
        
        Args:
            institution_name: Optional filter for specific institution
            
        Returns:
            List of account dictionaries
        """
        all_accounts = []
        
        tokens_to_query = {}
        if institution_name and institution_name in self.access_tokens:
            tokens_to_query[institution_name] = self.access_tokens[institution_name]
        else:
            tokens_to_query = self.access_tokens
        
        for inst_name, access_token in tokens_to_query.items():
            try:
                request = AccountsGetRequest(access_token=access_token)
                response = self.client.accounts_get(request)
                
                for account in response['accounts']:
                    account_info = {
                        'institution': inst_name,
                        'account_id': account['account_id'],
                        'name': account['name'],
                        'type': account['type'],
                        'subtype': account['subtype'],
                        'mask': account.get('mask', 'N/A'),
                        'balance_current': account['balances']['current'],
                        'balance_available': account['balances'].get('available'),
                        'currency': account['balances'].get('iso_currency_code', 'USD')
                    }
                    all_accounts.append(account_info)
            except Exception as e:
                logger.error(f"Error fetching accounts for {inst_name}: {e}")
        
        return all_accounts
    
    def get_transactions(
        self,
        start_date: datetime,
        end_date: datetime,
        institution_name: Optional[str] = None,
        account_ids: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Get transactions for linked accounts within a date range.
        
        Args:
            start_date: Start date for transactions
            end_date: End date for transactions
            institution_name: Optional filter for specific institution
            account_ids: Optional list of specific account IDs
            
        Returns:
            List of transaction dictionaries
        """
        all_transactions = []
        
        tokens_to_query = {}
        if institution_name and institution_name in self.access_tokens:
            tokens_to_query[institution_name] = self.access_tokens[institution_name]
        else:
            tokens_to_query = self.access_tokens
        
        for inst_name, access_token in tokens_to_query.items():
            try:
                request = TransactionsGetRequest(
                    access_token=access_token,
                    start_date=start_date.date(),
                    end_date=end_date.date(),
                    options={
                        'account_ids': account_ids,
                        'count': 500,
                        'offset': 0
                    } if account_ids else {'count': 500, 'offset': 0}
                )
                response = self.client.transactions_get(request)
                
                for transaction in response['transactions']:
                    tx_info = {
                        'institution': inst_name,
                        'transaction_id': transaction['transaction_id'],
                        'account_id': transaction['account_id'],
                        'date': transaction['date'].isoformat() if hasattr(transaction['date'], 'isoformat') else str(transaction['date']),
                        'name': transaction['name'],
                        'merchant_name': transaction.get('merchant_name'),
                        'amount': transaction['amount'],
                        'category': transaction.get('category', []),
                        'pending': transaction.get('pending', False),
                        'payment_channel': transaction.get('payment_channel')
                    }
                    all_transactions.append(tx_info)
                
                # Handle pagination if needed
                total_transactions = response['total_transactions']
                offset = 500
                while offset < total_transactions:
                    request.options['offset'] = offset
                    response = self.client.transactions_get(request)
                    for transaction in response['transactions']:
                        tx_info = {
                            'institution': inst_name,
                            'transaction_id': transaction['transaction_id'],
                            'account_id': transaction['account_id'],
                            'date': transaction['date'].isoformat() if hasattr(transaction['date'], 'isoformat') else str(transaction['date']),
                            'name': transaction['name'],
                            'merchant_name': transaction.get('merchant_name'),
                            'amount': transaction['amount'],
                            'category': transaction.get('category', []),
                            'pending': transaction.get('pending', False),
                            'payment_channel': transaction.get('payment_channel')
                        }
                        all_transactions.append(tx_info)
                    offset += 500
                    
            except Exception as e:
                logger.error(f"Error fetching transactions for {inst_name}: {e}")
        
        return all_transactions
    
    def get_balance_summary(self) -> str:
        """
        Get a summary of all account balances.
        
        Returns:
            Formatted string with balance information
        """
        accounts = self.get_accounts()
        
        if not accounts:
            return "No linked bank accounts found. Use the link_bank_account function to connect your bank."
        
        summary_lines = ["=== Bank Account Balances ===\n"]
        total_balance = 0
        
        for account in accounts:
            balance = account['balance_current']
            total_balance += balance
            
            summary_lines.append(
                f"{account['institution']} - {account['name']} "
                f"(***{account['mask']}): ${balance:,.2f}"
            )
        
        summary_lines.append(f"\nTotal Balance: ${total_balance:,.2f}")
        return "\n".join(summary_lines)
    
    def get_recent_transactions(self, days: int = 30) -> str:
        """
        Get recent transactions from the past N days.
        
        Args:
            days: Number of days to look back
            
        Returns:
            Formatted string with transaction information
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        transactions = self.get_transactions(start_date, end_date)
        
        if not transactions:
            return f"No transactions found in the last {days} days."
        
        # Sort by date, most recent first
        transactions.sort(key=lambda x: x['date'], reverse=True)
        
        summary_lines = [f"=== Transactions (Last {days} Days) ===\n"]
        
        for tx in transactions[:50]:  # Limit to 50 most recent
            pending_str = " [PENDING]" if tx['pending'] else ""
            category_str = ", ".join(tx['category']) if tx['category'] else "Uncategorized"
            
            summary_lines.append(
                f"{tx['date']} | {tx['name']:<40} | ${tx['amount']:>8.2f} | {category_str}{pending_str}"
            )
        
        if len(transactions) > 50:
            summary_lines.append(f"\n... and {len(transactions) - 50} more transactions")
        
        return "\n".join(summary_lines)
    
    def get_spending_by_category(self, days: int = 30) -> str:
        """
        Get spending grouped by category.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Formatted string with spending by category
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        transactions = self.get_transactions(start_date, end_date)
        
        if not transactions:
            return f"No transactions found in the last {days} days."
        
        # Group by category
        category_totals = {}
        for tx in transactions:
            if tx['amount'] > 0:  # Only count expenses (positive amounts in Plaid)
                category = tx['category'][0] if tx['category'] else 'Uncategorized'
                category_totals[category] = category_totals.get(category, 0) + tx['amount']
        
        # Sort by amount
        sorted_categories = sorted(category_totals.items(), key=lambda x: x[1], reverse=True)
        
        summary_lines = [f"=== Spending by Category (Last {days} Days) ===\n"]
        total_spending = 0
        
        for category, amount in sorted_categories:
            summary_lines.append(f"{category:<30} ${amount:>10.2f}")
            total_spending += amount
        
        summary_lines.append(f"\n{'Total':<30} ${total_spending:>10.2f}")
        
        return "\n".join(summary_lines)


# Global instance
_plaid_integration = None

def get_plaid_integration() -> PlaidIntegration:
    """Get or create the global PlaidIntegration instance."""
    global _plaid_integration
    if _plaid_integration is None:
        _plaid_integration = PlaidIntegration()
    return _plaid_integration
