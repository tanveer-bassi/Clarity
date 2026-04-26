"""
gemma_service.py — LLM-powered plain-English explanations via Gemma.

If GEMINI_API_KEY is set, calls the Google GenAI API using Gemma models.
Otherwise uses deterministic fallback translations so the demo always works.
"""

from __future__ import annotations

import json
import logging
import os
from typing import List, Optional, Tuple

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


def _is_api_configured() -> bool:
    key = os.getenv("GEMINI_API_KEY", "")
    return bool(key and not key.startswith("your-"))


def _get_fallback_translation(clause_type: str) -> str:
    return FALLBACK_TRANSLATIONS.get(
        clause_type,
        "This clause may contain terms that limit your rights or increase your obligations.",
    )


# ---------------------------------------------------------------------------
# Real Gemma calls
# ---------------------------------------------------------------------------

async def improve_analysis_with_gemma(
    flagged_clauses: List[dict], 
    risk_score: int, 
    risk_label: str
) -> Tuple[str, List[dict], bool]:
    """
    Use Gemma to improve the analysis summary and clause translations.
    Returns (summary, improved_clauses, used_gemma).
    """
    if not _is_api_configured():
        return _apply_fallbacks(flagged_clauses, risk_score, risk_label)

    primary_model = os.getenv("GEMMA_MODEL_NAME", "gemma-4-31b-it")
    fallback_model = "gemma-4-26b-a4b-it"

    # Prepare input data for Gemma (limited context as requested)
    input_data = {
        "overall_risk_score": risk_label,
        "risk_score_numeric": risk_score,
        "flagged_clauses": [
            {
                "type": c["type"],
                "severity": c["severity"],
                "original_text": c["original_text"],
                "fallback_translation": _get_fallback_translation(c["type"])
            }
            for c in flagged_clauses
        ]
    }

    prompt = f"""You are a consumer-rights legal assistant for Clarity.
Your goal is to explain complex legal risks in plain, empathetic English.

Input Data:
{json.dumps(input_data, indent=2)}

Task:
1. Provide an overall executive summary (2-3 sentences).
2. For each clause, provide a clear translation, why it matters, and a suggested action.

Return ONLY strict JSON in this format:
{{
  "summary_plain_english": "...",
  "clause_explanations": [
    {{
      "type": "...",
      "translation": "...",
      "why_it_matters": "...",
      "suggested_action": "..."
    }}
  ]
}}
"""

    for model_name in [primary_model, fallback_model]:
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
            
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )

            if not response or not response.text:
                continue

            # Parse JSON
            try:
                # Clean possible markdown wrap
                raw_text = response.text.strip()
                if raw_text.startswith("```json"):
                    raw_text = raw_text.split("```json")[1].split("```")[0].strip()
                elif raw_text.startswith("```"):
                    raw_text = raw_text.split("```")[1].split("```")[0].strip()
                
                gemma_data = json.loads(raw_text)
                
                summary = gemma_data.get("summary_plain_english", "")
                explanations = gemma_data.get("clause_explanations", [])
                
                # Merge Gemma explanations back into flagged_clauses
                # We match by type and index to be safe if types repeat
                improved_clauses = []
                for i, c in enumerate(flagged_clauses):
                    new_clause = c.copy()
                    # Try to find matching explanation from Gemma
                    if i < len(explanations):
                        exp = explanations[i]
                        new_clause["translation"] = exp.get("translation", _get_fallback_translation(c["type"]))
                        new_clause["why_it_matters"] = exp.get("why_it_matters", "")
                        new_clause["suggested_action"] = exp.get("suggested_action", "")
                    else:
                        new_clause["translation"] = _get_fallback_translation(c["type"])
                    
                    improved_clauses.append(new_clause)

                if not summary:
                    summary = _fallback_summary(flagged_clauses, risk_score, risk_label)

                logger.info("Successfully used Gemma model: %s", model_name)
                return summary, improved_clauses, True

            except (json.JSONDecodeError, KeyError) as e:
                logger.warning("Gemma JSON parse failed for model %s: %s", model_name, e)
                continue

        except Exception as exc:
            logger.warning("Gemma call failed for model %s: %s", model_name, exc)
            continue

    # If all models fail
    return _apply_fallbacks(flagged_clauses, risk_score, risk_label)


# ---------------------------------------------------------------------------
# Fallback implementations
# ---------------------------------------------------------------------------

def _apply_fallbacks(
    flagged_clauses: List[dict], 
    risk_score: int, 
    risk_label: str
) -> Tuple[str, List[dict], bool]:
    """Helper to apply all fallbacks at once."""
    improved_clauses = []
    for c in flagged_clauses:
        new_clause = c.copy()
        if not new_clause.get("translation"):
            new_clause["translation"] = _get_fallback_translation(c["type"])
        improved_clauses.append(new_clause)
    
    summary = _fallback_summary(flagged_clauses, risk_score, risk_label)
    return summary, improved_clauses, False


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
# Deprecated/Compatibility API (Optional, keeping for internal references)
# ---------------------------------------------------------------------------

async def explain_clauses(flagged_clauses: List[dict]) -> tuple[List[dict], bool]:
    # For backward compatibility if needed, but better to use the unified function
    _, clauses, used = await improve_analysis_with_gemma(flagged_clauses, 0, "UNKNOWN")
    return clauses, used

async def generate_summary(
    flagged_clauses: List[dict], risk_score: int, risk_label: str
) -> tuple[str, bool]:
    summary, _, used = await improve_analysis_with_gemma(flagged_clauses, risk_score, risk_label)
    return summary, used
