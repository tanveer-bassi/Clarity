"""
gemma_service.py — LLM-powered plain-English explanations.

If GEMINI_API_KEY is set, calls the Google Gemini / Gemma API.
Otherwise uses deterministic fallback translations so the demo always works.
"""

from __future__ import annotations

import logging
import os
from typing import List

logger = logging.getLogger("clearconsent.gemma")

# ---------------------------------------------------------------------------
# Deterministic fallback translations (always available)
# ---------------------------------------------------------------------------

FALLBACK_TRANSLATIONS: dict[str, str] = {
    "WAIVER_OF_RIGHTS": (
        "You may be giving up your ability to sue or take legal action."
    ),
    "ARBITRATION": (
        "You may be forced to resolve disputes privately instead of going to court."
    ),
    "FINANCIAL_LIABILITY": (
        "You may be responsible for costs your insurance or another party does not cover."
    ),
    "AUTO_RENEWAL": (
        "This agreement may renew automatically unless you cancel in time."
    ),
    "LIABILITY_LIMITATION": (
        "The other party may be limiting how much responsibility they have if something goes wrong."
    ),
    "TERMINATION": (
        "The other party may be able to end the agreement with limited notice or justification."
    ),
    "EMPLOYMENT_RESTRICTION": (
        "You may be restricted from working for competitors or soliciting clients after leaving."
    ),
    "LEGAL_JURISDICTION": (
        "Any disputes may need to be resolved in a specific jurisdiction that could be inconvenient for you."
    ),
    "LIMITED_PROTECTION": (
        "The protections or warranties offered may be significantly limited in scope or duration."
    ),
}

FALLBACK_SUMMARY_TEMPLATE = (
    "This document contains {count} potentially risky clause(s). "
    "The overall risk level is {level} ({score}/100). "
    "{top_risks}"
    "Review flagged sections carefully before signing."
)


def _gemini_available() -> bool:
    return bool(os.getenv("GEMINI_API_KEY"))


# ---------------------------------------------------------------------------
# Real Gemini / Gemma calls
# ---------------------------------------------------------------------------


async def _gemini_explain(flagged_clauses: List[dict]) -> List[dict]:
    """Use Gemini API to generate plain-English explanations."""
    try:
        from google import genai  # type: ignore

        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

        for clause in flagged_clauses:
            if clause.get("translation"):
                continue  # Already has a translation

            prompt = (
                "You are a consumer-rights assistant. Explain the following legal "
                "clause in one or two plain-English sentences that a non-lawyer can "
                "understand. Focus on what the signer is giving up or agreeing to.\n\n"
                f"Category: {clause['type']}\n"
                f"Clause: \"{clause['original_text']}\"\n\n"
                "Plain-English explanation:"
            )

            response = client.models.generate_content(
                model="gemma-3-4b-it",
                contents=prompt,
            )
            clause["translation"] = response.text.strip()

        return flagged_clauses
    except Exception as exc:
        logger.warning("Gemini explain failed: %s — using fallback", exc)
        return _fallback_explain(flagged_clauses)


async def _gemini_summary(flagged_clauses: List[dict], risk_score: int, risk_label: str) -> str:
    """Use Gemini API to generate an overall document summary."""
    try:
        from google import genai  # type: ignore

        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

        clause_descriptions = "\n".join(
            f"- {c['type']}: \"{c['original_text'][:120]}...\"" for c in flagged_clauses
        )

        prompt = (
            "You are a consumer-rights assistant. Summarize the risks of a legal "
            "document in 2–3 plain-English sentences. The document has a risk score "
            f"of {risk_score}/100 ({risk_label}).\n\n"
            f"Flagged clauses:\n{clause_descriptions}\n\n"
            "Summary:"
        )

        response = client.models.generate_content(
            model="gemma-3-4b-it",
            contents=prompt,
        )
        return response.text.strip()
    except Exception as exc:
        logger.warning("Gemini summary failed: %s — using fallback", exc)
        return _fallback_summary(flagged_clauses, risk_score, risk_label)


# ---------------------------------------------------------------------------
# Fallback implementations
# ---------------------------------------------------------------------------


def _fallback_explain(flagged_clauses: List[dict]) -> List[dict]:
    for clause in flagged_clauses:
        if not clause.get("translation"):
            clause["translation"] = FALLBACK_TRANSLATIONS.get(
                clause["type"],
                "This clause may contain terms that limit your rights or increase your obligations.",
            )
    return flagged_clauses


def _fallback_summary(
    flagged_clauses: List[dict], risk_score: int, risk_label: str
) -> str:
    categories = list({c["type"] for c in flagged_clauses})
    readable = [cat.replace("_", " ").title() for cat in categories[:3]]
    top_risks = (
        f"Key concerns include {', '.join(readable)}. "
        if readable
        else ""
    )
    return FALLBACK_SUMMARY_TEMPLATE.format(
        count=len(flagged_clauses),
        level=risk_label,
        score=risk_score,
        top_risks=top_risks,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def explain_clauses(flagged_clauses: List[dict]) -> tuple[List[dict], bool]:
    """
    Add plain-English translations to flagged clauses.
    Returns (clauses_with_translations, used_gemma).
    """
    if _gemini_available():
        result = await _gemini_explain(flagged_clauses)
        return result, True

    return _fallback_explain(flagged_clauses), False


async def generate_summary(
    flagged_clauses: List[dict], risk_score: int, risk_label: str
) -> tuple[str, bool]:
    """
    Generate a plain-English summary of the document.
    Returns (summary_text, used_gemma).
    """
    if _gemini_available():
        summary = await _gemini_summary(flagged_clauses, risk_score, risk_label)
        return summary, True

    return _fallback_summary(flagged_clauses, risk_score, risk_label), False
