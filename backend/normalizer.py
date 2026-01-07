
"""
Transaction normalization utilities for AICashAdvisor.

This module provides functions to transform raw transaction records from
various sources (CSV, PDF extractions, API payloads) into a unified
representation. Normalizing data is essential so analytics, budgeting,
and reporting logic can operate on a consistent schema.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Optional, List

def _parse_date(date_str: str) -> datetime:
    """Attempt to parse a date string into a datetime object.

    This helper tries multiple date formats to handle common variations
    found in bank statements (e.g., "2025-03-14", "03/14/2025", etc.).

    Args:
        date_str: The raw date string.

    Returns:
        A datetime instance.

    Raises:
        ValueError if none of the formats match.
    """
    formats = ["%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    raise ValueError(f"Unable to parse date: {date_str}")

def _to_decimal(amount: Any) -> Decimal:
    """Convert a numeric or string amount to a Decimal for accuracy."""
    return Decimal(str(amount))

def normalize_transaction(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a single raw transaction record.

    The returned dict uses the following keys:
    - ``date`` (datetime): The date of the transaction.
    - ``merchant`` (str): Merchant or payee name.
    - ``amount`` (Decimal): Signed transaction amount; income > 0, expenses < 0.
    - ``currency`` (str): Currency code (e.g., "USD").
    - ``category`` (Optional[str]): Optional category if already known.
    - ``description`` (str): Original description or memo field.
    - ``account`` (Optional[str]): Account identifier.

    Missing fields are handled gracefully; unknown values default to sensible
    placeholders such as "uncategorized" or ``None``.

    Args:
        raw: A mapping containing the raw transaction fields.

    Returns:
        A normalized transaction dictionary.
    """
    # Extract and parse the date.
    date_raw = raw.get("date") or raw.get("timestamp") or raw.get("datetime")
    date_parsed = _parse_date(date_raw) if date_raw else None

    # Determine merchant name. Fallback to description if merchant missing.
    merchant = raw.get("merchant") or raw.get("payee")
    if not merchant:
        desc = raw.get("description", "").strip()
        merchant = desc.split()[0] if desc else "Unknown"

    # Determine amount and sign. Some statements present credits as positive.
    raw_amount = raw.get("amount")
    amount = _to_decimal(raw_amount) if raw_amount is not None else Decimal("0")

    # Currency default to USD unless specified otherwise.
    currency = raw.get("currency", "USD").upper()

    # Optional category if provided by upstream categorizer.
    category: Optional[str] = raw.get("category")

    description = raw.get("description", "")

    account: Optional[str] = raw.get("account")

    return {
        "date": date_parsed,
        "merchant": merchant,
        "amount": amount,
        "currency": currency,
        "category": category,
        "description": description,
        "account": account,
    }

def normalize_transactions(raw_transactions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Normalize a list of raw transaction records."""
    return [normalize_transaction(rt) for rt in raw_transactions]
