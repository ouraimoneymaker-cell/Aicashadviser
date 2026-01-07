"""Entry point for the AICashAdvisor FastAPI application.

This module creates a FastAPI application instance and wires up the
various routers that implement the public API. It is intentionally
light‑weight so deployment scripts can import ``app`` without side
effects.

The file is placed under the ``backend`` package to ensure relative
imports work correctly when deployed. The corresponding root-level
``main.py`` should be removed from your repository to avoid confusion.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes_cases import router as cases_router
from .api.routes_uploads import router as uploads_router
from .api.routes_reports import router as reports_router
from .db import models, session

# Create FastAPI app with metadata
app = FastAPI(
    title="AICashAdvisor API",
    version="0.1.0",
    description=(
        "API for managing financial cases, uploading data and generating reports."
    ),
)

# Allow CORS from any origin for development. In production tighten this.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers with prefixes and tags for organisation.
app.include_router(cases_router, prefix="/api/cases", tags=["cases"])
app.include_router(uploads_router, prefix="/api/uploads", tags=["uploads"])
app.include_router(reports_router, prefix="/api/reports", tags=["reports"])

# Initialize database tables at startup. In production this should be done via
# migrations (e.g., Alembic) but for the MVP we create tables programmatically.
models.init_db(session.engine)


@app.get("/health", summary="Health check", response_model=dict)
async def health_check() -> dict:
    """Simple health check endpoint to verify the service is running."""
    return {"status": "ok"}
