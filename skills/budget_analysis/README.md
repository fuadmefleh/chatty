# Budget Analysis Skill

## Overview
The Budget Analysis skill provides intelligent spending analysis, budget monitoring, and financial insights. It automatically tracks your spending across all connected accounts and alerts you to potential budget concerns.

## Features

### 🎯 Core Capabilities
- **Monthly Spending Analysis**: Aggregates and categorizes all transactions for the current month
- **Budget Monitoring**: Compares spending against predefined budget targets
- **Smart Alerts**: Identifies categories approaching or exceeding budget limits
- **Spending Insights**: Analyzes daily spending rates and projects month-end totals
- **Actionable Recommendations**: Provides specific advice on how to stay within budget

### 📊 Budget Categories
The analyzer tracks spending across these categories with default targets:
- Groceries: $600/month
- Dining & Drinks: $300/month
- Shopping: $400/month
- Entertainment: $200/month
- Gas & Fuel: $200/month
- Transportation: $150/month
- Bills & Utilities: $500/month
- Health & Medical: $200/month
- **Total Monthly Target**: $3,000

### 🚨 Alert Levels
- **Critical (🚨)**: Category is at or over 100% of budget - immediate action needed
- **Warning (⚠️)**: Category is at 80-99% of budget - caution advised
- **Good (✅)**: Category is under 80% of budget - on track

## Usage

### Chat Commands
Ask your bot questions like:
- "How am I doing with my budget this month?"
- "What categories am I overspending on?"
- "Show me my spending breakdown"
- "Am I on track to stay within budget?"
- "What should I be concerned about financially?"
- "Give me my budget report"

### Available Tools
1. **analyze_monthly_budget**: Get comprehensive spending analysis
2. **get_budget_alerts**: Get only critical alerts that need attention
3. **generate_budget_report**: Get a formatted budget summary

### Autonomous Heartbeat Integration
The budget analyzer runs automatically during heartbeat cycles:
- Analyzes spending without being asked
- Sends Telegram alerts for critical budget issues
- Provides proactive recommendations
- Warns about projected overspending trends

## Data Sources
The budget analyzer pulls data from:
1. **Rocket Money** (Primary): Most comprehensive transaction data with proper categorization
2. **Plaid** (Fallback): Bank account transactions if Rocket Money unavailable

## How It Works

### Analysis Process
1. Retrieves all transactions for the current month
2. Aggregates spending by category
3. Compares against budget targets
4. Calculates daily spending rate
5. Projects month-end totals based on current trends
6. Generates warnings for over-budget categories
7. Provides specific, actionable recommendations

### Alert Generation
Alerts are sent via Telegram when:
- Any category exceeds its budget (critical alert)
- Any category is at 80%+ of budget (warning)
- Daily spending rate projects >10% over monthly budget
- Specific recommendations are available to reduce spending

### Example Alert
```
💰 Budget Analysis Alert

You have some budget concerns that need attention:

🚨 OVER BUDGET: Dining & Drinks - $345.23 spent ($300.00 budget, 115%)
⚠️  WARNING: Groceries - $510.75 spent ($600.00 budget, 85%)
🚨 BUDGET ALERT: Based on current spending ($105.50/day), you're projected to exceed your monthly budget by $165.00

📊 Full report:
💰 Budget Report - February 2026
========================================

Total Spending: $1,523.45 / $3,000.00 (51%)

Category Breakdown:
  🚨 Dining & Drinks: $345.23 / $300.00 (115%)
  ⚠️  Groceries: $510.75 / $600.00 (85%)
  ✅ Shopping: $234.56 / $400.00 (59%)
  ✅ Entertainment: $98.45 / $200.00 (49%)
  ...

Recommendations:
  🛑 Dining & Drinks: Stop non-essential spending immediately. You're $45.23 over budget.
  ⚠️  Groceries: Only $89.25 left in budget. Consider reducing spending for the rest of the month.
```

## Configuration

### Customizing Budget Targets
Edit [budget_analyzer.py](budget_analyzer.py) and modify the `monthly_budget_targets` dictionary:

```python
self.monthly_budget_targets = {
    "Groceries": 600,        # Your custom amount
    "Dining & Drinks": 300,
    "Shopping": 400,
    # ... etc
    "Total": 3000
}
```

### Adjusting Alert Thresholds
In [budget_analyzer.py](budget_analyzer.py):
```python
self.warning_threshold = 0.80   # 80% of budget triggers warning
self.critical_threshold = 1.0    # 100%+ triggers critical alert
```

## Testing

Run the budget analyzer directly to test:
```bash
cd /home/edgeworks-server/chatty
python3 skills/budget_analysis/budget_analyzer.py
```

This will:
1. Analyze current month's spending
2. Display actionable alerts
3. Show a formatted budget report

## Files

- **budget_analyzer.py**: Core analysis logic and alert generation
- **tools.py**: LLM function calling tools for chat integration
- **budget_analysis.md**: Skill description for the agent
- **README.md**: This file

## Integration with Other Skills

The budget analyzer integrates with:
- **Rocket Money**: Primary transaction data source
- **Plaid**: Fallback bank account data
- **Heartbeat Manager**: Autonomous budget monitoring
- **Telegram Bot**: Alert delivery system

## Future Enhancements

Potential improvements:
- [ ] Per-user budget customization via chat
- [ ] Historical spending trend analysis
- [ ] Predictive spending forecasts using ML
- [ ] Anomaly detection for unusual transactions
- [ ] Budget goal setting and tracking
- [ ] Spending comparison across months
- [ ] Category spending visualizations
- [ ] Integration with more financial data sources

## Troubleshooting

### No Budget Data Available
- Ensure Rocket Money CSV is imported: Check `data/rocketmoney/` for transaction files
- Or ensure Plaid is configured: Run `python3 skills/plaid/link_account.py`

### Alerts Not Sending
- Check heartbeat is running: Look for heartbeat logs
- Verify Telegram callback is set: Check `heartbeat_manager.set_send_message_callback()`
- Ensure user is authorized: User must be in `authorized_users` dict

### Incorrect Budget Amounts
- Verify transaction categorization in Rocket Money
- Check that budget targets match your actual budget
- Look for duplicate transactions

## Support

For issues or questions:
1. Check the logs: `logs/heartbeat.log` and `logs/main.log`
2. Test manually: Run `python3 skills/budget_analysis/budget_analyzer.py`
3. Verify data sources: Check that transaction data is available
