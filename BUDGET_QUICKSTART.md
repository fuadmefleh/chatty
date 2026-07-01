# Budget Analysis Quick Start Guide

## 🚀 Your Bot Now Has Budget Intelligence!

Your bot will now automatically analyze your spending and send you Telegram alerts about budget concerns during heartbeat cycles.

## ⚡ Quick Start

### 1. The Bot is Already Running
The budget analysis runs automatically every hour as part of the heartbeat system. No setup needed!

### 2. Test It Right Now

#### Option A: Trigger Heartbeat Manually
In Telegram, send to your bot:
```
/heartbeat
```

This will immediately run the budget analysis and send you alerts if there are any concerns.

#### Option B: Ask About Your Budget
Just chat with your bot:
```
How am I doing with my budget?
```
```
What should I look at financially?
```
```
Show me my spending breakdown
```

### 3. Import New Transactions (Optional)
To get current month data, import your latest Rocket Money CSV:
```bash
# Download latest transactions from Rocket Money
# Place CSV in: /home/edgeworks-server/chatty/data/rocketmoney/

# The bot will auto-import during heartbeat, or import manually:
cd /home/edgeworks-server/chatty
python3 skills/rocketmoney/rocketmoney_parser.py data/rocketmoney/your-file.csv
```

## 📱 What You'll Receive

### When Things Need Attention
You'll get a Telegram message like:
```
💰 Budget Analysis Alert

You have some budget concerns that need attention:

🚨 OVER BUDGET: Dining & Drinks - $345.23 spent ($300.00 budget, 115%)
⚠️  WARNING: Groceries - $510.75 spent ($600.00 budget, 85%)

📊 Full report:
[Complete breakdown of all categories]
```

### When Everything is Good
No spam! The bot only messages you when there are actual concerns.

## 🎯 Budget Categories Being Monitored

| Category | Monthly Budget | Alert Threshold |
|----------|----------------|-----------------|
| Groceries | $600 | $480 (80%) |
| Dining & Drinks | $300 | $240 (80%) |
| Shopping | $400 | $320 (80%) |
| Entertainment | $200 | $160 (80%) |
| Gas & Fuel | $200 | $160 (80%) |
| Transportation | $150 | $120 (80%) |
| Bills & Utilities | $500 | $400 (80%) |
| Health & Medical | $200 | $160 (80%) |
| **TOTAL** | **$3,000** | **$2,400 (80%)** |

## 💬 Example Conversations

### Check Budget Status
**You:** How am I doing with my budget this month?

**Bot:** *Analyzes spending and provides detailed breakdown with insights*

### Get Specific Category Info
**You:** How much have I spent on groceries?

**Bot:** *Shows grocery spending with trend analysis*

### Get Recommendations
**You:** What should I be concerned about financially?

**Bot:** *Provides only critical alerts and actionable recommendations*

## ⚙️ Customize Your Budgets

Edit the file: `skills/budget_analysis/budget_analyzer.py`

Find this section:
```python
self.monthly_budget_targets = {
    "Groceries": 600,          # Change these amounts
    "Dining & Drinks": 300,
    "Shopping": 400,
    # ... etc
}
```

Change the amounts to match your actual budget, then restart the bot.

## 🔄 How Often Does It Check?

- **Default**: Every 60 minutes (1 hour)
- **Customizable**: Edit `HEARTBEAT_INTERVAL_MINUTES` in `.env`

To check more frequently (e.g., every 30 minutes):
```bash
# Edit .env file
HEARTBEAT_INTERVAL_MINUTES=30
```

Then restart: `./start.sh`

## 🧪 Test the System

### Test 1: Manual Budget Check
```bash
cd /home/edgeworks-server/chatty
python3 test_budget_analysis.py
```

### Test 2: Trigger Heartbeat
In Telegram:
```
/heartbeat
```

### Test 3: Ask Your Bot
In Telegram:
```
What's my budget status?
```

## 📊 Understanding the Reports

### Budget Status Icons
- ✅ **Green/Good**: Under 80% of budget - doing great!
- ⚠️  **Yellow/Warning**: 80-99% of budget - watch it
- 🚨 **Red/Critical**: 100%+ of budget - overspending!

### Key Metrics
- **Total Spending**: How much spent this month so far
- **Daily Average**: Your average spending per day
- **Projected Total**: Estimated end-of-month spending at current rate
- **Budget %**: What percentage of budget you've used

## 🛠️ Troubleshooting

### Not Getting Alerts?
1. **Check the bot is running**: `ps aux | grep python3 | grep main.py`
2. **Verify heartbeat is working**: Send `/heartbeat` in Telegram
3. **Check logs**: `tail -f logs/heartbeat.log`

### No Spending Data?
1. **Import Rocket Money CSV**: Place in `data/rocketmoney/`
2. **Or link Plaid account**: Run `python3 skills/plaid/link_account.py`
3. **Verify data**: `python3 test_budget_analysis.py`

### Wrong Budget Amounts?
- Edit: `skills/budget_analysis/budget_analyzer.py`
- Change the `monthly_budget_targets` dict
- Restart the bot

## 📈 What Happens Automatically

Every hour (or your configured interval):

1. ✅ Bot wakes up (heartbeat cycle)
2. ✅ Analyzes all spending for current month
3. ✅ Compares against budget targets
4. ✅ Calculates spending trends
5. ✅ Generates insights and recommendations
6. ✅ **Sends Telegram alerts if needed**
7. ✅ Logs everything for your review

**All automatic. No action required from you!**

## 🎉 You're Done!

Your bot is now monitoring your budget 24/7 and will proactively alert you via Telegram whenever there are concerns. Just keep importing your transaction data, and the bot will handle the rest!

## 💡 Tips

1. **Import transactions weekly** to keep analysis current
2. **Adjust budgets** based on actual spending patterns  
3. **Use `/heartbeat`** to get immediate updates
4. **Ask questions naturally** - the bot understands context
5. **Check logs** if you want to see detailed analysis history

---

**Questions or Issues?**
- Check logs: `logs/heartbeat.log` and `logs/main.log`
- Test manually: `python3 test_budget_analysis.py`
- View summary: See `BUDGET_ANALYSIS_SUMMARY.md`

**Happy budgeting! 💰✨**
