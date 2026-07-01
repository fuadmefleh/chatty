# Gmail Reader

## Description
Read and search your Gmail messages with secure OAuth 2.0 authentication. Access your inbox, search for specific emails, read message content, and get information about your unread messages.

## Setup

### 1. Enable Gmail API
1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the Gmail API for your project
4. Go to "Credentials" and create OAuth 2.0 credentials
5. Download the credentials JSON file and save it as `credentials.json` in the `skills/gmail/` directory

### 2. Set OAuth Scopes
The skill uses the following scopes:
- `https://www.googleapis.com/auth/gmail.readonly` - Read all resources and their metadata
- `https://www.googleapis.com/auth/gmail.modify` - Modify emails (mark as read, archive, label, trash)

### 3. Install Dependencies
```bash
pip install google-auth-oauthlib google-auth-httplib2 google-api-python-client
```

### 4. First Time Setup
The first time you use the skill, it will:
1. Open a browser window for OAuth authentication
2. Ask you to grant permissions to read your Gmail
3. Save the authentication token to `data/gmail_token.json`

## Usage
Use this skill when you need to:
- Check for new unread emails
- Search for specific emails by sender, subject, or content
- Read email messages
- Get email metadata (date, from, subject, etc.)
- Filter emails by date range
- Check emails from specific senders
- Clean up and organize your inbox
- Archive old or promotional emails
- Mark emails as read
- Add labels to emails for organization
- Move emails to trash

## Examples
- "Check my unread emails"
- "Show me emails from john@example.com"
- "Search for emails about the project meeting"
- "What are my recent emails?"
- "Show me emails from the last 3 days"
- "Read the latest email from Amazon"
- "Find emails with 'invoice' in the subject"
- "Show me all emails from this week"
- "How many unread emails do I have?"
- "Archive old promotional emails"
- "Mark these emails as read"
- "Organize my inbox by adding labels"
- "Clean up my inbox"
- "Show me old read emails to archive"

## Features
- OAuth 2.0 secure authentication
- Search emails by sender, subject, date, or content
- Read full email content (text and HTML)
- Filter by read/unread status
- Date range filtering
- Attachment detection
- Thread support
- Label/folder filtering
- Mark emails as read
- Archive emails (remove from inbox while keeping in All Mail)
- Trash emails (recoverable for 30 days)
- Add custom labels for organization
- Bulk operations support (process multiple emails at once)
- Automatic inbox cleanup during heartbeat cycles

## Privacy
- All authentication is done via OAuth 2.0
- Tokens are stored locally in `data/gmail_token.json`
- The skill only requests read-only access
- No email data is stored permanently by the skill
