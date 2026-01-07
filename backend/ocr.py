"""OCR fallback service.

This module defines a function to perform OCR on scanned documents. It
serves as a fallback when PDF text extraction fails. Using pytesseract
requires that Tesseract is installed in the environment, which may not be
the case in this minimal example.
"""

from typing import List, Dict


def ocr_extract(file_path: str) -> List[str]:
    """Perform OCR on a file and return extracted text lines.

    This stub implementation returns an empty list. In a real setup you
    would load the image or PDF page and run pytesseract.image_to_string.
    """
    # TODO: Implement OCR using pytesseract
    return []