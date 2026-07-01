# Autonomous Heartbeat

This file defines what the AI agent should consider doing autonomously when not actively chatting with users.

## Description

The heartbeat system allows the AI to perform periodic checks and autonomous actions without direct user prompting. This file is checked every 15 minutes (configurable via HEARTBEAT_INTERVAL_MINUTES in .env).

**After each heartbeat cycle, the bot sends you a Telegram summary of all completed activities.**

## Autonomous Tasks

### 1. Memory Consolidation (Priority: High)
- Review short-term memories (daily chat logs) older than 7 days
- Analyze conversations for important long-term information:
  - Personal preferences and habits
  - Important facts (name, location, job, relationships)
  - Goals and ongoing projects
  - Recurring topics and interests
  - Key decisions and insights
- Consolidate findings into long-term memory categories
- Archive processed short-term memory files

### 2. Long-Term Memory Cleanup (Priority: High)
- Analyze all long-term memory files for duplicates and redundancies
- Remove duplicate entries while preserving unique information
- Consolidate related information into organized sections
- Maintain data integrity and keep the most recent/accurate versions
- Reorganize content for clarity and easy retrieval

### 3. Check and Send Pending Reminders
- Review upcoming reminders for all users
- Send notifications for reminders that are due
- Clean up expired or sent reminders

### 4. Gmail Inbox Cleanup and Organization (Priority: High)
- Archive old read emails (30+ days in inbox)
- Archive promotional emails (marketing, newsletters)
- Archive old social media notifications
- Keep inbox clean and organized
- Maintain only recent and actionable emails in inbox
- Report on cleanup activities and inbox health

### 5. Budget Analysis and Financial Insights (Priority: High)
- Analyze current month's spending across all accounts
- Compare spending against budget targets by category
- Identify categories approaching or exceeding budget limits
- Calculate daily spending rate and project month-end totals
- Generate actionable recommendations for staying within budget
- Send Telegram alerts for critical budget concerns:
  - Categories that are over budget
  - Projected overspending based on current trends
  - High-priority spending recommendations
- Help user understand spending patterns and make better financial decisions

### 6. Memory Maintenance
- Monitor memory file sizes (both short-term and long-term)
- Ensure archived memories are properly stored
- Check memory integrity
- Optimize storage if needed

### 7. System Health Checks
- Verify all systems are operational
- Check API connections (OpenAI, Telegram)
- Log any issues detected

### 8. Proactive User Engagement (Optional)
- Check if any users have birthdays coming up (from memory)
- Look for follow-up opportunities on previous conversations
- Send gentle check-ins to users who haven't interacted in a while (be respectful, not intrusive)

## Guidelines

When processing this heartbeat:
1. **Be Non-Intrusive**: Don't spam users. Only send messages when truly relevant.
2. **Be Thoughtful**: Consider context from memory before reaching out.
3. **Be Helpful**: Focus on genuinely useful autonomous actions.
4. **Be Efficient**: Keep processing lightweight to avoid resource drain.
5. **Send Summary**: After each cycle, send a concise summary of completed activities to the user via Telegram.

## Heartbeat Summary

After each heartbeat cycle, users receive a Telegram message with:
- ⏰ Timestamp of the heartbeat
- 📋 List of activities completed (memory consolidation, Gmail cleanup, budget analysis, etc.)
- ✅ Status indicators for each task

Example summary:
```
💓 Heartbeat Summary
⏰ 2026-02-01 03:45 PM

Activities completed:

• 📧 Gmail: Archived 15 emails (inbox: 247 → 232)
• 💰 Budget: All spending within budget ✅
• 🧠 Memory consolidation: Processed memories for 1 user(s)

✅ All heartbeat tasks completed successfully
```

## Current Active Tasks

[You can add specific tasks here that the AI should autonomously work on]

- None currently

## Notes

- The heartbeat runs in the background every HEARTBEAT_INTERVAL_MINUTES
- Each heartbeat execution is logged for monitoring
- You can add or remove tasks by editing this file
- Changes take effect on the next heartbeat cycle
