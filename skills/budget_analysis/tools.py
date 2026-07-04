"""Budget Analysis skill tools for LLM function calling.

These tools are dynamically loaded by the framework when the skill is activated.
"""
import json
import logging
import sys
import importlib.util
from pathlib import Path

# Add project root to path for src imports
project_root = str(Path(__file__).parent.parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.core.skill_tool import SkillTool

# Load the budget_analyzer module from THIS skill folder explicitly
_analyzer_path = Path(__file__).parent / "budget_analyzer.py"
_spec = importlib.util.spec_from_file_location("budget_analyzer_module", _analyzer_path)
_analyzer_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_analyzer_module)

BudgetAnalyzer = _analyzer_module.BudgetAnalyzer


class AnalyzeMonthlyBudget(SkillTool):
    """Analyze current month's spending and budget status."""
    
    name = "analyze_monthly_budget"
    description = "Analyze current month's spending across all accounts and categories. Provides budget warnings, insights, and recommendations. Use this when user asks about their budget, spending this month, or financial health."
    parameters = {
        "type": "object",
        "properties": {},
        "required": []
    }
    
    async def execute(self) -> str:
        try:
            analyzer = BudgetAnalyzer()
            analysis = await analyzer.analyze_monthly_spending()
            return json.dumps(analysis, indent=2, default=str)
        except Exception as e:
            logging.error(f"Error analyzing monthly budget: {e}")
            return f"Error analyzing budget: {str(e)}"


class GetBudgetAlerts(SkillTool):
    """Get critical budget alerts and warnings."""
    
    name = "get_budget_alerts"
    description = "Get only critical budget alerts that need immediate attention - categories over budget, projected overspending, etc. Use when user asks 'what should I look at' or 'any budget concerns'."
    parameters = {
        "type": "object",
        "properties": {},
        "required": []
    }
    
    async def execute(self) -> str:
        try:
            analyzer = BudgetAnalyzer()
            alerts = await analyzer.get_actionable_alerts()
            
            if alerts:
                return json.dumps({
                    "success": True,
                    "alert_count": len(alerts),
                    "alerts": alerts
                }, indent=2)
            else:
                return json.dumps({
                    "success": True,
                    "alert_count": 0,
                    "message": "No critical budget alerts. Everything looks good!"
                }, indent=2)
                
        except Exception as e:
            logging.error(f"Error getting budget alerts: {e}")
            return f"Error getting alerts: {str(e)}"


class GenerateBudgetReport(SkillTool):
    """Generate a formatted budget summary report."""
    
    name = "generate_budget_report"
    description = "Generate a comprehensive budget report with spending breakdown, insights, and recommendations. Use when user asks for a budget summary or wants a detailed financial overview."
    parameters = {
        "type": "object",
        "properties": {},
        "required": []
    }
    
    async def execute(self) -> str:
        try:
            analyzer = BudgetAnalyzer()
            report = await analyzer.generate_summary_report()
            return report
        except Exception as e:
            logging.error(f"Error generating budget report: {e}")
            return f"Error generating report: {str(e)}"


# Export available tools
TOOLS = [
    AnalyzeMonthlyBudget,
    GetBudgetAlerts,
    GenerateBudgetReport
]
