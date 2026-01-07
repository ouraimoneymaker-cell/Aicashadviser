"""
PDF report generation for AICashAdvisor using ReportLab.

This module contains functions to build professional PDF reports
summarizing the user’s financial analysis. The reports include tables
of income/expense data, charts (via reportlab.platypus), and narrative
explanations. If ReportLab is not available, the functions gracefully
fallback to generating a simple text report.
"""

from typing import Dict, Any, List, Optional

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib import colors
    REPORTLAB_AVAILABLE = True
except ImportError:
    # ReportLab is optional; if unavailable, we'll generate a plain text report.
    REPORTLAB_AVAILABLE = False


def generate_pdf_report(
    file_path: str,
    summary: Dict[str, Any],
    narrative: str,
    tables: Optional[List[List[List[Any]]]] = None,
) -> None:
    """Generate a financial report as a PDF (or text fallback).

    Args:
        file_path: Destination path for the PDF file.
        summary: Dictionary of summary metrics (income, expenses, net, etc.).
        narrative: Narrative explanation or commentary on the analysis.
        tables: Optional list of tables, where each table is a list of row lists.
    """
    if REPORTLAB_AVAILABLE:
        # Build a PDF using ReportLab.
        doc = SimpleDocTemplate(file_path, pagesize=letter)
        styles = getSampleStyleSheet()
        story: List[Any] = []

        # Title
        story.append(Paragraph("AICashAdvisor Financial Report", styles["Title"]))
        story.append(Spacer(1, 12))

        # Summary section
        story.append(Paragraph("Summary", styles["Heading2"]))
        for key, val in summary.items():
            story.append(Paragraph(f"<b>{key.capitalize()}</b>: {val}", styles["Normal"]))
        story.append(Spacer(1, 12))

        # Narrative section
        story.append(Paragraph("Narrative", styles["Heading2"]))
        story.append(Paragraph(narrative, styles["Normal"]))
        story.append(Spacer(1, 12))

        # Tables section
        if tables:
            story.append(Paragraph("Detailed Tables", styles["Heading2"]))
            for table_data in tables:
                tbl = Table(table_data)
                tbl.setStyle(
                    TableStyle(
                        [
                            ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                            ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                        ]
                    )
                )
                story.append(tbl)
                story.append(Spacer(1, 12))

        # Generate the PDF file
        doc.build(story)
    else:
        # Fallback: Create a simple text report.
        txt_path = file_path.replace(".pdf", ".txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write("AICashAdvisor Financial Report\n")
            f.write("Summary\n")
            for key, val in summary.items():
                f.write(f"{key.capitalize()}: {val}\n")
            f.write("\nNarrative\n")
            f.write(narrative + "\n")
            if tables:
                f.write("\nDetailed Tables\n")
                for table in tables:
                    for row in table:
                        f.write("\t".join(str(cell) for cell in row) + "\n")
                    f.write("\n")