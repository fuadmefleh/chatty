#!/bin/bash
# Setup script for Plaid integration

echo "=== Plaid Integration Setup ==="
echo ""

# Check if .env file exists
if [ ! -f .env ]; then
    echo "Creating .env file..."
    touch .env
fi

# Check for existing Plaid credentials
if grep -q "PLAID_CLIENT_ID" .env; then
    echo "✓ Plaid credentials already configured in .env"
else
    echo "📝 Setting up Plaid credentials..."
    echo ""
    echo "Please enter your Plaid credentials (get them from https://dashboard.plaid.com):"
    echo ""
    
    read -p "Plaid Client ID: " client_id
    read -p "Plaid Secret: " secret
    read -p "Environment (sandbox/development/production) [sandbox]: " env
    env=${env:-sandbox}
    
    echo "" >> .env
    echo "# Plaid Configuration" >> .env
    echo "PLAID_CLIENT_ID=$client_id" >> .env
    echo "PLAID_SECRET=$secret" >> .env
    echo "PLAID_ENV=$env" >> .env
    
    echo "✓ Plaid credentials added to .env"
fi

# Create data directory if it doesn't exist
mkdir -p data

# Check if plaid_tokens.json is in .gitignore
if [ -f .gitignore ]; then
    if grep -q "data/plaid_tokens.json" .gitignore; then
        echo "✓ plaid_tokens.json already in .gitignore"
    else
        echo "data/plaid_tokens.json" >> .gitignore
        echo "✓ Added plaid_tokens.json to .gitignore"
    fi
else
    echo "data/plaid_tokens.json" > .gitignore
    echo "✓ Created .gitignore with plaid_tokens.json"
fi

# Install Plaid dependency
echo ""
echo "📦 Installing plaid-python..."
source venv/bin/activate 2>/dev/null || true
pip install plaid-python>=20.0.0

echo ""
echo "✅ Plaid integration setup complete!"
echo ""
echo "Next steps:"
echo "1. Make sure your .env file has the correct Plaid credentials"
echo "2. Start your bot with ./start.sh"
echo "3. Ask your bot: 'What's my bank balance?'"
echo "4. In Sandbox mode, use these test credentials when prompted:"
echo "   - Username: user_good"
echo "   - Password: pass_good"
echo ""
echo "For production use, update PLAID_ENV to 'production' and use real credentials."
