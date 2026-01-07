"""Debt payoff plan generator.

This service provides a deterministic payoff simulation for a list of debt
accounts. It supports two strategies: the avalanche method (pay highest APR
first) and the snowball method (pay lowest balance first). The output
includes a schedule of monthly balances for each debt until paid off.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import List, Dict

from ..utils.money import to_decimal, quantize_cents


@dataclass
class Debt:
    name: str
    balance: Decimal
    apr: Decimal  # Annual percentage rate (e.g., 0.2499 for 24.99%)
    min_payment: Decimal


def _monthly_rate(apr: Decimal) -> Decimal:
    """Convert an annual percentage rate into a monthly rate."""
    return apr / Decimal("12")


def payoff_plan(
    debts: List[Debt],
    extra_payment: Decimal = Decimal("0.00"),
    method: str = "avalanche",
) -> Dict:
    """Compute a deterministic payoff schedule.

    Args:
        debts: List of `Debt` objects.
        extra_payment: Extra amount to apply each month beyond minimums.
        method: "avalanche" (highest APR first) or "snowball" (lowest balance first).

    Returns:
        Dictionary containing payoff method, total months and monthly schedule.
    """
    # Deep copy and quantize initial values to avoid modifying inputs.
    debts = [
        Debt(
            d.name,
            quantize_cents(to_decimal(d.balance)),
            to_decimal(d.apr),
            quantize_cents(to_decimal(d.min_payment)),
        )
        for d in debts
    ]
    extra_payment = quantize_cents(to_decimal(extra_payment))

    def sort_key(d: Debt):
        return (-d.apr, d.balance) if method == "avalanche" else (d.balance, -d.apr)

    month = 0
    schedule = []
    max_months = 600  # Prevent infinite loops

    while month < max_months and any(d.balance > 0 for d in debts):
        month += 1
        debts.sort(key=sort_key)

        # Apply monthly interest
        for d in debts:
            if d.balance <= 0:
                continue
            interest = quantize_cents(d.balance * _monthly_rate(d.apr))
            d.balance = quantize_cents(d.balance + interest)

        # Pay minimums
        for d in debts:
            if d.balance <= 0:
                continue
            payment = min(d.min_payment, d.balance)
            d.balance = quantize_cents(d.balance - payment)

        # Apply extra payment to highest priority debt
        remaining_extra = extra_payment
        for d in debts:
            if remaining_extra <= 0:
                break
            if d.balance <= 0:
                continue
            pay = min(remaining_extra, d.balance)
            d.balance = quantize_cents(d.balance - pay)
            remaining_extra = quantize_cents(remaining_extra - pay)

        schedule.append({
            "month": month,
            "debts": [
                {"name": d.name, "balance": str(d.balance)} for d in debts
            ],
        })

    return {
        "method": method,
        "months": month,
        "schedule": schedule,
        "done": all(d.balance <= 0 for d in debts),
    }