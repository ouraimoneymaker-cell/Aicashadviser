"""
CSV ingestion module for AICashAdvisor.

This module provides basic functions to ingest CSV files containing
transaction data and return raw transaction dictionaries. It uses
Python's built-in csv module to parse comma-separated values.

Users can extend or customize the header mapping to suit their
specific bank or statement formats.
"""

import csv
from typing import List, Dict, Any, Optional


def ingest_csv(file_path: str, column_map: Optional[Dict[str, str]] = None) -> List[Dict[str, Any]]:
    """Read a CSV file and return a list of transaction dictionaries.

    Args:
        file_path: Path to the CSV file.
        column_map: Optional mapping from CSV column names to normalized
            field names (e.g., {"Transaction Date": "date", "Description": "description"}).

    Returns:
        A list of dictionaries representing raw transactions. If ``column_map``
        is provided, keys in the returned dicts will be normalized accordingly.
    """
    transactions: List[Dict[str, Any]] = []
    with open(file_path, newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            if column_map:
                normalized = {column_map.get(k, k): v for k, v in row.items()}
                transactions.append(normalized)
            else:
                transactions.append(dict(row))
    return transactions
