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
    logger.info("[Vault] Saved analysis for user %s: %s", user_id, record.get("filename", "unknown"))


def _mock_history(user_id: str) -> list[dict]:
    """Return in-memory history."""
    items = _mock_store.get(user_id, [])
    logger.info("[Vault] Returning %d history items for %s", len(items), user_id)
    return items


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
    filename = analysis.get("filename", "unknown")
    logger.info("[Vault] Saving analysis for user %s: %s", user_id, filename)
    
    if _backboard_available():
        ok = await _real_save(user_id, analysis)
        if ok:
            return True, True
        # If it failed, it already fell back to mock in _real_save
        logger.info("[Vault] Backboard failed, saved to local fallback")
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
