"""
main.py — ClearConsent FastAPI application.

Entry point for the backend.  Run with:
    uvicorn app.main:app --reload --port 8000
"""

from __future__ import annotations

import logging
import os
import time

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.models.schemas import HealthResponse
from app.routes import analyze, history, session

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

load_dotenv()  # Load .env from the backend/ directory

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("clearconsent")

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="ClearConsent API",
    description=(
        "AI-powered consent & document analysis platform. "
        "Upload legal, medical, rental, employment, or ToS documents "
        "and get plain-English risk analysis powered by a custom DistilBERT model."
    ),
    version="1.0.0",
)

# ---------------------------------------------------------------------------
# CORS — allow the local frontend to call the API
# ---------------------------------------------------------------------------

# CORS_ORIGINS env var: comma-separated list of extra allowed origins (e.g. ngrok URL).
# Falls back to wildcard when not set — safe for local hackathon use.
_extra_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()]
_allow_origins = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:5500",
    "http://localhost:8080",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5500",
    "http://127.0.0.1:8080",
    *_extra_origins,
] or ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins if _extra_origins else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Request logging middleware
# ---------------------------------------------------------------------------


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed = (time.perf_counter() - start) * 1000
    logger.info(
        "%s %s → %s (%.0f ms)",
        request.method,
        request.url.path,
        response.status_code,
        elapsed,
    )
    return response


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

app.include_router(session.router, prefix="/api")
app.include_router(analyze.router, prefix="/api")
app.include_router(history.router, prefix="/api")


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """Health check endpoint — reports status and integration availability."""
    from app.services.model_service import is_model_loaded, _load_model, get_model_source

    # Attempt to load the model if it hasn't been loaded yet
    _load_model()

    return HealthResponse(
        status="healthy",
        version="1.0.0",
        model_loaded=is_model_loaded(),
        model_source=get_model_source(),
        integrations={
            "google_vision": bool(
                os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
                or os.getenv("GOOGLE_CLOUD_VISION_KEY")
            ),
            "gemma": bool(os.getenv("GEMINI_API_KEY")),
            "backboard": bool(os.getenv("BACKBOARD_API_KEY")),
            "dcp": bool(os.getenv("DCP_API_KEY")),
        },
    )


# ---------------------------------------------------------------------------
# Startup event
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def startup_event():
    logger.info("=" * 60)
    logger.info("  ClearConsent API starting up")
    logger.info("=" * 60)

    # Pre-load the model in the background (non-blocking)
    from app.services.model_service import _load_model

    try:
        _load_model()
    except Exception as exc:
        logger.warning("Model pre-load skipped: %s", exc)

    logger.info("Ready to accept requests.")
