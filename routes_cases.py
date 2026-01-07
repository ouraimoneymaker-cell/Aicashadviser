"""Case management endpoints.

This module defines REST endpoints for creating and listing financial cases.
Each case represents a discrete financial analysis session for a user. In the
future this module can enforce authentication and 2FA for sensitive actions.
"""

from typing import List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..db import models, schemas, session

router = APIRouter()


@router.post("/", response_model=schemas.Case)
async def create_case(case_in: schemas.CaseCreate) -> schemas.Case:
    """Create a new financial analysis case.

    For now this function persists to an in‑memory list. In a future
    iteration it should create a database record.
    """
    db = session.get_db()
    new_case = models.Case(name=case_in.name)
    db.add(new_case)
    db.commit()
    db.refresh(new_case)
    return schemas.Case.from_orm(new_case)


@router.get("/", response_model=List[schemas.Case])
async def list_cases() -> List[schemas.Case]:
    """Return all existing cases.

    This endpoint is intentionally simple. Pagination and filtering can be added
    when the number of cases becomes large.
    """
    db = session.get_db()
    cases = db.query(models.Case).all()
    return [schemas.Case.from_orm(c) for c in cases]