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
        # Also check by extension as a fallback
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
# POST /api/analyze — Full pipeline
# ---------------------------------------------------------------------------

@router.post("", response_model=AnalysisResponse)
async def analyze_document(
    file: UploadFile = File(...),
    user_id: Optional[str] = Form(default="demo_user"),
):
    """
    Analyze an uploaded document through the full ClearConsent pipeline:
    1. OCR via Google Vision (or mock fallback)
    2. Clause splitting
    3. Hybrid classification (rules + DistilBERT)
    4. Risk score computation
    5. Plain-English explanations via Gemma (or fallback)
    6. Save to Backboard consent vault (or mock)
    """
    start = time.perf_counter()

    _validate_file(file)

    # --- Step 1: Extract text ---
    raw_text, used_vision, ocr_mode = await vision_service.extract_text_from_upload(file)

    if not raw_text.strip():
        raise HTTPException(status_code=422, detail="Could not extract text from the uploaded file.")

    # --- Step 2: Split into clauses ---
    clauses = model_service.split_into_clauses(raw_text)

    if not clauses:
        raise HTTPException(status_code=422, detail="No analysable clauses found in the document.")

    # --- Step 3: Hybrid classification ---
    flagged_raw = model_service.hybrid_predict(clauses, top_n=5)
    used_distilbert = model_service.is_model_loaded()

    # --- Step 4: Risk score ---
    risk_numeric, risk_label = model_service.compute_risk_score(flagged_raw)

    # --- Step 5: Plain-English explanations & Summary via Gemma ---
    summary, flagged_explained, used_gemma = await gemma_service.improve_analysis_with_gemma(
        flagged_raw, risk_numeric, risk_label
    )

    # --- Step 7: Build response ---
    doc_id = _make_doc_id()
    elapsed_ms = int((time.perf_counter() - start) * 1000)
    
    # Generate a preview of the text
    preview = raw_text.replace('\n', ' ')
    if len(preview) > 250:
        preview = preview[:250] + "..."

    flagged_clauses = [
        FlaggedClause(
            type=c["type"],
            original_text=c["original_text"],
            translation=c.get("translation", ""),
            severity=c["severity"],
            confidence=c["confidence"],
            source=c["source"],
            why_it_matters=c.get("why_it_matters"),
            suggested_action=c.get("suggested_action"),
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
            used_backboard=False,  # Updated below
            used_dcp=False,
            dcp_mode="off",
            processing_time_ms=elapsed_ms,
            ocr_mode=ocr_mode,
            model_source=model_service.get_model_source(),
            endpoint_mode="real_analyze",
            extracted_text_preview=preview,
        ),
    )

    # --- Step 8: Save to vault ---
    analysis_dict = response.model_dump()
    analysis_dict["filename"] = file.filename or "Uploaded Document"
    
    _, used_backboard = await backboard_service.save_document_analysis(
        user_id or "demo_user", 
        analysis_dict
    )
    
    # Update the live response object with the final backboard status
    response.processing_metadata.used_backboard = used_backboard

    return response


# ---------------------------------------------------------------------------
# POST /api/analyze/mock — Instant demo
# ---------------------------------------------------------------------------

@router.post("/mock", response_model=AnalysisResponse)
async def analyze_mock():
    """
    Return a polished demo response instantly.
    Critical fallback for hackathon demos when external APIs are down.
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
        # Return polished mock DCP response
        return MOCK_DCP_ANALYSIS

    _validate_file(file)

    # --- OCR ---
    raw_text, used_vision, ocr_mode = await vision_service.extract_text_from_upload(file)
    clauses = model_service.split_into_clauses(raw_text)

    if not clauses:
        raise HTTPException(status_code=422, detail="No analysable clauses found.")

    # --- Simulate pages (split text into ~page-sized chunks) ---
    page_size = max(1, len(clauses) // 4)
    pages = [
        " ".join(clauses[i : i + page_size])
        for i in range(0, len(clauses), page_size)
    ]
    if not pages:
        pages = [raw_text]

    # --- DCP processing ---
    dcp_metrics, used_dcp, dcp_mode = await dcp_service.process_pages_parallel(pages)

    # --- Classification ---
    flagged_raw = model_service.hybrid_predict(clauses, top_n=5)
    used_distilbert = model_service.is_model_loaded()

    risk_numeric, risk_label = model_service.compute_risk_score(flagged_raw)
    summary, flagged_explained, used_gemma = await gemma_service.improve_analysis_with_gemma(
        flagged_raw, risk_numeric, risk_label
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
            why_it_matters=c.get("why_it_matters"),
            suggested_action=c.get("suggested_action"),
        )
        for c in flagged_explained
    ]

    response = DCPAnalysisResponse(
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
            dcp_mode=dcp_mode,
            processing_time_ms=elapsed_ms,
            ocr_mode=ocr_mode,
            model_source=model_service.get_model_source(),
            endpoint_mode="real_analyze_dcp",
        ),
    )

    # --- Step 8: Save to vault ---
    analysis_dict = response.model_dump()
    analysis_dict["filename"] = file.filename or "Uploaded Document (DCP)"
    
    _, used_backboard = await backboard_service.save_document_analysis(
        user_id or "demo_user", 
        analysis_dict
    )
    
    # Update the live response object with the final backboard status
    response.processing_metadata.used_backboard = used_backboard

    return response
