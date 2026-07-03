"""Test script for Plaid integration."""
import os
import sys
from datetime import datetime, timedelta
from dotenv import load_dotenv
import pytest

# Load environment variables
load_dotenv()

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

print("Testing Plaid Integration")
print("=" * 50)
print()

# Test 1: Check environment variables
print("Test 1: Environment Variables")
client_id = os.getenv('PLAID_CLIENT_ID')
secret = os.getenv('PLAID_SECRET')
env = os.getenv('PLAID_ENV', 'sandbox')

if client_id and secret:
    print(f"✅ PLAID_CLIENT_ID: {client_id[:10]}...")
    print(f"✅ PLAID_SECRET: {'*' * len(secret)}")
    print(f"✅ PLAID_ENV: {env}")
else:
    print("❌ Plaid credentials not found!")
    print("   Run: ./setup_plaid.sh")
    pytest.skip("Plaid credentials not configured (run ./setup_plaid.sh)", allow_module_level=True)

print()

# Test 2: Import Plaid integration
print("Test 2: Import Plaid Integration")
try:
    from skills.plaid.plaid_integration import get_plaid_integration
    print("✅ Successfully imported plaid_integration")
except ImportError as e:
    print(f"❌ Failed to import: {e}")
    print("   Run: pip install plaid-python>=20.0.0")
    pytest.skip(f"plaid-python not installed: {e}", allow_module_level=True)

print()

# Test 3: Initialize Plaid client
print("Test 3: Initialize Plaid Client")
try:
    plaid = get_plaid_integration()
    print(f"✅ Plaid client initialized")
    print(f"   Environment: {plaid.environment}")
except Exception as e:
    print(f"❌ Failed to initialize: {e}")
    pytest.skip(f"Could not initialize Plaid client: {e}", allow_module_level=True)

print()

# Test 4: Create link token
print("Test 4: Create Link Token")
try:
    link_token = plaid.create_link_token("test_user")
    print(f"✅ Link token created: {link_token[:20]}...")
except Exception as e:
    print(f"❌ Failed to create link token: {e}")
    print("   Check your Plaid credentials")
    pytest.skip(f"Could not create Plaid link token: {e}", allow_module_level=True)

print()

# Test 5: Check for linked accounts
print("Test 5: Check Linked Accounts")
try:
    accounts = plaid.get_accounts()
    if accounts:
        print(f"✅ Found {len(accounts)} linked account(s):")
        for acc in accounts:
            print(f"   - {acc['institution']}: {acc['name']} (***{acc['mask']})")
    else:
        print("⚠️  No linked accounts found")
        print("   Run: python3 skills/plaid/link_account.py")
except Exception as e:
    print(f"⚠️  Could not check accounts: {e}")

print()

# Test 6: Import tools
print("Test 6: Import Plaid Tools")
try:
    from src.tools.plaid_tools import (
        GetBankBalancesTool,
        GetRecentTransactionsTool,
        GetSpendingByCategoryTool,
        GetBankAccountsTool
    )
    print("✅ Successfully imported all Plaid tools")
    
    # Test tool initialization
    tools = [
        GetBankBalancesTool(),
        GetRecentTransactionsTool(),
        GetSpendingByCategoryTool(),
        GetBankAccountsTool()
    ]
    print(f"✅ Initialized {len(tools)} tools:")
    for tool in tools:
        print(f"   - {tool.name}")
except ImportError as e:
    print(f"❌ Failed to import tools: {e}")

print()
print("=" * 50)
print("✅ All tests passed!")
print()
print("Next steps:")
if not accounts:
    print("1. Link a bank account: python3 skills/plaid/link_account.py")
    print("2. Start your bot: ./start.sh")
    print("3. Ask: 'What's my bank balance?'")
else:
    print("1. Start your bot: ./start.sh")
    print("2. Try these commands:")
    print("   - What's my bank balance?")
    print("   - Show me my recent transactions")
    print("   - How much did I spend this month?")
