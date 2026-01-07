"""File upload endpoints.

These endpoints allow users to upload CSV or PDF files associated with a
financial case. Uploaded files are saved to disk and a record is stored in
the database. Future iterations should include security checks and scanning
for malicious content.
"""

import os
from typing import List

from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse

from ..db import models, schemas, session

router = APIRouter()

UPLOAD_ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "uploads")
os.makedirs(UPLOAD_ROOT, exist_ok=True)


@router.post("/{case_id}", response_model=schemas.FileUpload)
async def upload_file(case_id: int, file: UploadFile = File(...)) -> schemas.FileUpload:
    """Upload a single CSV or PDF file to a case.

    The file is saved under `UPLOAD_ROOT/<case_id>/` and a FileUpload entry is
    persisted. If the case does not exist, an HTTP 404 error is returned.
    """
    db = session.get_db()
    case = db.query(models.Case).filter(models.Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    # Ensure case-specific directory exists.
    case_dir = os.path.join(UPLOAD_ROOT, str(case_id))
    os.makedirs(case_dir, exist_ok=True)

    # Save the uploaded file to disk.
    file_location = os.path.join(case_dir, file.filename)
    with open(file_location, "wb") as f:
        content = await file.read()
        f.write(content)

    # Create database record.
    new_upload = models.FileUpload(
        case_id=case_id,
        filename=file.filename,
        path=file_location,
        content_type=file.content_type,
    )
    db.add(new_upload)
    db.commit()
    db.refresh(new_upload)

    return schemas.FileUpload.from_orm(new_upload)


@router.get("/{case_id}", response_model=List[schemas.FileUpload])
async def list_files(case_id: int) -> List[schemas.FileUpload]:
    """List all uploaded files for a given case."""
    db = session.get_db()
    uploads = db.query(models.FileUpload).filter(models.FileUpload.case_id == case_id).all()
    return [schemas.FileUpload.from_orm(u) for u in uploads]