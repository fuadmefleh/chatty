#!/usr/bin/env python3
"""Test script for budget analysis functionality."""
import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = str(Path(__file__).parent.parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)


async def test_budget_analyzer():
    """Test the budget analyzer."""
    print("=" * 60)
    print("Testing Budget Analysis")
    print("=" * 60)
    print()
    
    from skills.budget_analysis.budget_analyzer import BudgetAnalyzer
    
    analyzer = BudgetAnalyzer()
    
    # Test 1: Monthly spending analysis
    print("Test 1: Analyzing monthly spending...")
    print("-" * 60)
    analysis = await analyzer.analyze_monthly_spending()
    
    print(f"Analysis Date: {analysis['analysis_date']}")
    print(f"Month: {analysis['month']}/{analysis['year']}")
    print(f"Total Spending: ${analysis['total_spending']:.2f}")
    print()
    
    if analysis.get('category_breakdown'):
        print("Category Breakdown:")
        for category, amount in analysis['category_breakdown'].items():
            print(f"  {category}: ${amount:.2f}")
        print()
    
    if analysis.get('warnings'):
        print(f"⚠️  Warnings ({len(analysis['warnings'])}):")
        for warning in analysis['warnings']:
            print(f"  {warning['message']}")
        print()
    
    if analysis.get('insights'):
        print("💡 Insights:")
        for insight in analysis['insights']:
            print(f"  {insight}")
        print()
    
    if analysis.get('recommendations'):
        print("📋 Recommendations:")
        for rec in analysis['recommendations']:
            print(f"  {rec}")
        print()
    
    if analysis.get('error'):
        print(f"❌ Error: {analysis['error']}")
        print()
    
    # Test 2: Get actionable alerts
    print("\nTest 2: Getting actionable alerts...")
    print("-" * 60)
    alerts = await analyzer.get_actionable_alerts()
    
    if alerts:
        print(f"Found {len(alerts)} actionable alert(s):")
        for alert in alerts:
            print(f"  • {alert}")
    else:
        print("✅ No critical alerts - everything looks good!")
    print()
    
    # Test 3: Generate summary report
    print("\nTest 3: Generating summary report...")
    print("-" * 60)
    report = await analyzer.generate_summary_report()
    print(report)
    print()
    
    print("=" * 60)
    print("Budget Analysis Tests Complete")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_budget_analyzer())
