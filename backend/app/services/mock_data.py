"""
mock_data.py — Polished demo response for the /api/analyze/mock endpoint.

Returns a production-quality response instantly so the hackathon demo
always works even if every external API is offline.
"""

from __future__ import annotations

MOCK_ANALYSIS = {
    "document_id": "doc_84729",
    "overall_risk_score": "HIGH",
    "risk_score_numeric": 74,
    "summary_plain_english": (
        "This document contains 5 potentially risky clauses. "
        "The overall risk level is HIGH (74/100). "
        "Key concerns include Waiver Of Rights, Arbitration, and Financial Liability. "
        "You may be waiving your right to sue, agreeing to resolve disputes through "
        "private arbitration instead of court, accepting financial responsibility for "
        "uncovered costs, and consenting to automatic renewal. "
        "Review all flagged sections carefully before signing."
    ),
    "flagged_clauses": [
        {
            "type": "WAIVER_OF_RIGHTS",
            "original_text": (
                "By signing this document, the patient agrees to waive the right "
                "to bring a lawsuit against Acme Regional Medical Center. The patient "
                "releases the hospital from all claims, demands, and causes of action "
                "arising from treatment provided."
            ),
            "translation": (
                "You may be giving up your ability to sue or take legal action "
                "against the hospital, even if something goes wrong during treatment."
            ),
            "severity": "CRITICAL",
            "confidence": 0.93,
            "source": "merged",
        },
        {
            "type": "ARBITRATION",
            "original_text": (
                "Any dispute arising out of this agreement shall be resolved "
                "exclusively through binding arbitration. The patient agrees that "
                "claims will not be resolved through a jury trial or class action."
            ),
            "translation": (
                "You may be forced to resolve disputes privately through an "
                "arbitrator instead of a judge or jury in court."
            ),
            "severity": "CRITICAL",
            "confidence": 0.91,
            "source": "rule",
        },
        {
            "type": "FINANCIAL_LIABILITY",
            "original_text": (
                "The patient accepts full financial responsibility for all charges, "
                "fees, deductibles, and unpaid balances not covered by insurance, "
                "including out-of-network provider fees."
            ),
            "translation": (
                "You may be responsible for significant costs that your insurance "
                "does not cover, including out-of-network charges and collection fees."
            ),
            "severity": "CRITICAL",
            "confidence": 0.88,
            "source": "merged",
        },
        {
            "type": "LIABILITY_LIMITATION",
            "original_text": (
                "In no event shall Acme Regional Medical Center's total liability "
                "exceed the amount of fees paid by the patient in the twelve months "
                "preceding the claim. The hospital disclaims all liability for "
                "consequential damages."
            ),
            "translation": (
                "The hospital is limiting how much they would owe you if something "
                "goes wrong — even if the actual harm is far greater."
            ),
            "severity": "HIGH",
            "confidence": 0.82,
            "source": "merged",
        },
        {
            "type": "AUTO_RENEWAL",
            "original_text": (
                "This agreement will automatically renew for successive one-year "
                "terms unless either party provides written notice of cancellation "
                "at least thirty (30) days before the renewal term begins."
            ),
            "translation": (
                "This agreement renews automatically each year. If you forget to "
                "cancel in writing at least 30 days early, you're locked in again."
            ),
            "severity": "HIGH",
            "confidence": 0.85,
            "source": "merged",
        },
    ],
    "processing_metadata": {
        "used_google_vision": True,
        "used_distilbert": True,
        "used_gemma": True,
        "used_backboard": True,
        "used_dcp": False,
        "processing_time_ms": 1840,
    },
}


MOCK_DCP_ANALYSIS = {
    **MOCK_ANALYSIS,
    "dcp_metrics": {
        "pages_processed": 20,
        "sequential_time_ms": 40000,
        "dcp_parallel_time_ms": 4200,
        "speedup_factor": 9.5,
    },
    "processing_metadata": {
        **MOCK_ANALYSIS["processing_metadata"],
        "used_dcp": True,
    },
}
