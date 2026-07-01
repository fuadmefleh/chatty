"""Helper script to link a bank account via Plaid Link."""
import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project root to path (go up 3 levels: link_account.py -> plaid -> skills -> chatty)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from skills.plaid.plaid_integration import get_plaid_integration


def main():
    """Interactive script to link a bank account."""
    print("=== Plaid Bank Account Linking ===\n")
    
    try:
        plaid = get_plaid_integration()
    except ValueError as e:
        print(f"❌ Error: {e}")
        print("\nPlease run ./setup_plaid.sh first to configure your credentials.")
        return
    
    print(f"Environment: {plaid.environment}")
    print()
    
    if plaid.environment == 'sandbox':
        print("📝 SANDBOX MODE - Use test credentials:")
        print("   Username: user_good")
        print("   Password: pass_good")
        print("   Institution: Any bank (search for Chase, Bank of America, etc.)")
        print()
    
    print("To link a bank account, you need to:")
    print("1. Get a Link token from Plaid")
    print("2. Complete the Plaid Link flow in a web browser")
    print("3. Exchange the public token for an access token")
    print()
    
    # Create link token
    user_id = input("Enter a user ID (any string to identify you): ").strip() or "default_user"
    
    try:
        link_token = plaid.create_link_token(user_id)
        print(f"\n✅ Link token created: {link_token[:20]}...")
        print()
        print("Next steps:")
        print(f"1. Open Plaid Link by visiting:")
        print(f"   https://cdn.plaid.com/link/v2/stable/link-initialize.html?link_token={link_token}")
        print()
        print("2. Complete the bank login flow")
        print("3. Copy the public_token you receive")
        print("4. Run this script again and enter the public_token when prompted")
        print()
        
        # Option to exchange token
        public_token = input("If you have a public_token, paste it here (or press Enter to skip): ").strip()
        
        if public_token:
            institution_name = input("Enter a name for this bank connection (e.g., 'chase_checking'): ").strip() or "bank"
            access_token = plaid.exchange_public_token(public_token, institution_name)
            print(f"\n✅ Successfully linked {institution_name}!")
            print(f"Access token: {access_token[:20]}...")
            print()
            print("You can now ask your bot questions like:")
            print("  - What's my bank balance?")
            print("  - Show me my recent transactions")
            print("  - How much did I spend this month?")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nMake sure your Plaid credentials are correct in .env")


if __name__ == "__main__":
    main()
