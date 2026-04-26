"""
analyze.py — Routes for document analysis.

POST /api/analyze       — Full pipeline (Vision → classifier → Gemma → Backboard)
POST /api/analyze/mock  — Instant polished demo response
POST /api/analyze/dcp   — DCP parallel-processing demo
"""

from __future__ import annotations

import logging
import random
import time
from typing import Optional

from fastapi import APIRouter, File, UploadFile, Form, HTTPException

from app.models.schemas import (
    AnalysisResponse,
    DCPAnalysisResponse,
    FlaggedClause,
    ProcessingMetadata,
    DCPMetrics,
)
from app.services import (
    backboard_service,
    dcp_service,
    gemma_service,
    model_service,
    vision_service,
)
from app.services.mock_data import MOCK_ANALYSIS, MOCK_DCP_ANALYSIS

logger = logging.getLogger("clearconsent.analyze")
router = APIRouter(prefix="/analyze", tags=["Analysis"])

ALLOWED_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/heic",
    "image/heif",
}

ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".heic", ".heif"}


def _validate_file(file: UploadFile) -> None:
    """Basic file validation."""
    if file.content_type and file.content_type not in ALLOWED_TYPES:
        ext = "." + file.filename.rsplit(".", 1)[-1].lower() if file.filename else ""
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {file.content_type}. "
                       f"Accepted: PDF, PNG, JPG, JPEG, HEIC.",
            )


def _make_doc_id() -> str:
    return f"doc_{random.randint(10000, 99999)}"


# ---------------------------------------------------------------------------
# POST /api/analyze — Full pipeline (reads actual uploaded file)
# ---------------------------------------------------------------------------

@router.post("", response_model=AnalysisResponse)
async def analyze_document(
    file: UploadFile = File(...),
    user_id: Optional[str] = Form(default="demo_user"),
):
    """
    Analyze an uploaded document through the full ClearConsent pipeline.
    This endpoint reads the ACTUAL file — it does NOT return mock data.
    """
    start = time.perf_counter()

    _validate_file(file)

    # --- Logging: uploaded file info ---
    logger.info("=" * 60)
    logger.info("ANALYZE REQUEST")
    logger.info("  filename:     %s", file.filename)
    logger.info("  content_type: %s", file.content_type)
    logger.info("  endpoint:     /api/analyze (real)")

    # --- Step 1: Extract text from the actual uploaded file ---
    raw_text, used_vision, ocr_mode = await vision_service.extract_text_from_upload(file)

    logger.info("  ocr_mode:     %s", ocr_mode)
    logger.info("  used_vision:  %s", used_vision)
    logger.info("  text_length:  %d chars", len(raw_text))
    logger.info("  text_preview: %s", raw_text[:300].replace("\n", " "))

    if not raw_text.strip():
        raise HTTPException(status_code=422, detail="Could not extract text from the uploaded file.")

    # --- Step 2: Split into clauses ---
    clauses = model_service.split_into_clauses(raw_text)
    logger.info("  clauses_found: %d", len(clauses))

    if not clauses:
        raise HTTPException(status_code=422, detail="No analysable clauses found in the document.")

    # --- Step 3: Hybrid classification ---
    flagged_raw = model_service.hybrid_predict(clauses, top_n=5)
    used_distilbert = model_service.is_model_loaded()
    model_source = model_service.get_model_source()

    logger.info("  model_source:  %s", model_source)
    logger.info("  used_distilbert: %s", used_distilbert)
    logger.info("  flagged_clauses: %d", len(flagged_raw))

    # --- Step 4: Risk score ---
    risk_numeric, risk_label = model_service.compute_risk_score(flagged_raw)
    logger.info("  risk_score:    %d (%s)", risk_numeric, risk_label)

    # --- Step 5: Plain-English explanations ---
    flagged_explained, used_gemma = await gemma_service.explain_clauses(flagged_raw)

    # --- Step 6: Summary ---
    summary, _ = await gemma_service.generate_summary(
        flagged_explained, risk_numeric, risk_label
    )

    # --- Step 7: Build response ---
    doc_id = _make_doc_id()
    elapsed_ms = int((time.perf_counter() - start) * 1000)

    logger.info("  used_gemma:    %s", used_gemma)
    logger.info("  processing_ms: %d", elapsed_ms)
    logger.info("=" * 60)

    flagged_clauses = [
        FlaggedClause(
            type=c["type"],
            original_text=c["original_text"],
            translation=c.get("translation", ""),
            severity=c["severity"],
            confidence=c["confidence"],
            source=c["source"],
        )
        for c in flagged_explained
    ]

    response = AnalysisResponse(
        document_id=doc_id,
        overall_risk_score=risk_label,
        risk_score_numeric=risk_numeric,
        summary_plain_english=summary,
        flagged_clauses=flagged_clauses,
        processing_metadata=ProcessingMetadata(
            used_google_vision=used_vision,
            used_distilbert=used_distilbert,
            used_gemma=used_gemma,
            used_backboard=False,
            used_dcp=False,
            processing_time_ms=elapsed_ms,
            ocr_mode=ocr_mode,
            model_source=model_source,
            endpoint_mode="real_analyze",
            extracted_text_preview=raw_text[:300],
        ),
    )

    # --- Step 8: Save to vault ---
    analysis_dict = response.model_dump()
    analysis_dict["filename"] = file.filename or "Uploaded Document"
    _, used_backboard = await backboard_service.save_document_analysis(
        user_id or "demo_user", analysis_dict
    )
    response.processing_metadata.used_backboard = used_backboard

    return response


