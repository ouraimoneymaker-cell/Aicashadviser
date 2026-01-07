
"""
Debt payoff planning for AICashAdvisor.

This module implements deterministic debt payoff simulations. Users can
choose between avalanche (highest APR first) or snowball (lowest balance
first) methods. Results include a month-by-month schedule showing
remaining balances.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import List, Dict


@dataclass
class Debt:
    name: str
    balance: Decimal
    apr: Decimal  # Annual percentage rate as a decimal (e.g. 0.2499 for 24.99%)
    min_payment: Decimal


def _monthly_rate(apr: Decimal) -> Decimal:
    return apr / Decimal("12")


def payoff_plan(debts: List[Debt], extra_payment: Decimal, method: str = "avalanche") -> Dict:
    """Simulate a payoff schedule for multiple debts.

    Args:
        debts: List of Debt objects to pay off.
        extra_payment: Amount to pay in addition to minimum payments.
        method: "avalanche" for highest APR first, or "snowball" for lowest balance first.

    Returns:
        A dict with the payment schedule and metadata.
    """
    # Copy debts to avoid modifying inputs
    debts = [Debt(d.name, Decimal(d.balance), Decimal(d.apr), Decimal(d.min_payment)) for d in debts]
    schedule = []
    month = 0
    max_months = 600

    def key_fn(d: Debt):
        return (-d.apr, d.balance) if method == "avalanche" else (d.balance, -d.apr)

    while month < max_months and any(d.balance > 0 for d in debts):
        month += 1
        debts.sort(key=key_fn)

        # Apply monthly interest
        for d in debts:
            if d.balance > 0:
                interest = (d.balance * _monthly_rate(d.apr)).quantize(Decimal("0.01"))
                d.balance += interest

        # Make minimum payments
        for d in debts:
            if d.balance <= 0:
                continue
            payment = min(d.min_payment, d.balance)
            d.balance -= payment

        # Apply extra payment to prioritized debts
        remaining_extra = extra_payment
        for d in debts:
            if remaining_extra <= 0:
                break
            if d.balance <= 0:
                continue
            payment = min(remaining_extra, d.balance)
            d.balance -= payment
            remaining_extra -= payment

        # Record this month
        schedule.append({
            "month": month,
            "debts": [{"name": d.name, "balance": float(d.balance)} for d in debts],
        })

    return {
        "method": method,
        "months": month,
        "schedule": schedule,
        "done": all(d.balance <= 0 for d in debts),
    }
