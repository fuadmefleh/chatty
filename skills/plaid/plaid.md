# Plaid Bank Integration

## Description
Connect to your bank accounts via Plaid to access balance information, recent transactions, and spending analytics. This skill provides secure, read-only access to your financial data through the Plaid API.

## Setup

### 1. Get Plaid API Credentials
1. Sign up for a free account at https://dashboard.plaid.com/signup
2. Get your `client_id` and `secret` from the dashboard
3. Start with the Sandbox environment for testing

### 2. Set Environment Variables
Add these to your `.env` file or export them:

```bash
export PLAID_CLIENT_ID="your_client_id_here"
export PLAID_SECRET="your_secret_here"
export PLAID_ENV="sandbox"  # Options: sandbox, development, production
```

### 3. Install Dependencies
```bash
pip install plaid-python
```

### 4. Link Your Bank Account
The first time you use Plaid, you'll need to link your bank account. In the Sandbox environment, you can use test credentials:
- Institution: Any bank (search for "Chase", "Bank of America", etc.)
- Username: `user_good`
- Password: `pass_good`

For production, you'll complete the real bank login flow through Plaid Link.

## Usage
Use this skill when you need to:
- Check bank account balances
- Review recent transactions
- Analyze spending by category
- Get financial insights from your bank data

## Examples
- "What's my bank balance?"
- "Show me my recent transactions"
- "How much did I spend in the last 30 days?"
- "What are my spending categories this month?"
- "Show me transactions from the past week"
- "How much did I spend on food?"
- "What accounts do I have linked?"

## Features

### Balance Checking
Get current balances across all linked accounts with total summary.

### Transaction History
View detailed transaction history with:
- Merchant names
- Transaction amounts
- Categories
- Dates
- Pending status

### Spending Analytics
Analyze spending patterns:
- Breakdown by category
- Customizable date ranges
- Total spending summaries

## Security Notes
- Access tokens are stored locally in `data/plaid_tokens.json`
- **Important**: Never commit this file to version control
- Add `data/plaid_tokens.json` to your `.gitignore`
- In production, use a secure database for token storage
- Plaid provides read-only access - no ability to move money
- Use environment variables for credentials, never hardcode them

## Plaid Environments

### Sandbox (Testing)
- Free, unlimited API calls
- Test credentials provided by Plaid
- No real financial data

### Development
- Limited free API calls
- Real bank connections
- Use for development before production

### Production
- Paid pricing based on usage
- Full production access
- Real bank data

## Troubleshooting

### "Missing Plaid credentials" error
Make sure `PLAID_CLIENT_ID` and `PLAID_SECRET` environment variables are set.

### "No linked bank accounts found"
You need to complete the Plaid Link flow first to connect a bank account.

### Rate limits
Sandbox: Unlimited
Development: Limited free calls
Production: Based on your plan

## API Reference
- Official Docs: https://plaid.com/docs/
- Python Client: https://github.com/plaid/plaid-python
- API Quickstart: https://plaid.com/docs/quickstart/

## Data Storage
Transaction data is fetched in real-time from Plaid. For better performance and offline access, consider adding local caching/database storage similar to the Walmart orders integration.
