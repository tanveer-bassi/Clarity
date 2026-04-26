"""
backboard_service.py — Backboard integration.

Session identity: each user gets a Backboard Thread ID (stored in browser localStorage).
Consent vault: analysis results are saved per-thread via the Backboard SDK.
Falls back to in-memory store when BACKBOARD_API_KEY is not set.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger("clearconsent.backboard")

# ---------------------------------------------------------------------------
# In-memory fallback (keyed by thread_id / user_id)
# ---------------------------------------------------------------------------

_mock_store: dict[str, list[dict]] = {}

# Cached SDK client and assistant ID (initialised lazily)
_client = None
_assistant_id: str | None = None


# ---------------------------------------------------------------------------
# SDK helpers
# ---------------------------------------------------------------------------


def _get_client():
    global _client
    if _client is None and os.getenv("BACKBOARD_API_KEY"):
        from backboard import BackboardClient
        _client = BackboardClient(api_key=os.getenv("BACKBOARD_API_KEY"))
    return _client


def _backboard_available() -> bool:
    return bool(os.getenv("BACKBOARD_API_KEY"))


async def _get_or_create_assistant() -> str | None:
    """Return the Clarity assistant_id, creating it once per process if needed."""
    global _assistant_id
    if _assistant_id:
        return _assistant_id
    _assistant_id = os.getenv("BACKBOARD_ASSISTANT_ID")
    if _assistant_id:
        return _assistant_id
    client = _get_client()
    if client is None:
        return None
    try:
        assistant = await client.create_assistant(
            name="Clarity",
            system_prompt=(
                "You are Clarity, an AI assistant that helps users understand "
                "legal and medical documents by identifying risky clauses."
            ),
        )
        _assistant_id = assistant.assistant_id
        logger.info(
            "Created Backboard assistant %s — persist this as BACKBOARD_ASSISTANT_ID",
            _assistant_id,
        )
        return _assistant_id
    except Exception as exc:
        logger.warning("Failed to create Backboard assistant: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Public: session management
# ---------------------------------------------------------------------------


async def create_user_thread() -> str | None:
    """
    Create a Backboard Thread for a new user session.
    Returns thread_id, or None if Backboard is not configured.
    """
    client = _get_client()
    if client is None:
        return None
    try:
        assistant_id = await _get_or_create_assistant()
        if not assistant_id:
            return None
        thread = await client.create_thread(assistant_id)
        return thread.thread_id
    except Exception as exc:
        logger.warning("Failed to create Backboard thread: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Public: consent vault
# ---------------------------------------------------------------------------


async def save_document_analysis(
    user_id: str, analysis: dict
) -> tuple[bool, bool]:
    """
    Persist an analysis to the consent vault.
    user_id is the Backboard Thread ID (or any session key).
    Returns (success, used_backboard).
    """
    entry = {
        "document_id": analysis["document_id"],
        "filename": analysis.get("filename", "Uploaded Document"),
        "overall_risk_score": analysis["overall_risk_score"],
        "risk_score_numeric": analysis["risk_score_numeric"],
        "flagged_count": len(analysis.get("flagged_clauses", [])),
        "scanned_at": datetime.now(timezone.utc).isoformat(),
    }

    # Always cache locally for fast history reads within the same process
    _mock_store.setdefault(user_id, []).append(entry)

    if _backboard_available():
        client = _get_client()
        try:
            await client.add_message(
                thread_id=user_id,
                content=f"[VAULT] {json.dumps(entry)}",
                memory="Auto",
            )
            return True, True
        except Exception as exc:
            logger.warning("Backboard save failed: %s — kept in local cache", exc)
            return True, False

    return True, False


async def get_user_history(user_id: str) -> tuple[list[dict], bool]:
    """
    Retrieve a user's scan history.
    Returns (history_items, used_backboard).
    """
    if user_id in _mock_store and _mock_store[user_id]:
        return list(reversed(_mock_store[user_id])), _backboard_available()

    # Seed demo data so the UI always has something to show on first load
    return [
        {
            "document_id": "doc_38201",
            "filename": "Hospital_Consent_Form.pdf",
            "overall_risk_score": "HIGH",
            "risk_score_numeric": 74,
            "flagged_count": 5,
            "scanned_at": "2026-04-24T14:30:00Z",
        },
        {
            "document_id": "doc_29104",
            "filename": "Apartment_Lease_Agreement.pdf",
            "overall_risk_score": "MEDIUM",
            "risk_score_numeric": 48,
            "flagged_count": 3,
            "scanned_at": "2026-04-22T09:15:00Z",
        },
        {
            "document_id": "doc_15773",
            "filename": "Employment_Offer_Letter.pdf",
            "overall_risk_score": "LOW",
            "risk_score_numeric": 22,
            "flagged_count": 1,
            "scanned_at": "2026-04-20T16:45:00Z",
        },
    ], False
