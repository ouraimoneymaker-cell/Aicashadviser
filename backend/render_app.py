"""Render deployment entry point.

This minimal ASGI app is used by ``render.yaml`` so Render can reliably boot
and health-check the service from this repository.
"""

from fastapi import FastAPI

app = FastAPI(title="AICashAdvisor API", version="0.1.0")


@app.get("/health", summary="Health check")
async def health_check() -> dict[str, str]:
    """Simple health check endpoint used by Render."""
    return {"status": "ok"}
