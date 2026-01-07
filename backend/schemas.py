"""Pydantic schemas for API inputs and outputs.

These models define the shapes of requests and responses for FastAPI. They
correspond closely to the SQLAlchemy models but omit database‑specific
constructs. Each schema sets `orm_mode=True` so that it can be constructed
directly from ORM objects.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


class CaseBase(BaseModel):
    """Shared properties for a Case."""
    name: str


class CaseCreate(CaseBase):
    """Properties to receive via API on case creation."""
    pass


class Case(CaseBase):
    """Properties to return via API for a case."""
    id: int
    created_at: datetime

    class Config:
        orm_mode = True


class FileUpload(BaseModel):
    """Schema representing an uploaded file."""
    id: int
    case_id: int
    filename: str
    path: str
    content_type: Optional[str] = None
    uploaded_at: datetime

    class Config:
        orm_mode = True


class Transaction(BaseModel):
    """Schema representing a transaction."""
    id: int
    case_id: int
    date: datetime
    merchant: Optional[str] = None
    amount: Decimal
    category: Optional[str] = None
    description: Optional[str] = None
    account: Optional[str] = None

    class Config:
        orm_mode = True


class Debt(BaseModel):
    """Schema representing a debt account."""
    id: int
    case_id: int
    name: str
    balance: Decimal
    apr: float
    min_payment: Decimal

    class Config:
        orm_mode = True