# ---------------------------------------------------------------------------
# POST /api/analyze/mock — Instant demo (hardcoded, clearly labeled)
# ---------------------------------------------------------------------------

@router.post("/mock", response_model=AnalysisResponse)
async def analyze_mock():
    """
    Return a polished demo response instantly.
    Critical fallback for hackathon demos when external APIs are down.
    This is explicitly NOT real analysis — metadata marks it as mock.
    """
    return MOCK_ANALYSIS


# ---------------------------------------------------------------------------
# POST /api/analyze/dcp — DCP parallel demo
# ---------------------------------------------------------------------------

@router.post("/dcp", response_model=DCPAnalysisResponse)
async def analyze_dcp(
    file: Optional[UploadFile] = File(default=None),
    user_id: Optional[str] = Form(default="demo_user"),
):
    """
    Analyze a document using DCP parallel page processing.
    If no file is uploaded, returns a polished demo with DCP metrics.
    """
    start = time.perf_counter()

    if file is None:
        return MOCK_DCP_ANALYSIS

    _validate_file(file)

    # --- OCR ---
    raw_text, used_vision, ocr_mode = await vision_service.extract_text_from_upload(file)
    clauses = model_service.split_into_clauses(raw_text)

    if not clauses:
        raise HTTPException(status_code=422, detail="No analysable clauses found.")

    # --- Simulate pages ---
    page_size = max(1, len(clauses) // 4)
    pages = [
        " ".join(clauses[i : i + page_size])
        for i in range(0, len(clauses), page_size)
    ]
    if not pages:
        pages = [raw_text]

    # --- DCP processing ---
    dcp_metrics, used_dcp = await dcp_service.process_pages_parallel(pages)

    # --- Classification ---
    flagged_raw = model_service.hybrid_predict(clauses, top_n=5)
    used_distilbert = model_service.is_model_loaded()
    model_source = model_service.get_model_source()

    risk_numeric, risk_label = model_service.compute_risk_score(flagged_raw)
    flagged_explained, used_gemma = await gemma_service.explain_clauses(flagged_raw)
    summary, _ = await gemma_service.generate_summary(
        flagged_explained, risk_numeric, risk_label
    )

    elapsed_ms = int((time.perf_counter() - start) * 1000)

    flagged_clauses = [
        FlaggedClause(
            type=c["type"],
            original_text=c["original_text"],
            translation=c.get("translation", ""),
            severity=c["severity"],
            confidence=c["confidence"],
            source=c["source"],
        )
        for c in flagged_explained
    ]

    return DCPAnalysisResponse(
        document_id=_make_doc_id(),
        overall_risk_score=risk_label,
        risk_score_numeric=risk_numeric,
        summary_plain_english=summary,
        flagged_clauses=flagged_clauses,
        dcp_metrics=DCPMetrics(**dcp_metrics),
        processing_metadata=ProcessingMetadata(
            used_google_vision=used_vision,
            used_distilbert=used_distilbert,
            used_gemma=used_gemma,
            used_backboard=False,
            used_dcp=used_dcp,
            processing_time_ms=elapsed_ms,
            ocr_mode=ocr_mode,
            model_source=model_source,
            endpoint_mode="real_analyze",
            extracted_text_preview=raw_text[:300],
        ),
    )
