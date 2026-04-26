"""
Pydantic schemas for the ClearConsent API.
Defines the strict response contract that the frontend expects.
"""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Shared / nested schemas
# ---------------------------------------------------------------------------

class FlaggedClause(BaseModel):
    """A single risky clause detected in the document."""
    type: str = Field(..., description="Risk category, e.g. WAIVER_OF_RIGHTS")
    original_text: str = Field(..., description="Verbatim clause from the document")
    translation: str = Field(..., description="Plain-English explanation")
    severity: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"] = "MEDIUM"
    confidence: float = Field(..., ge=0.0, le=1.0)
    source: Literal["rule", "distilbert", "merged"] = "distilbert"
    why_it_matters: Optional[str] = Field(None, description="Detailed explanation of the risk")
    suggested_action: Optional[str] = Field(None, description="Recommended next step for the user")


class ProcessingMetadata(BaseModel):
    """Tracks which integrations were actually used during analysis."""
    used_google_vision: bool = False
    used_distilbert: bool = False
    used_gemma: bool = False
    used_backboard: bool = False
    used_dcp: bool = False
    processing_time_ms: int = 0
    ocr_mode: Optional[str] = None
    model_source: Optional[str] = None
    endpoint_mode: Optional[str] = None
    extracted_text_preview: Optional[str] = None


class DCPMetrics(BaseModel):
    """Distributive Computing Protocol performance metrics."""
    pages_processed: int = 1
    sequential_time_ms: int = 0
    dcp_parallel_time_ms: int = 0
    speedup_factor: float = 1.0


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class AnalysisResponse(BaseModel):
    """Full analysis response returned to the frontend."""
    document_id: str
    overall_risk_score: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    risk_score_numeric: int = Field(..., ge=0, le=100)
    summary_plain_english: str
    flagged_clauses: List[FlaggedClause]
    processing_metadata: ProcessingMetadata


class DCPAnalysisResponse(BaseModel):
    """Analysis response that includes DCP parallel-processing metrics."""
    document_id: str
    overall_risk_score: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    risk_score_numeric: int = Field(..., ge=0, le=100)
    summary_plain_english: str
    flagged_clauses: List[FlaggedClause]
    dcp_metrics: DCPMetrics
    processing_metadata: ProcessingMetadata


class HistoryItem(BaseModel):
    """One entry in a user's consent vault history."""
    document_id: str
    filename: str
    overall_risk_score: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    risk_score_numeric: int
    flagged_count: int
    scanned_at: str  # ISO-8601 timestamp


class HistoryResponse(BaseModel):
    """Wrapper for the history endpoint."""
    user_id: str
    documents: List[HistoryItem]


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = "healthy"
    version: str = "1.0.0"
    model_loaded: bool = False
    model_source: str = "rules_only"
    integrations: dict = {}
