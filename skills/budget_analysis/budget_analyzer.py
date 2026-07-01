"""Budget analysis and insights module.

Analyzes spending patterns, provides recommendations, and generates insights
from transaction data across multiple sources (Plaid, Rocket Money, etc.).
"""
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import sys

# Add project root to path
project_root = str(Path(__file__).parent.parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

logger = logging.getLogger(__name__)


class BudgetAnalyzer:
    """Analyzes spending and provides budget insights."""
    
    def __init__(self):
        """Initialize the budget analyzer."""
        self.current_date = datetime.now()
        self.current_month = self.current_date.month
        self.current_year = self.current_date.year
        
        # Budget thresholds (can be customized per user)
        self.monthly_budget_targets = {
            "Groceries": 600,
            "Dining & Drinks": 300,
            "Shopping": 400,
            "Entertainment": 200,
            "Gas & Fuel": 200,
            "Transportation": 150,
            "Bills & Utilities": 500,
            "Health & Medical": 200,
            "Total": 3000
        }
        
        # Warning thresholds (percentage of budget)
        self.warning_threshold = 0.80  # 80% of budget
        self.critical_threshold = 1.0  # 100% or over budget
    
    async def analyze_monthly_spending(self) -> Dict[str, Any]:
        """Analyze current month's spending across all sources.
        
        Returns:
            Dict with spending analysis, warnings, and recommendations
        """
        analysis = {
            "analysis_date": self.current_date.isoformat(),
            "month": self.current_month,
            "year": self.current_year,
            "total_spending": 0.0,
            "category_breakdown": {},
            "warnings": [],
            "insights": [],
            "recommendations": []
        }
        
        try:
            # Try to get Rocket Money data first
            spending_data = await self._get_rocketmoney_spending()
            
            if spending_data:
                analysis["total_spending"] = spending_data.get("total", 0.0)
                analysis["category_breakdown"] = spending_data.get("categories", {})
            else:
                # Fall back to Plaid if Rocket Money not available
                plaid_data = await self._get_plaid_spending()
                if plaid_data:
                    analysis["total_spending"] = plaid_data.get("total", 0.0)
                    analysis["category_breakdown"] = plaid_data.get("categories", {})
            
            # Generate warnings for over-budget categories
            analysis["warnings"] = self._generate_budget_warnings(analysis["category_breakdown"])
            
            # Generate insights
            analysis["insights"] = self._generate_insights(analysis)
            
            # Generate recommendations
            analysis["recommendations"] = self._generate_recommendations(analysis)
            
        except Exception as e:
            logger.error(f"Error analyzing monthly spending: {e}", exc_info=True)
            analysis["error"] = str(e)
        
        return analysis
    
    async def _get_rocketmoney_spending(self) -> Optional[Dict[str, Any]]:
        """Get spending data from Rocket Money.
        
        Returns:
            Dict with total and categories, or None if not available
        """
        try:
            from skills.rocketmoney.query_transactions import get_monthly_spending
            
            result = await get_monthly_spending(self.current_year, self.current_month)
            
            if result and not result.get("error"):
                return {
                    "total": result.get("total_spent", 0.0),
                    "categories": result.get("category_breakdown", {}),
                    "transaction_count": result.get("transaction_count", 0)
                }
            
        except Exception as e:
            logger.warning(f"Could not get Rocket Money data: {e}")
        
        return None
    
    async def _get_plaid_spending(self) -> Optional[Dict[str, Any]]:
        """Get spending data from Plaid.
        
        Returns:
            Dict with total and categories, or None if not available
        """
        try:
            import importlib.util
            
            # Load plaid integration
            integration_path = Path(__file__).parent.parent / "plaid" / "plaid_integration.py"
            spec = importlib.util.spec_from_file_location("plaid_integration", integration_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            plaid = module.get_plaid_integration()
            
            # Get transactions for current month
            days_in_month = self.current_date.day
            transactions_result = plaid.get_recent_transactions(days=days_in_month)
            
            # Parse and aggregate by category
            # This is a simplified version - would need proper parsing
            return {
                "total": 0.0,  # Would calculate from transactions
                "categories": {},
                "transaction_count": 0
            }
            
        except Exception as e:
            logger.warning(f"Could not get Plaid data: {e}")
        
        return None
    
    def _generate_budget_warnings(self, category_breakdown: Dict[str, float]) -> List[Dict[str, Any]]:
        """Generate warnings for categories approaching or exceeding budget.
        
        Args:
            category_breakdown: Dict mapping category names to spending amounts
            
        Returns:
            List of warning dicts with category, amount, budget, percentage
        """
        warnings = []
        
        for category, spent in category_breakdown.items():
            if category in self.monthly_budget_targets:
                budget = self.monthly_budget_targets[category]
                percentage = (spent / budget) if budget > 0 else 0
                
                if percentage >= self.critical_threshold:
                    warnings.append({
                        "severity": "critical",
                        "category": category,
                        "spent": spent,
                        "budget": budget,
                        "percentage": percentage,
                        "message": f"🚨 OVER BUDGET: {category} - ${spent:.2f} spent (${budget:.2f} budget, {percentage*100:.0f}%)"
                    })
                elif percentage >= self.warning_threshold:
                    warnings.append({
                        "severity": "warning",
                        "category": category,
                        "spent": spent,
                        "budget": budget,
                        "percentage": percentage,
                        "message": f"⚠️  WARNING: {category} - ${spent:.2f} spent (${budget:.2f} budget, {percentage*100:.0f}%)"
                    })
        
        return warnings
    
    def _generate_insights(self, analysis: Dict[str, Any]) -> List[str]:
        """Generate insights from spending analysis.
        
        Args:
            analysis: Analysis dict with spending data
            
        Returns:
            List of insight strings
        """
        insights = []
        
        total_spending = analysis.get("total_spending", 0.0)
        category_breakdown = analysis.get("category_breakdown", {})
        
        # Total spending insight
        total_budget = self.monthly_budget_targets.get("Total", 3000)
        if total_spending > 0:
            percentage = (total_spending / total_budget) * 100
            insights.append(f"📊 Total spending this month: ${total_spending:.2f} ({percentage:.0f}% of ${total_budget:.2f} budget)")
        
        # Find top spending category
        if category_breakdown:
            top_category = max(category_breakdown.items(), key=lambda x: x[1])
            insights.append(f"💰 Highest spending category: {top_category[0]} (${top_category[1]:.2f})")
        
        # Days remaining in month
        days_in_month = 30  # Simplified
        days_elapsed = self.current_date.day
        days_remaining = days_in_month - days_elapsed
        
        if days_remaining > 0 and total_spending > 0:
            daily_spending = total_spending / days_elapsed
            projected_total = daily_spending * days_in_month
            insights.append(f"📈 Daily spending average: ${daily_spending:.2f}/day")
            insights.append(f"📉 Projected month-end total: ${projected_total:.2f}")
            
            if projected_total > total_budget:
                overage = projected_total - total_budget
                insights.append(f"⚠️  Projected to exceed budget by ${overage:.2f}")
        
        return insights
    
    def _generate_recommendations(self, analysis: Dict[str, Any]) -> List[str]:
        """Generate actionable recommendations based on analysis.
        
        Args:
            analysis: Analysis dict with spending data
            
        Returns:
            List of recommendation strings
        """
        recommendations = []
        
        warnings = analysis.get("warnings", [])
        category_breakdown = analysis.get("category_breakdown", {})
        
        # Recommendations for over-budget categories
        for warning in warnings:
            category = warning["category"]
            spent = warning["spent"]
            budget = warning["budget"]
            overage = spent - budget
            
            if warning["severity"] == "critical":
                recommendations.append(
                    f"🛑 {category}: Stop non-essential spending immediately. "
                    f"You're ${overage:.2f} over budget."
                )
            elif warning["severity"] == "warning":
                remaining_budget = budget - spent
                recommendations.append(
                    f"⚠️  {category}: Only ${abs(remaining_budget):.2f} left in budget. "
                    f"Consider reducing spending for the rest of the month."
                )
        
        # Recommendations for categories with room in budget
        for category, spent in category_breakdown.items():
            if category in self.monthly_budget_targets:
                budget = self.monthly_budget_targets[category]
                percentage = (spent / budget) if budget > 0 else 0
                
                if percentage < 0.5:  # Less than 50% of budget used
                    remaining = budget - spent
                    recommendations.append(
                        f"✅ {category}: Good spending control! ${remaining:.2f} remaining in budget."
                    )
        
        # General recommendations if no specific warnings
        if not warnings:
            recommendations.append("✅ Great job! All categories are within budget.")
            recommendations.append("💡 Keep tracking your spending to maintain this trend.")
        
        return recommendations
    
    async def get_actionable_alerts(self) -> List[str]:
        """Get only critical alerts that require user attention.
        
        Returns:
            List of alert messages for things user should look at
        """
        alerts = []
        
        try:
            analysis = await self.analyze_monthly_spending()
            
            # Add critical warnings
            for warning in analysis.get("warnings", []):
                if warning["severity"] == "critical":
                    alerts.append(warning["message"])
            
            # Add high-priority recommendations
            for rec in analysis.get("recommendations", []):
                if rec.startswith("🛑") or rec.startswith("⚠️"):
                    alerts.append(rec)
            
            # Add projected overspending alert
            total_spending = analysis.get("total_spending", 0.0)
            total_budget = self.monthly_budget_targets.get("Total", 3000)
            
            if total_spending > 0:
                days_elapsed = self.current_date.day
                daily_spending = total_spending / days_elapsed
                projected_total = daily_spending * 30  # Assuming 30-day month
                
                if projected_total > total_budget * 1.1:  # Projected to be 10% over budget
                    overage = projected_total - total_budget
                    alerts.append(
                        f"🚨 BUDGET ALERT: Based on current spending (${daily_spending:.2f}/day), "
                        f"you're projected to exceed your monthly budget by ${overage:.2f}"
                    )
        
        except Exception as e:
            logger.error(f"Error getting actionable alerts: {e}", exc_info=True)
            alerts.append(f"⚠️  Error analyzing budget: {str(e)}")
        
        return alerts
    
    async def generate_summary_report(self) -> str:
        """Generate a formatted summary report for user notification.
        
        Returns:
            Formatted string with budget summary
        """
        try:
            analysis = await self.analyze_monthly_spending()
            
            report_lines = [
                f"💰 Budget Report - {datetime.now().strftime('%B %Y')}",
                "=" * 40,
                ""
            ]
            
            # Add spending summary
            total_spending = analysis.get("total_spending", 0.0)
            total_budget = self.monthly_budget_targets.get("Total", 3000)
            percentage = (total_spending / total_budget * 100) if total_budget > 0 else 0
            
            report_lines.append(f"Total Spending: ${total_spending:.2f} / ${total_budget:.2f} ({percentage:.0f}%)")
            report_lines.append("")
            
            # Add category breakdown
            if analysis.get("category_breakdown"):
                report_lines.append("Category Breakdown:")
                for category, amount in sorted(
                    analysis["category_breakdown"].items(),
                    key=lambda x: x[1],
                    reverse=True
                ):
                    budget = self.monthly_budget_targets.get(category, 0)
                    if budget > 0:
                        pct = (amount / budget * 100)
                        status = "✅" if pct < 80 else "⚠️" if pct < 100 else "🚨"
                        report_lines.append(f"  {status} {category}: ${amount:.2f} / ${budget:.2f} ({pct:.0f}%)")
                    else:
                        report_lines.append(f"  • {category}: ${amount:.2f}")
                report_lines.append("")
            
            # Add insights
            if analysis.get("insights"):
                report_lines.append("Insights:")
                for insight in analysis["insights"]:
                    report_lines.append(f"  {insight}")
                report_lines.append("")
            
            # Add warnings
            if analysis.get("warnings"):
                report_lines.append("⚠️  ALERTS:")
                for warning in analysis["warnings"]:
                    report_lines.append(f"  {warning['message']}")
                report_lines.append("")
            
            # Add recommendations
            if analysis.get("recommendations"):
                report_lines.append("Recommendations:")
                for rec in analysis["recommendations"][:3]:  # Top 3 recommendations
                    report_lines.append(f"  {rec}")
            
            return "\n".join(report_lines)
            
        except Exception as e:
            logger.error(f"Error generating summary report: {e}", exc_info=True)
            return f"Error generating budget report: {str(e)}"


async def execute(action: str = "analyze") -> Dict[str, Any]:
    """Execute budget analysis.
    
    Args:
        action: Action to perform ("analyze", "alerts", "report")
        
    Returns:
        Dict with results
    """
    analyzer = BudgetAnalyzer()
    
    if action == "analyze":
        return await analyzer.analyze_monthly_spending()
    elif action == "alerts":
        alerts = await analyzer.get_actionable_alerts()
        return {"success": True, "alerts": alerts}
    elif action == "report":
        report = await analyzer.generate_summary_report()
        return {"success": True, "report": report}
    else:
        return {"success": False, "error": f"Unknown action: {action}"}


if __name__ == "__main__":
    import asyncio
    
    async def test():
        analyzer = BudgetAnalyzer()
        
        print("Testing monthly spending analysis...")
        analysis = await analyzer.analyze_monthly_spending()
        print(json.dumps(analysis, indent=2, default=str))
        
        print("\n\nTesting actionable alerts...")
        alerts = await analyzer.get_actionable_alerts()
        for alert in alerts:
            print(alert)
        
        print("\n\nTesting summary report...")
        report = await analyzer.generate_summary_report()
        print(report)
    
    import json
    asyncio.run(test())
