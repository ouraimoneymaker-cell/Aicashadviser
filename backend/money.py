"""Utilities for precise monetary calculations.

This module provides helper functions for working with money amounts
represented as `Decimal`. In finance applications it is important to avoid
floating‑point arithmetic because it introduces rounding errors. The
functions here convert arbitrary inputs into `Decimal` and quantize to
cents.
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import Union


def to_decimal(amount: Union[str, int, float, Decimal]) -> Decimal:
    """Convert arbitrary numeric input to a `Decimal`.

    Args:
        amount: A number, string or Decimal representing a currency amount.

    Returns:
        Decimal: The equivalent decimal value.
    """
    if isinstance(amount, Decimal):
        return amount
    return Decimal(str(amount))


def quantize_cents(value: Decimal) -> Decimal:
    """Quantize a `Decimal` value to two decimal places (cents).

    Args:
        value: Decimal value.

    Returns:
        Decimal: Value rounded to two decimal places using half‑up rounding.
    """
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def add(a: Union[str, int, float, Decimal], b: Union[str, int, float, Decimal]) -> Decimal:
    """Add two monetary amounts and return the result quantized to cents."""
    return quantize_cents(to_decimal(a) + to_decimal(b))