"""Analytics services for financial cases.

This module contains functions that operate on lists of transactions to
compute insights such as total income, total expenses, net cash flow,
category breakdowns and recurring transaction detection. These functions
could be extended with more sophisticated ML models but start simple.
"""

from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from typing import Iterable, Dict, List, Tuple

from ..db import models
from ..utils.money import quantize_cents


def summarize_transactions(transactions: Iterable[models.Transaction]) -> Dict:
    """Return basic summary statistics for a list of transactions.

    Args:
        transactions: An iterable of `Transaction` ORM objects.

    Returns:
        Dictionary containing total income, total expenses, net, and
        category totals.
    """
    total_income = Decimal("0.00")
    total_expense = Decimal("0.00")
    category_totals: Dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))

    for txn in transactions:
        amount = txn.amount
        # Determine whether amount is income or expense. Negative amounts mean
        # expenses; positive amounts are income. Adjust as needed.
        if amount > 0:
            total_income += amount
        else:
            total_expense += abs(amount)
        # Sum by category
        cat = txn.category or "Uncategorized"
        category_totals[cat] += abs(amount)

    return {
        "total_income": str(quantize_cents(total_income)),
        "total_expense": str(quantize_cents(total_expense)),
        "net_cash_flow": str(quantize_cents(total_income - total_expense)),
        "category_totals": {k: str(quantize_cents(v)) for k, v in category_totals.items()},
    }


def detect_recurring(transactions: Iterable[models.Transaction]) -> List[Tuple[str, Decimal]]:
    """Identify potential recurring transactions.

    This naive implementation groups transactions by merchant and
    approximately monthly cadence. More advanced logic would use time
    series clustering.

    Args:
        transactions: Iterable of `Transaction` ORM objects.

    Returns:
        List of tuples (merchant, average_amount) representing recurring
        charges.
    """
    # Group transactions by merchant.
    groups: Dict[str, List[models.Transaction]] = defaultdict(list)
    for txn in transactions:
        if txn.merchant:
            groups[txn.merchant].append(txn)

    recurring = []
    for merchant, txns in groups.items():
        # Look for at least 2 transactions at roughly monthly intervals
        if len(txns) < 2:
            continue
        # Sort by date
        txns.sort(key=lambda t: t.date)
        intervals = []
        for i in range(1, len(txns)):
            delta = (txns[i].date - txns[i - 1].date).days
            intervals.append(delta)
        # Check if median interval is between 27 and 33 days
        if intervals:
            intervals.sort()
            median = intervals[len(intervals) // 2]
            if 27 <= median <= 33:
                avg_amount = sum(abs(t.amount) for t in txns) / len(txns)
                recurring.append((merchant, quantize_cents(avg_amount)))
    return recurring