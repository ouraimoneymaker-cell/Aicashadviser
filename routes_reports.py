"""Report generation endpoints.

This module exposes endpoints to generate financial analysis reports for a
case. It uses services that compute analytics, budgets and debt payoff
plans. Initially it returns a simple summary; full PDF generation is
planned for future iterations.
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from ..db import models, session
from ..services import analytics, plans_budget, plans_debt

router = APIRouter()


@router.get("/{case_id}")
async def get_report(case_id: int) -> JSONResponse:
    """Generate a basic JSON report for a case.

    This early implementation counts the number of uploaded files and
    transactions associated with the case and returns totals. Later
    versions will produce detailed PDFs and CSVs using ReportLab.
    """
    db = session.get_db()
    case = db.query(models.Case).filter(models.Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    # Count files and transactions.
    file_count = db.query(models.FileUpload).filter(models.FileUpload.case_id == case_id).count()
    txn_count = db.query(models.Transaction).filter(models.Transaction.case_id == case_id).count()

    return JSONResponse(
        {
            "case_id": case.id,
            "case_name": case.name,
            "files": file_count,
            "transactions": txn_count,
        }
    )