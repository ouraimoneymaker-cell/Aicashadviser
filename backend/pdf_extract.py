"""PDF extraction service.

This module provides a stub function for extracting transaction data from
PDF statements. In a real implementation this would use a library such
as PyMuPDF or pdfplumber to extract text and then parse structured data.
"""

from typing import List, Dict


def extract_transactions_from_pdf(file_path: str) -> List[Dict]:
    """Extract transactions from a PDF file (stub).

    Args:
        file_path: Path to the PDF file.

    Returns:
        List of transaction dictionaries. This stub returns an empty list.
    """
    # TODO: Implement PDF extraction using PyMuPDF or pdfplumber
    return []