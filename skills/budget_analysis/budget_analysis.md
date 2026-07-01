# Budget Analysis

## Description
Analyzes your spending patterns across all connected accounts and provides intelligent budget insights, warnings, and recommendations. Automatically monitors your spending against budget targets and alerts you to potential overspending.

## What This Tool Does
- **Monthly Spending Analysis**: Tracks total spending and breaks it down by category
- **Budget Monitoring**: Compares spending against predefined budget targets for each category
- **Smart Alerts**: Identifies categories that are approaching or exceeding budget limits
- **Spending Insights**: Analyzes patterns like daily spending rate and projected month-end totals
- **Actionable Recommendations**: Provides specific advice on how to stay within budget

## When to Use This Tool
Use budget analysis when you want to:
- Check your current spending this month
- See if you're on track with your budget
- Get recommendations on where to cut spending
- Understand your spending patterns
- Get alerts about budget concerns

## Example Queries
- "How am I doing with my budget this month?"
- "What categories am I overspending on?"
- "Show me my spending breakdown"
- "Am I on track to stay within budget?"
- "What should I be concerned about financially?"

## Budget Categories
The tool tracks spending across these categories:
- **Groceries**: Food and household items ($600/month target)
- **Dining & Drinks**: Restaurants, bars, coffee shops ($300/month target)
- **Shopping**: Retail purchases, clothing, etc. ($400/month target)
- **Entertainment**: Movies, events, subscriptions ($200/month target)
- **Gas & Fuel**: Automotive fuel ($200/month target)
- **Transportation**: Public transit, rideshare ($150/month target)
- **Bills & Utilities**: Monthly bills ($500/month target)
- **Health & Medical**: Healthcare expenses ($200/month target)

**Total Monthly Budget Target**: $3,000

## Alert Levels
- **🚨 Critical**: Category is at or over 100% of budget
- **⚠️  Warning**: Category is at 80-99% of budget
- **✅ Good**: Category is under 80% of budget

## How It Works
1. Pulls transaction data from Rocket Money (primary) or Plaid (fallback)
2. Aggregates spending by category for the current month
3. Compares against budget targets
4. Calculates daily spending rate and projects month-end totals
5. Generates warnings for over-budget categories
6. Provides actionable recommendations

## Autonomous Features
During heartbeat cycles, the budget analyzer:
- Automatically analyzes monthly spending
- Sends Telegram alerts for critical budget issues
- Provides proactive spending recommendations
- Warns about projected overspending

## Data Sources
- **Rocket Money**: Primary transaction source (most comprehensive)
- **Plaid**: Fallback for bank account transactions
- **Historical Data**: Tracks trends over time

## Customization
Budget targets can be customized per user in the budget_analyzer.py configuration.
