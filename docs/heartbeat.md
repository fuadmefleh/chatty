# Autonomous Heartbeat

This file defines what the AI agent should consider doing autonomously when not actively chatting with users.

## Description

The heartbeat system allows the AI to perform periodic checks and autonomous actions without direct user prompting. This file is checked every 15 minutes (configurable via HEARTBEAT_INTERVAL_MINUTES in .env).

**After each heartbeat cycle, the bot sends you a Telegram summary of all completed activities.**

> **Note:** the sections below describe the autonomous behavior; they are not
> re-parsed by the LLM on every tick. What actually executes is a set of
> hardcoded methods in `src/managers/heartbeat_manager.py`
> (`_process_gmail_cleanup`, `_process_walmart_orders`,
> `_process_budget_analysis`, `_process_world_watch`,
> `_process_memory_watch_suggestions`, `_process_daily_briefing`,
> `_process_self_upgrade_ideas`, etc.), each computing its own results and
> sending Telegram messages directly when warranted.

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

### 6. World Watch (Priority: Medium)
- For each topic on the user's watchlist (added via chat, e.g. "keep an eye on X"),
  check its source at most once per its own interval:
  - **news** topics: fresh web search via SearXNG, at most once per `WORLD_WATCH_INTERVAL_HOURS` (default: daily)
  - **stock** topics: day-change % via Yahoo Finance, at most once per `STOCK_WATCH_INTERVAL_HOURS` (default: every 4h);
    alerts when the move exceeds `STOCK_WATCH_MOVE_THRESHOLD_PERCENT` (default: 5%)
  - **github** topics: new releases/commits via the GitHub API, at most once per `GITHUB_WATCH_INTERVAL_HOURS` (default: every 12h)
- Skip topics that were already checked within their interval
- Compare new results against previously-seen sources/markers to avoid repeating old news
- Summarize genuinely notable updates; skip recycled or low-value results entirely
- Send a Telegram message with the summary and source links for each notable update
- Save every surfaced update as an Insight, viewable on the web dashboard's Insights page

### 7. Memory-Driven Watch Suggestions (Priority: Low)
- At most once per `MEMORY_SUGGESTION_INTERVAL_HOURS` (default: weekly), mine long-term
  memory for recurring topics, goals, and projects worth proactively watching
- Never auto-adds anything - just sends a Telegram suggestion the user can accept the normal
  way ("watch X")
- Tracks what's already been suggested so it doesn't repeat the same suggestion every week

### 8. Daily Briefing (Priority: Low)
- Once per day, at local hour `DAILY_BRIEFING_HOUR` (default: 8am), send a single digest combining:
  - Weather (if `HOME_LOCATION` is configured)
  - This month's spending snapshot
  - Reminders due today
  - Insights surfaced in the last 24 hours
- Additive to the other real-time proactive messages above, not a replacement for them -
  time-sensitive alerts (e.g. a stock move) still arrive immediately when they happen

### 9. Memory Maintenance
- Monitor memory file sizes (both short-term and long-term)
- Ensure archived memories are properly stored
- Check memory integrity
- Optimize storage if needed

### 10. System Health Checks
- Verify all systems are operational
- Check API connections (OpenAI, Telegram)
- Log any issues detected

### 11. Proactive User Engagement (Optional)
- Check if any users have birthdays coming up (from memory)
- Look for follow-up opportunities on previous conversations
- Send gentle check-ins to users who haven't interacted in a while (be respectful, not intrusive)

### 12. Self-Upgrade (Priority: Low, Safety-Gated)
- At most once per `SELF_UPGRADE_INTERVAL_HOURS` (default: weekly), reflect on: current
  skills/tool coverage, recent error logs, past self-upgrade attempts (to avoid repeating
  ideas), and recent conversation history (to catch frustrations or unmet requests)
- Propose ONE small, concrete improvement to Chatty's own codebase - or nothing, if there
  isn't a genuinely good idea
- Implement it end-to-end via `src/managers/self_upgrade_manager.py`:
  - Create an isolated git worktree on a new branch off `main` (never edits the live checkout)
  - Run the Pi coding agent inside that worktree
  - Commit, then run the full test suite (+ frontend typecheck/build if frontend files changed)
  - If the tests fail, feed the failure output back to Pi for a fix attempt in the same
    worktree and try again - up to `SELF_UPGRADE_MAX_TEST_ATTEMPTS` total attempts (default: 3)
    - the retry prompt also reminds it of this repo's pytest-asyncio marker convention, since
      that's the most common way a self-written test silently fails to even run
  - **Only if all of the following hold** does it merge and restart: tests pass, the live
    `main` checkout has no uncommitted changes, and `main` is actually checked out
  - Any failure at any stage (including running out of fix attempts) leaves the branch/worktree
    in place for manual review - `main` is never touched unless the full gate passes
- Every attempt (successful or not) shows up on the dashboard's Requests page tagged
  🤖 self-upgrade, alongside a Telegram notification
- A cross-process file lock (`skills/pi_agent/lock.py`) prevents this from ever running
  the Pi coding agent at the same time as a manually-submitted dashboard feature request

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
