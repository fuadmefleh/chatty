# Heartbeat Summary Feature

## Overview

The bot now sends you a Telegram message after each heartbeat cycle with a summary of all activities it completed autonomously.

## What You'll Receive

Every hour (or at your configured `HEARTBEAT_INTERVAL_MINUTES`), you'll get a message like:

```
💓 Heartbeat Summary
⏰ 2026-02-01 03:45 PM

Activities completed:

• 📧 Gmail: Archived 15 emails (inbox: 247 → 232)
• 💰 Budget: All spending within budget ✅
• 🛒 Walmart: Processed 1 order(s)
• 🧠 Memory consolidation: Processed memories for 1 user(s)
• 🗂️ Memory cleanup: Organized memories for 1 user(s)

✅ All heartbeat tasks completed successfully
```

## What's Included

The summary reports on:

1. **📧 Gmail Cleanup**
   - Number of emails archived
   - Inbox count before and after
   - Status if inbox is already clean

2. **💰 Budget Analysis**
   - Whether spending is within budget
   - Number of alerts sent if concerns found
   - Status of budget monitoring

3. **🛒 Walmart Orders**
   - Number of order PDFs processed
   - Only shown if orders were processed

4. **🧠 Memory Consolidation**
   - Number of users whose memories were consolidated
   - Only shown if consolidation occurred

5. **🗂️ Memory Cleanup**
   - Number of users whose long-term memories were organized
   - Only shown if cleanup occurred

## When Summaries Are Sent

- ✅ **Always**: After every heartbeat cycle
- 📋 **Content**: Only activities that actually occurred
- 🚫 **Silence**: If no activities were performed, no summary is sent

## Manual Heartbeat

You can manually trigger a heartbeat anytime with:
```
/heartbeat
```

This will immediately run a heartbeat cycle and send you the summary.

## Configuration

The heartbeat interval is controlled in your `.env` file:
```env
HEARTBEAT_INTERVAL_MINUTES=60  # Default: 60 minutes
```

Change this value to adjust how often heartbeats run.

## Why This Feature?

Benefits:
- 👀 **Visibility**: Know what your bot is doing autonomously
- 📊 **Transparency**: See all background activities at a glance
- ✅ **Confirmation**: Verify tasks are running as expected
- 🔍 **Debugging**: Easier to spot issues with autonomous tasks
- 🎯 **Awareness**: Stay informed about your Gmail, budget, and system health

## Notes

- Summaries are only sent if activities were performed
- Each activity reports its own status (success, skipped, error)
- Budget alerts are sent separately when concerns are found
- The summary is sent to all authorized users via Telegram
