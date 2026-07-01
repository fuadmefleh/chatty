# Gmail Cleanup and Organization - Implementation Summary

## Overview
Added comprehensive email cleanup and organization capabilities to the chatbot's heartbeat system. The bot will now autonomously maintain a clean, organized inbox during its periodic heartbeat cycles.

## What Was Added

### 1. Gmail Integration Enhancements (`skills/gmail/gmail_integration.py`)

**New Scopes:**
- Added `gmail.modify` scope to enable email management operations

**New Functions:**
- `mark_as_read(message_ids)` - Mark emails as read
- `archive_emails(message_ids)` - Archive emails (remove from inbox, keep in All Mail)
- `trash_emails(message_ids)` - Move emails to trash
- `add_label(message_ids, label_name)` - Add labels to emails for organization
- `get_promotional_emails(max_results)` - Get promotional category emails
- `get_old_read_emails(days, max_results)` - Get old read emails from inbox
- `get_social_emails(max_results)` - Get social media notification emails

### 2. New Gmail Tools (`skills/gmail/tools.py`)

**New SkillTool Classes:**
- `MarkAsRead` - Mark emails as read
- `ArchiveEmails` - Archive emails from inbox
- `TrashEmails` - Move emails to trash
- `AddLabel` - Add custom labels to emails
- `GetPromotionalEmails` - Find promotional emails
- `GetOldReadEmails` - Find old read emails for cleanup

These tools are now available for the AI to use during conversations and autonomous operations.

### 3. Heartbeat Integration (`src/managers/heartbeat_manager.py`)

**New Method: `_process_gmail_cleanup()`**

This method runs during every heartbeat cycle and performs:

1. **Archive Old Read Emails**
   - Archives inbox emails that are 30+ days old and already read
   - Keeps inbox focused on recent, actionable items
   
2. **Archive Promotional Emails**
   - Archives emails in the Promotions category
   - Removes marketing and newsletter clutter
   
3. **Archive Social Media Notifications**
   - Archives social media notifications and updates
   - Reduces notification spam
   
4. **Batch Processing**
   - Processes emails in batches of 50 (Gmail API limit)
   - Handles large volumes efficiently
   
5. **Logging and Reporting**
   - Logs all cleanup activities
   - Reports inbox statistics before and after cleanup
   - Tracks total emails archived

### 4. Documentation Updates

**Updated Files:**
- `docs/heartbeat.md` - Added Gmail cleanup as Priority: High autonomous task
- `skills/gmail/gmail.md` - Updated with new capabilities and examples

## How It Works

### Automatic Cleanup (Heartbeat)
Every 15 minutes (configurable), the heartbeat system will:
1. Check Gmail configuration (if token exists)
2. Get inbox statistics
3. Find and archive:
   - Old read emails (30+ days)
   - Promotional emails
   - Social media notifications
4. Report cleanup results in logs

### Manual Usage
Users can also ask the bot to:
- "Clean up my inbox"
- "Archive old emails"
- "Mark promotional emails as read"
- "Add labels to organize emails"
- "Show me old read emails"

## Configuration

### First-Time Setup
The first time Gmail cleanup runs, users need to:
1. Re-authenticate with Gmail (due to new `gmail.modify` scope)
2. Grant permission for email modification
3. Delete existing `data/gmail_token.json` to trigger re-auth

### Re-Authentication Command
```bash
# Remove old token to trigger re-authentication
rm data/gmail_token.json

# Test Gmail integration
python3 skills/gmail/gmail_integration.py
```

## Safety Features

1. **Non-Destructive Operations**
   - Archive (not delete) - emails remain in All Mail
   - Trash has 30-day recovery period
   - No permanent deletions

2. **Conservative Approach**
   - Only archives old (30+ days) read emails from inbox
   - Leaves recent and unread emails untouched
   - Focuses on promotional/social categories

3. **Logging**
   - All operations logged to heartbeat logs
   - Full transparency of what was archived
   - Easy to audit and troubleshoot

## Benefits

1. **Cleaner Inbox**
   - Automatically maintains focused, actionable inbox
   - Reduces email overwhelm
   
2. **Better Organization**
   - Removes clutter automatically
   - Keeps only recent, relevant emails visible
   
3. **Time Savings**
   - No manual inbox maintenance needed
   - Runs autonomously every 15 minutes
   
4. **Flexible Control**
   - Can disable by removing Gmail token
   - Adjustable thresholds (days, categories)
   - Manual override available through conversation

## Future Enhancements

Potential additions for future versions:
- Smart categorization using AI (Finance, Travel, Shopping, etc.)
- Custom user preferences for retention periods
- Email summary notifications
- Priority inbox management
- Spam detection and cleanup
- Attachment organization
- Email thread management

## Testing

To test the implementation:

```bash
# 1. Re-authenticate Gmail (if needed)
rm data/gmail_token.json
python3 skills/gmail/gmail_integration.py

# 2. Run manual heartbeat to test cleanup
# Use the bot's /heartbeat command in Telegram

# 3. Check logs for results
tail -f logs/heartbeat.log
```

## Notes

- Gmail API has rate limits (250 quota units per user per second)
- Batch operations are used to stay within limits
- Cleanup runs during heartbeat (every 15 minutes by default)
- All archived emails remain accessible in Gmail's "All Mail"
