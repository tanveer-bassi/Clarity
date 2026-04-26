"""
backboard_service.py — Backboard integration for the consent vault.

If BACKBOARD_API_KEY is set, saves and retrieves analyses via the
Backboard API.  Otherwise uses in-memory storage so the demo always works.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import List, Optional

logger = logging.getLogger("clearconsent.backboard")

# ---------------------------------------------------------------------------
# In-memory mock store (used when Backboard is not configured)
# ---------------------------------------------------------------------------

_mock_store: dict[str, list[dict]] = {}


def _backboard_available() -> bool:
    key = os.getenv("BACKBOARD_API_KEY", "")
    return bool(key and not key.startswith("your-"))


# ---------------------------------------------------------------------------
# Real Backboard implementation
# ---------------------------------------------------------------------------


async def _real_save(user_id: str, analysis: dict) -> bool:
    """Save analysis to the Backboard API."""
    try:
        import httpx

        api_key = os.getenv("BACKBOARD_API_KEY")
        base_url = os.getenv("BACKBOARD_API_URL", "https://app.backboard.io/api")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{base_url}/documents",
                headers={
                    "X-API-Key": api_key,
                    "Content-Type": "application/json",
                },
                json={
                    "user_id": user_id,
                    "document_id": analysis["document_id"],
                    "risk_score": analysis["risk_score_numeric"],
                    "risk_label": analysis["overall_risk_score"],
                    "flagged_clauses": analysis["flagged_clauses"],
                    "summary": analysis["summary_plain_english"],
                    "scanned_at": datetime.now(timezone.utc).isoformat(),
                },
                timeout=10.0,
            )
            response.raise_for_status()
            return True
    except Exception as exc:
        logger.warning("Backboard save failed: %s — using mock store", exc)
        _mock_save(user_id, analysis)
        return False


async def _real_history(user_id: str) -> list[dict]:
    """Retrieve history from the Backboard API."""
    try:
        import httpx

        api_key = os.getenv("BACKBOARD_API_KEY")
        base_url = os.getenv("BACKBOARD_API_URL", "https://app.backboard.io/api")

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{base_url}/documents",
                headers={"X-API-Key": api_key},
                params={"user_id": user_id},
                timeout=10.0,
            )
            response.raise_for_status()
            return response.json().get("documents", [])
    except Exception as exc:
        logger.warning("Backboard history failed: %s — using mock", exc)
        return _mock_history(user_id)


# ---------------------------------------------------------------------------
# Mock implementations
# ---------------------------------------------------------------------------


def _mock_save(user_id: str, analysis: dict) -> None:
    """Save to in-memory store."""
    if user_id not in _mock_store:
        _mock_store[user_id] = []

    record = analysis.copy()
    record["scanned_at"] = datetime.now(timezone.utc).isoformat()
    # Add helper field for frontend card rendering if missing
    if "flagged_count" not in record:
        record["flagged_count"] = len(analysis.get("flagged_clauses", []))
        
    _mock_store[user_id].append(record)


def _mock_history(user_id: str) -> list[dict]:
    """Return in-memory history, or seed some demo entries."""
    if user_id in _mock_store and _mock_store[user_id]:
        return _mock_store[user_id]

    # Seed demo data so the UI always has something to show
    return [
        {
            "document_id": "doc_38201",
            "filename": "Hospital_Consent_Form.pdf",
            "overall_risk_score": "HIGH",
            "risk_score_numeric": 74,
            "flagged_count": 5,
            "summary_plain_english": "High risk detected in liability waivers and arbitration requirements. This document significantly limits your right to sue for malpractice.",
            "flagged_clauses": [
                {"type": "Liability Limitation", "severity": "HIGH", "original_text": "Facility is not liable for any injury...", "translation": "They are trying to avoid paying if they hurt you.", "confidence": 0.95}
            ],
            "processing_metadata": {"ocr_mode": "pdf_text_extraction", "model_source": "distilbert", "endpoint_mode": "mock", "used_distilbert": True, "used_vision": False, "used_gemma": False, "used_backboard": False},
            "scanned_at": "2026-04-24T14:30:00Z",
        },
        {
            "document_id": "doc_29104",
            "filename": "Apartment_Lease_Agreement.pdf",
            "overall_risk_score": "MEDIUM",
            "risk_score_numeric": 48,
            "flagged_count": 3,
            "summary_plain_english": "Moderate risk found in security deposit return terms and early termination penalties.",
            "flagged_clauses": [
                {"type": "Termination Penalty", "severity": "MEDIUM", "original_text": "3 months rent penalty for early exit.", "translation": "Moving out early will cost you 3 months of rent.", "confidence": 0.88}
            ],
            "processing_metadata": {"ocr_mode": "pdf_text_extraction", "model_source": "distilbert", "endpoint_mode": "mock", "used_distilbert": True, "used_vision": False, "used_gemma": False, "used_backboard": False},
            "scanned_at": "2026-04-22T09:15:00Z",
        },
        {
            "document_id": "doc_15773",
            "filename": "Employment_Offer_Letter.pdf",
            "overall_risk_score": "LOW",
            "risk_score_numeric": 22,
            "flagged_count": 1,
            "summary_plain_english": "Low risk document. Standard at-will employment terms detected.",
            "flagged_clauses": [
                {"type": "At-Will Employment", "severity": "LOW", "original_text": "Employment may be terminated by either party...", "translation": "Either you or the company can end the job at any time.", "confidence": 0.92}
            ],
            "processing_metadata": {"ocr_mode": "pdf_text_extraction", "model_source": "distilbert", "endpoint_mode": "mock", "used_distilbert": True, "used_vision": False, "used_gemma": False, "used_backboard": False},
            "scanned_at": "2026-04-20T16:45:00Z",
        },
    ]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def save_document_analysis(
    user_id: str, analysis: dict
) -> tuple[bool, bool]:
    """
    Persist an analysis to the consent vault.

    Returns (success, used_backboard).
    """
    if _backboard_available():
        ok = await _real_save(user_id, analysis)
        if ok:
            return True, True
        # If it failed, it already fell back to mock in _real_save
        return True, False

    _mock_save(user_id, analysis)
    return True, False


async def get_user_history(user_id: str) -> tuple[list[dict], bool]:
    """
    Retrieve a user's scan history.

    Returns (history_items, used_backboard).
    """
    if _backboard_available():
        items = await _real_history(user_id)
        return items, True

    return _mock_history(user_id), False
