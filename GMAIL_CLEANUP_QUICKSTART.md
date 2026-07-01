# Gmail Cleanup - Quick Start Guide

## Important: Re-Authentication Required

Since we added the `gmail.modify` scope, you'll need to re-authenticate Gmail:

```bash
# 1. Delete the old token
rm data/gmail_token.json

# 2. Re-authenticate (this will open a browser)
python3 skills/gmail/gmail_integration.py
```

When the browser opens:
1. Sign in to your Google account
2. Grant permission to "See, edit, create, and delete your email messages"
3. The token will be saved automatically

## What the Bot Does Automatically

Every 15 minutes during heartbeat, the bot will:

### ✅ Archive Old Read Emails
- Emails in inbox that are **30+ days old** and already read
- Moves them to All Mail (not deleted)
- Keeps inbox focused on recent items

### ✅ Archive Promotional Emails  
- Marketing emails, newsletters, promotions
- Identified by Gmail's Promotions category
- Clears out marketing clutter

### ✅ Archive Social Media Emails
- Facebook, Twitter, LinkedIn notifications
- Instagram updates, etc.
- Removes notification spam

## What's Protected

The bot will **NOT** touch:
- ❌ Unread emails (always preserved)
- ❌ Recent emails (less than 30 days)
- ❌ Primary inbox emails (non-promotional)
- ❌ Important/starred emails
- ❌ Permanently delete anything (just archives)

## Manual Controls

You can also ask the bot to:

```
"Clean up my inbox"
"Show me old emails"
"Archive promotional emails"
"Mark these emails as read"
"Add label 'Important' to emails from boss@company.com"
```

## Monitoring

Check what the bot is doing:

```bash
# View heartbeat logs
tail -f logs/heartbeat.log

# Look for lines like:
# "Gmail cleanup complete - Archived X emails total"
# "Inbox stats - Total: X, Unread: Y"
```

## Disable Gmail Cleanup

If you want to stop automatic cleanup:

```bash
# Simply remove the Gmail token
rm data/gmail_token.json
```

The bot will skip Gmail cleanup if no token is found.

## Customization

Want to adjust settings? Edit these values in the code:

### `src/managers/heartbeat_manager.py`

```python
# Line ~260 - Change how old emails must be
old_emails = get_old_read_emails(days=30, max_results=100)
# Change 'days=30' to a different number

# Line ~281 - Change how many emails to process
promo_emails = get_promotional_emails(max_results=100)
# Change 'max_results=100' to process more or fewer
```

## FAQ

**Q: Will this delete my emails?**
A: No! It only archives them (moves to All Mail). Everything is still accessible.

**Q: Can I recover archived emails?**
A: Yes! They're all in Gmail's "All Mail" folder. Just search for them.

**Q: What if it archives something important?**
A: 
1. Go to Gmail
2. Search for the email
3. Move it back to Inbox manually
4. Star it so it won't be archived again

**Q: How often does this run?**
A: Every 15 minutes (configurable in `.env` with `HEARTBEAT_INTERVAL_MINUTES`)

**Q: Can I see what was archived?**
A: Yes! Check `logs/heartbeat.log` for detailed cleanup reports

## Troubleshooting

### Problem: "Gmail tools are not available"
```bash
# Install required packages
pip install google-auth-oauthlib google-auth-httplib2 google-api-python-client
```

### Problem: "Gmail not configured"
```bash
# Re-authenticate
rm data/gmail_token.json
python3 skills/gmail/gmail_integration.py
```

### Problem: "Token expired"
```bash
# Token auto-refreshes, but if it fails:
rm data/gmail_token.json
python3 skills/gmail/gmail_integration.py
```

### Problem: Rate limit errors
Gmail API has limits. The bot handles this by:
- Processing in batches of 50 emails
- Only running every 15 minutes
- If you hit limits, wait 60 seconds

## Testing

Test the cleanup manually:

```bash
# 1. Trigger a manual heartbeat via Telegram
/heartbeat

# 2. Check the logs
tail -n 50 logs/heartbeat.log

# 3. Check your Gmail inbox - old emails should be archived
```

## Next Steps

After setup:
1. ✅ Re-authenticate Gmail (see top of guide)
2. ✅ Test with `/heartbeat` command in Telegram
3. ✅ Check logs to see results
4. ✅ Open Gmail to verify inbox is cleaner
5. ✅ Let it run automatically going forward

Enjoy your automatically organized inbox! 🎉
