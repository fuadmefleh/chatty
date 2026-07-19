# Gmail Integration Setup

This guide will help you set up Gmail API access for your chatbot.

## Prerequisites

- A Google account with Gmail
- Python 3.7 or higher

## Step 1: Install Required Packages

```bash
pip install google-auth-oauthlib google-auth-httplib2 google-api-python-client
```

Or add to your `requirements.txt`:
```
google-auth-oauthlib>=1.0.0
google-auth-httplib2>=0.1.0
google-api-python-client>=2.0.0
```

## Step 2: Enable Gmail API in Google Cloud Console

1. **Go to Google Cloud Console**
   - Visit https://console.cloud.google.com/

2. **Create or Select a Project**
   - Click on the project dropdown at the top
   - Click "New Project" or select an existing one
   - Give it a name like "Chatbot Gmail Integration"

3. **Enable Gmail API**
   - In the left sidebar, navigate to "APIs & Services" > "Library"
   - Search for "Gmail API"
   - Click on it and press "Enable"

4. **Create OAuth 2.0 Credentials**
   - Go to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "OAuth client ID"
   - If prompted to configure the consent screen:
     - Choose "External" user type
     - Fill in the required fields (app name, user support email, developer email)
     - Add your email to test users
     - Save and continue through the scopes (you don't need to add any here)
   - For "Application type", select "Desktop app"
   - Give it a name like "Gmail Reader"
   - Click "Create"

5. **Download Credentials**
   - After creating, click the download icon (⬇️) next to your OAuth client
   - Save the downloaded file as `credentials.json`
   - Move it to the `skills/gmail/` directory in your project

> **Web OAuth flow**: the steps above cover the desktop-app flow. The integration
> also supports a web-based OAuth callback (`web_credentials.json` +
> `GMAIL_OAUTH_REDIRECT_URI` env var) for authenticating without a local browser —
> see `gmail_integration.py` if you need that flow instead.

## Step 3: First-Time Authentication

The first time you use the Gmail integration, it will:

1. Open a browser window automatically
2. Ask you to sign in to your Google account
3. Request permission to read your Gmail (read-only access)
4. Save the authentication token to `data/gmail_token.json`

Future uses will use the saved token automatically.

## Step 4: Test the Integration

Run the test script to verify everything is working:

```bash
cd /home/edgeworks-server/chatty
source venv/bin/activate
python3 skills/gmail/gmail_integration.py
```

If successful, you should see:
- Count of unread emails
- List of recent emails with subjects and senders

## Troubleshooting

### Error: credentials.json not found
- Make sure you've downloaded the credentials file from Google Cloud Console
- Ensure it's named exactly `credentials.json`
- Place it in `skills/gmail/` directory

### Error: Access blocked
- Go to Google Cloud Console > OAuth consent screen
- Make sure your email is added to "Test users"
- The app may be in testing mode, which requires whitelisted users

### Error: Invalid grant or token expired
- Delete the `data/gmail_token.json` file
- Run the authentication flow again

### Error: Insufficient permission
- Make sure the Gmail API is enabled in your Google Cloud project
- Verify the OAuth scope includes `gmail.readonly`

## Security Notes

- The credentials file (`credentials.json`) contains your OAuth client ID and secret
- The token file (`data/gmail_token.json`) contains your authentication token
- Both files should be kept secure and not committed to version control
- Add them to your `.gitignore`:
  ```
  skills/gmail/credentials.json
  data/gmail_token.json
  ```

## API Scopes

This integration uses:
- `https://www.googleapis.com/auth/gmail.readonly` - Read-only access to Gmail
- `https://www.googleapis.com/auth/gmail.modify` - Modify/organize messages (mark read, archive, trash, label)

This means the bot can:
- ✅ Read your emails
- ✅ Search your emails
- ✅ Get email metadata
- ✅ Mark emails as read, archive them, trash them, or add labels
- ❌ Send new emails

## Usage in the Bot

Once set up, you can ask your bot:
- "Check my unread emails"
- "Show me emails from john@example.com"
- "Search for emails about the project"
- "What are my recent emails?"
- "How many unread emails do I have?"

## Rate Limits

Gmail API has usage quotas:
- 1,000,000,000 quota units per day
- Reading a message costs 5 quota units
- Listing messages costs 5 quota units

For typical personal use, you're unlikely to hit these limits.

## References

- [Gmail API Documentation](https://developers.google.com/gmail/api)
- [Python Quickstart](https://developers.google.com/gmail/api/quickstart/python)
- [OAuth 2.0 Setup](https://developers.google.com/identity/protocols/oauth2)
