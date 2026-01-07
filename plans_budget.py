
"""
Budget planning utilities for AICashAdvisor.

This module provides rule-based budgeting suggestions based on user
income, current expenses, and optional user-defined rules. It uses a
default 50/30/20 model (needs/wants/savings) when no custom rules are
specified.
"""

from typing import Dict, Optional


def propose_budget(total_income: float, expenses_by_category: Dict[str, float], custom_rules: Optional[Dict[str, float]] = None) -> Dict[str, float]:
    """Generate a budget allocation.

    Args:
        total_income: The user’s monthly net income.
        expenses_by_category: Current spending grouped by category.
        custom_rules: Optional mapping of category names to desired percentage allocations (0–1 range).

    Returns:
        A dict mapping categories to budget amounts.
    """
    # Default 50/30/20 rule for needs, wants, and savings
    default_rules = {
        "needs": 0.50,
        "wants": 0.30,
        "savings": 0.20,
    }
    rules = custom_rules if custom_rules else default_rules

    budget = {}
    for cat, pct in rules.items():
        budget[cat] = round(total_income * pct, 2)

    # Distribute any unassigned categories proportionally into needs
    known_cats = set(rules.keys())
    for cat, amt in expenses_by_category.items():
        if cat not in known_cats:
            budget.setdefault("other", 0)
            budget["other"] += amt

    return budget
