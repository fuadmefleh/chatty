# Plaid Bank Integration Guide

This guide will help you integrate Plaid with your bot to access bank account information.

## What is Plaid?

Plaid is a secure API that connects to over 12,000 banks and financial institutions, allowing your bot to access:
- Account balances
- Transaction history
- Spending analytics
- Account details

## Quick Start

### 1. Get Plaid Credentials

1. Visit [Plaid Dashboard](https://dashboard.plaid.com/signup)
2. Sign up for a free account
3. Navigate to "Team Settings" → "Keys"
4. Copy your `client_id` and `secret` (use Sandbox keys to start)

### 2. Run Setup Script

```bash
chmod +x setup_plaid.sh
./setup_plaid.sh
```

This will:
- Prompt you for your Plaid credentials
- Add them to your `.env` file
- Install the required `plaid-python` package
- Configure security settings

### 3. Link Your Bank Account

#### Option A: Using Test Credentials (Sandbox)

```bash
source venv/bin/activate
python3 skills/plaid/link_account.py
```

Follow the prompts and use these test credentials:
- **Username**: `user_good`
- **Password**: `pass_good`
- **Institution**: Any bank (search for "Chase", "Wells Fargo", etc.)

#### Option B: Real Bank (Development/Production)

For real bank connections:
1. Change `PLAID_ENV=development` in `.env`
2. Run the link script
3. Complete the real bank login flow

### 4. Test It Out

Start your bot and try these commands:
```
What's my bank balance?
Show me my recent transactions
How much did I spend on food this month?
What are my spending categories?
```

## Features

### Available Bot Commands

| Command | Description |
|---------|-------------|
| "What's my bank balance?" | Shows current balance across all accounts |
| "Show me recent transactions" | Lists transactions from the last 30 days |
| "Show me transactions from the past week" | Recent 7-day transactions |
| "How much did I spend this month?" | Total spending breakdown |
| "What did I spend on groceries?" | Category-specific spending |
| "What accounts do I have?" | Lists all linked accounts |

### Tools Available to Your Bot

1. **get_bank_balances** - Get current account balances
2. **get_recent_transactions** - View transaction history
3. **get_spending_by_category** - Analyze spending patterns
4. **get_bank_accounts** - List linked accounts

## Environment Variables

Add these to your `.env` file:

```bash
# Plaid Configuration
PLAID_CLIENT_ID=your_client_id_here
PLAID_SECRET=your_secret_here
PLAID_ENV=sandbox  # or 'development' or 'production'
```

## Plaid Environments

### Sandbox (Free Testing)
- ✅ Unlimited API calls
- ✅ Test with fake bank credentials
- ✅ Perfect for development
- ❌ No real financial data

**Test Credentials:**
- Username: `user_good`
- Password: `pass_good`

### Development (Limited Free)
- ✅ Connect to real banks
- ✅ 100 free Items (bank connections)
- ⚠️ Limited to 100 API calls/day
- Use for testing before production

### Production (Paid)
- ✅ Full access to all banks
- ✅ Real financial data
- 💰 Paid based on usage
- 🔒 Requires compliance review

## Security Best Practices

### ✅ DO:
- Store credentials in `.env` file (never commit to git)
- Add `data/plaid_tokens.json` to `.gitignore`
- Use environment variables for all secrets
- Regularly rotate API keys
- Use Sandbox for testing

### ❌ DON'T:
- Hardcode API credentials in code
- Commit `plaid_tokens.json` or `.env` to version control
- Share your API keys publicly
- Use Production credentials for testing

## File Structure

```
skills/plaid/
├── plaid.md                 # Skill documentation
├── plaid_integration.py     # Core Plaid integration
├── link_account.py          # Helper script to link banks
└── README.md               # This file

src/tools/
└── plaid_tools.py          # LLM function calling tools

data/
└── plaid_tokens.json       # Access tokens (NEVER COMMIT)
```

## Troubleshooting

### "Missing Plaid credentials" Error
**Solution:** Make sure `PLAID_CLIENT_ID` and `PLAID_SECRET` are set in your `.env` file.

```bash
# Check if variables are set
grep PLAID .env
```

### "No linked bank accounts found"
**Solution:** You need to link a bank account first.

```bash
python3 skills/plaid/link_account.py
```

### Import Errors
**Solution:** Install the Plaid package.

```bash
pip install plaid-python>=20.0.0
```

### Rate Limit Errors
- **Sandbox**: No limits
- **Development**: 100 Items, limited daily calls
- **Production**: Based on your plan

**Solution:** Upgrade your Plaid account or use Sandbox for testing.

## Advanced Usage

### Caching Transaction Data

For better performance, consider caching transaction data locally (similar to the Walmart orders integration):

```python
# TODO: Add SQLite database for transaction caching
# Benefits:
# - Faster queries
# - Offline access
# - Historical data analysis
# - Reduced API calls
```

### Multiple Bank Accounts

The integration supports multiple bank connections. Each bank gets a unique identifier:

```python
# Link multiple banks
plaid.exchange_public_token(token1, "chase_checking")
plaid.exchange_public_token(token2, "wells_fargo_savings")
```

### Custom Date Ranges

```python
# Get transactions for specific date range
from datetime import datetime, timedelta

start = datetime(2026, 1, 1)
end = datetime(2026, 1, 31)
transactions = plaid.get_transactions(start, end)
```

## API Reference

- **Official Docs**: https://plaid.com/docs/
- **Python Client**: https://github.com/plaid/plaid-python
- **API Quickstart**: https://plaid.com/docs/quickstart/
- **Sandbox Testing**: https://plaid.com/docs/sandbox/

## Cost Information

| Plan | Price | Includes |
|------|-------|----------|
| Sandbox | Free | Unlimited test data |
| Development | Free | 100 Items, limited calls |
| Production | Pay-as-you-go | $0.35 per Item/month + transaction fees |

**Note:** "Items" = unique bank connections

## Support

- Plaid Support: https://plaid.com/contact/
- Documentation: https://plaid.com/docs/
- Status Page: https://status.plaid.com/

## Next Steps

1. ✅ Complete the Quick Start guide
2. ✅ Link a test bank in Sandbox mode
3. ✅ Try the bot commands
4. 📝 Consider adding transaction caching
5. 🚀 When ready, upgrade to Production

---

**Need Help?** Check the [Plaid documentation](https://plaid.com/docs/) or review the code in `plaid_integration.py`.
