"""Simple web interface for Plaid Link to connect real bank accounts."""
from flask import Flask, render_template_string, request, jsonify
import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project root to path (go up 3 levels: web_link.py -> plaid -> skills -> chatty)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from skills.plaid.plaid_integration import get_plaid_integration

app = Flask(__name__)

# HTML template for Plaid Link
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Link Bank Account - Chatty Bot</title>
    <script src="https://cdn.plaid.com/link/v2/stable/link-initialize.js"></script>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 800px;
            margin: 50px auto;
            padding: 20px;
            background: #f5f5f5;
        }
        .container {
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        h1 {
            color: #333;
        }
        button {
            background: #0066cc;
            color: white;
            border: none;
            padding: 15px 30px;
            font-size: 16px;
            border-radius: 5px;
            cursor: pointer;
            margin-top: 20px;
        }
        button:hover {
            background: #0052a3;
        }
        button:disabled {
            background: #ccc;
            cursor: not-allowed;
        }
        .status {
            margin-top: 20px;
            padding: 15px;
            border-radius: 5px;
        }
        .success {
            background: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
        }
        .error {
            background: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
        }
        .info {
            background: #d1ecf1;
            color: #0c5460;
            border: 1px solid #bee5eb;
        }
        .env-mode {
            display: inline-block;
            padding: 5px 10px;
            border-radius: 3px;
            font-weight: bold;
            margin-left: 10px;
        }
        .env-sandbox {
            background: #fff3cd;
            color: #856404;
        }
        .env-development {
            background: #d1ecf1;
            color: #0c5460;
        }
        .env-production {
            background: #f8d7da;
            color: #721c24;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🏦 Link Your Bank Account</h1>
        <p>Environment: <span class="env-mode env-{{ env }}">{{ env.upper() }}</span></p>
        
        {% if env == 'sandbox' %}
        <div class="status info">
            <strong>Test Mode:</strong> You're in Sandbox mode. Use these credentials:
            <ul>
                <li>Username: <code>user_good</code></li>
                <li>Password: <code>pass_good</code></li>
            </ul>
            To connect a real bank, change <code>PLAID_ENV</code> to <code>development</code> in your .env file.
        </div>
        {% elif env == 'development' %}
        <div class="status info">
            <strong>Development Mode:</strong> You can connect real bank accounts. Your bank login is secure and handled by Plaid.
        </div>
        {% else %}
        <div class="status error">
            <strong>Production Mode:</strong> Make sure you have proper compliance approval from Plaid.
        </div>
        {% endif %}
        
        <button id="link-button" onclick="startPlaidLink()">
            Connect Bank Account
        </button>
        
        <div id="status"></div>
        
        <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #ddd;">
            <h3>Already Linked Accounts:</h3>
            <div id="accounts">Loading...</div>
        </div>
    </div>

    <script>
        let linkToken = null;
        
        // Get link token on page load
        fetch('/api/create_link_token')
            .then(response => response.json())
            .then(data => {
                if (data.link_token) {
                    linkToken = data.link_token;
                    console.log('Link token received');
                } else {
                    showStatus('Error: ' + data.error, 'error');
                    document.getElementById('link-button').disabled = true;
                }
            })
            .catch(error => {
                showStatus('Error: ' + error, 'error');
                document.getElementById('link-button').disabled = true;
            });
        
        // Load existing accounts
        fetch('/api/get_accounts')
            .then(response => response.json())
            .then(data => {
                const accountsDiv = document.getElementById('accounts');
                if (data.accounts && data.accounts.length > 0) {
                    let html = '<ul>';
                    data.accounts.forEach(acc => {
                        html += `<li><strong>${acc.institution}</strong>: ${acc.name} (***${acc.mask}) - $${acc.balance_current.toFixed(2)}</li>`;
                    });
                    html += '</ul>';
                    accountsDiv.innerHTML = html;
                } else {
                    accountsDiv.innerHTML = '<p><em>No accounts linked yet.</em></p>';
                }
            })
            .catch(error => {
                document.getElementById('accounts').innerHTML = '<p><em>Could not load accounts.</em></p>';
            });
        
        function startPlaidLink() {
            if (!linkToken) {
                showStatus('Error: Link token not ready. Refresh the page.', 'error');
                return;
            }
            
            const handler = Plaid.create({
                token: linkToken,
                onSuccess: function(public_token, metadata) {
                    // Exchange public token for access token
                    showStatus('Processing...', 'info');
                    
                    const institutionName = prompt('Enter a name for this bank connection (e.g., "chase_checking"):') || 'bank';
                    
                    fetch('/api/exchange_token', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            public_token: public_token,
                            institution_name: institutionName
                        })
                    })
                    .then(response => response.json())
                    .then(data => {
                        if (data.success) {
                            showStatus('✅ Successfully linked ' + institutionName + '! Refresh the page to see it.', 'success');
                            // Reload accounts
                            setTimeout(() => location.reload(), 2000);
                        } else {
                            showStatus('Error: ' + data.error, 'error');
                        }
                    })
                    .catch(error => {
                        showStatus('Error: ' + error, 'error');
                    });
                },
                onExit: function(err, metadata) {
                    if (err != null) {
                        showStatus('Error: ' + err.error_message, 'error');
                    }
                }
            });
            
            handler.open();
        }
        
        function showStatus(message, type) {
            const statusDiv = document.getElementById('status');
            statusDiv.innerHTML = `<div class="status ${type}">${message}</div>`;
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    """Render the Plaid Link page."""
    env = os.getenv('PLAID_ENV', 'sandbox')
    return render_template_string(HTML_TEMPLATE, env=env)

@app.route('/api/create_link_token', methods=['GET'])
def create_link_token():
    """Create a Plaid Link token."""
    try:
        plaid = get_plaid_integration()
        link_token = plaid.create_link_token("default_user")
        return jsonify({'link_token': link_token})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/exchange_token', methods=['POST'])
def exchange_token():
    """Exchange public token for access token."""
    try:
        data = request.json
        public_token = data.get('public_token')
        institution_name = data.get('institution_name', 'bank')
        
        plaid = get_plaid_integration()
        access_token = plaid.exchange_public_token(public_token, institution_name)
        
        return jsonify({
            'success': True,
            'access_token': access_token[:20] + '...'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/get_accounts', methods=['GET'])
def get_accounts():
    """Get linked accounts."""
    try:
        plaid = get_plaid_integration()
        accounts = plaid.get_accounts()
        return jsonify({'accounts': accounts})
    except Exception as e:
        return jsonify({'accounts': [], 'error': str(e)})

if __name__ == '__main__':
    print("=" * 60)
    print("🏦 Plaid Bank Linking Interface")
    print("=" * 60)
    print()
    print(f"Environment: {os.getenv('PLAID_ENV', 'sandbox')}")
    print()
    print("Open your browser and go to:")
    print("    http://localhost:5555")
    print()
    print("Press Ctrl+C to stop the server.")
    print("=" * 60)
    print()
    
    app.run(host='0.0.0.0', port=5555, debug=True)
