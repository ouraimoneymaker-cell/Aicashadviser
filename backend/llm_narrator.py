"""
Natural language narrative generation for AICashAdvisor.

This module wraps an LLM (if available) to produce coherent narrative
explanations of financial analysis. Numbers and calculations
are supplied externally and must not be invented by the model.
"""

import os
from typing import Dict, Any

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    # If the OpenAI SDK isn't available, fall back to a simple narrative.
    OPENAI_AVAILABLE = False


def generate_narrative(report_summary: Dict[str, Any]) -> str:
    """Generate a narrative explanation of the report summary.

    Args:
        report_summary: A dictionary containing summary statistics and key points.

    Returns:
        A human‑readable narrative string explaining the user's cash flow and spending patterns.
    """
    # Compose a basic narrative if no LLM or API key is available.
    if not OPENAI_AVAILABLE or not os.getenv("OPENAI_API_KEY"):
        return (
            "This report summarizes your financial position. "
            "Income, expenses, and key trends are described in the attached tables."
        )

    # Build prompt from summary
    prompt = (
        "You are a financial analyst assistant. Based on the following summary, "
        "write a concise narrative explaining the user's cash flow, spending patterns, "
        "and any notable insights. Do not make up numbers; reference only the provided summary.\n"
    )
    for key, val in report_summary.items():
        prompt += f"{key}: {val}\n"

    # Call OpenAI chat completion API
    completion = openai.chat.completions.create(
        model="gpt-4-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful financial analyst."},
            {"role": "user", "content": prompt},
        ],
    )

    narrative = completion.choices[0].message.content.strip()
    return narrative