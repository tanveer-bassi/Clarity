"""
history.py — Consent vault history route.

GET /api/history/{user_id}  — Returns saved scans from Backboard or mock store.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter

from app.models.schemas import HistoryItem, HistoryResponse
from app.services import backboard_service

logger = logging.getLogger("clearconsent.history")
router = APIRouter(prefix="/history", tags=["History"])


@router.get("/{user_id}", response_model=HistoryResponse)
async def get_history(user_id: str):
    """
    Retrieve a user's consent vault history.
    Uses Backboard if configured, otherwise returns mock/in-memory data.
    """
    items, used_backboard = await backboard_service.get_user_history(user_id)

    documents = [
        HistoryItem(
            document_id=item.get("document_id", "unknown"),
            filename=item.get("filename", "Document"),
            overall_risk_score=item.get("overall_risk_score", "MEDIUM"),
            risk_score_numeric=item.get("risk_score_numeric", 50),
            flagged_count=item.get("flagged_count", 0),
            scanned_at=item.get("scanned_at", ""),
            # Full fields for detail view
            summary_plain_english=item.get("summary_plain_english"),
            flagged_clauses=item.get("flagged_clauses"),
            dcp_metrics=item.get("dcp_metrics"),
            processing_metadata=item.get("processing_metadata"),
        )
        for item in items
    ]

    return HistoryResponse(
        user_id=user_id,
        documents=documents,
    )
