"""
model_service.py — Hybrid clause classifier.

Loads the custom DistilBERT model from ml/clearconsent-distilbert-v2 and
combines it with deterministic rule-based predictions for must-catch
categories (arbitration, waiver, financial liability, auto-renewal,
liability limitation).
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import List, Tuple

logger = logging.getLogger("clearconsent.model")

# ---------------------------------------------------------------------------
# Model directory resolution
# ---------------------------------------------------------------------------

_DEFAULT_MODEL_DIR = str(
    Path(__file__).resolve().parent.parent.parent.parent / "ml" / "clearconsent-distilbert-v2"
)
MODEL_DIR = os.getenv("CLEARCONSENT_MODEL_DIR", _DEFAULT_MODEL_DIR)

# ---------------------------------------------------------------------------
# Lazy-loaded model & tokenizer (populated on first call)
# ---------------------------------------------------------------------------

_tokenizer = None
_model = None
_device = None
_model_available = False


def _load_model() -> bool:
    """Attempt to load the DistilBERT model once. Returns success flag."""
    global _tokenizer, _model, _device, _model_available

    if _model_available:
        return True

    try:
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        if not Path(MODEL_DIR).exists():
            logger.warning("Model directory not found: %s", MODEL_DIR)
            return False

        _device = "cuda" if torch.cuda.is_available() else "cpu"
        _tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR)
        _model = AutoModelForSequenceClassification.from_pretrained(MODEL_DIR)
        _model.to(_device)
        _model.eval()
        _model_available = True
        logger.info("DistilBERT loaded on %s from %s", _device, MODEL_DIR)
        return True
    except Exception as exc:
        logger.warning("Could not load DistilBERT model: %s", exc)
        return False


def is_model_loaded() -> bool:
    return _model_available


# ---------------------------------------------------------------------------
# Severity helpers
# ---------------------------------------------------------------------------

_CRITICAL_CATEGORIES = {
    "WAIVER_OF_RIGHTS",
    "ARBITRATION",
    "LIABILITY_LIMITATION",
    "FINANCIAL_LIABILITY",
    "EMPLOYMENT_RESTRICTION",
}


def _severity(category: str, confidence: float) -> str:
    if category in _CRITICAL_CATEGORIES and confidence >= 0.70:
        return "CRITICAL"
    if confidence >= 0.55:
        return "HIGH"
    if confidence >= 0.40:
        return "MEDIUM"
    return "LOW"


# ---------------------------------------------------------------------------
# Rule-based classifier
# ---------------------------------------------------------------------------

RULE_PATTERNS: dict[str, list[str]] = {
    "ARBITRATION": [
        "binding arbitration",
        "arbitration",
        "arbitrator",
        "resolved by arbitration",
        "settled by arbitration",
        "not through a jury trial",
        "waive the right to a jury trial",
        "class action waiver",
    ],
    "WAIVER_OF_RIGHTS": [
        "waive the right",
        "waiver of rights",
        "right to sue",
        "bring a lawsuit",
        "legal action",
        "release from all claims",
        "forever discharges",
        "not to sue",
    ],
    "FINANCIAL_LIABILITY": [
        "financial responsibility",
        "not covered by insurance",
        "unpaid balances",
        "deductibles",
        "out-of-network",
        "indemnify",
        "hold harmless",
        "attorney fees",
    ],
    "AUTO_RENEWAL": [
        "automatically renew",
        "renews automatically",
        "successive terms",
        "renewal term",
        "unless cancelled",
    ],
    "LIABILITY_LIMITATION": [
        "limitation of liability",
        "total liability shall not exceed",
        "not liable",
        "no event shall",
        "consequential damages",
        "incidental damages",
        "disclaims all liability",
    ],
}


def _rule_classify(clause: str) -> List[Tuple[str, float]]:
    """Return list of (category, confidence) pairs matched by rules."""
    lower = clause.lower()
    hits: list[Tuple[str, float]] = []

    for category, patterns in RULE_PATTERNS.items():
        matched = sum(1 for p in patterns if p in lower)
        if matched:
            # Confidence scales with how many keywords matched
            confidence = min(0.65 + 0.10 * matched, 0.99)
            hits.append((category, round(confidence, 4)))

    return hits


# ---------------------------------------------------------------------------
# DistilBERT classifier
# ---------------------------------------------------------------------------

def _distilbert_classify(clause: str, threshold: float = 0.35) -> List[Tuple[str, float]]:
    """Run inference through the DistilBERT model. Returns (category, conf)."""
    if not _model_available:
        return []

    import torch

    inputs = _tokenizer(
        clause,
        return_tensors="pt",
        truncation=True,
        padding=True,
        max_length=256,
    )
    inputs = {k: v.to(_device) for k, v in inputs.items()}

    with torch.no_grad():
        outputs = _model(**inputs)
        probs = torch.sigmoid(outputs.logits)[0]

    results: list[Tuple[str, float]] = []
    for idx, prob in enumerate(probs):
        conf = float(prob)
        if conf >= threshold:
            label = _model.config.id2label[idx]
            results.append((label, round(conf, 5)))

    return results


# ---------------------------------------------------------------------------
# Clause splitting
# ---------------------------------------------------------------------------

_SENTENCE_SPLIT = re.compile(r'(?<=[.!?;])\s+(?=[A-Z"])')


def split_into_clauses(text: str) -> List[str]:
    """Split a block of text into individual clauses/sentences."""
    raw = _SENTENCE_SPLIT.split(text.strip())
    # Filter out very short fragments
    return [c.strip() for c in raw if len(c.strip()) > 20]


# ---------------------------------------------------------------------------
# Public API — hybrid predict
# ---------------------------------------------------------------------------

def hybrid_predict(clauses: List[str], top_n: int = 5) -> List[dict]:
    """
    Run the hybrid classifier on a list of clauses.

    1. Rule-based predictions first (must-catch categories).
    2. DistilBERT predictions second.
    3. Merge duplicates by category + clause.
    4. Sort by severity, then confidence.
    5. Return top N flagged clauses.
    """
    # Try to load the model if not loaded yet
    _load_model()

    seen: dict[str, dict] = {}  # key = f"{category}::{clause_idx}"

    for idx, clause in enumerate(clauses):
        # -- Rule-based --
        for category, conf in _rule_classify(clause):
            key = f"{category}::{idx}"
            if key not in seen or seen[key]["confidence"] < conf:
                seen[key] = {
                    "type": category,
                    "original_text": clause,
                    "confidence": conf,
                    "severity": _severity(category, conf),
                    "source": "rule",
                }

        # -- DistilBERT --
        for category, conf in _distilbert_classify(clause):
            key = f"{category}::{idx}"
            if key in seen:
                # Merge: keep higher confidence, mark as merged
                existing = seen[key]
                if conf > existing["confidence"]:
                    existing["confidence"] = conf
                    existing["source"] = "merged"
                elif existing["source"] == "rule":
                    existing["source"] = "merged"
            else:
                seen[key] = {
                    "type": category,
                    "original_text": clause,
                    "confidence": conf,
                    "severity": _severity(category, conf),
                    "source": "distilbert",
                }

    # Sort: CRITICAL > HIGH > MEDIUM > LOW, then by confidence descending
    severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    results = sorted(
        seen.values(),
        key=lambda x: (severity_order.get(x["severity"], 9), -x["confidence"]),
    )

    return results[:top_n]


# ---------------------------------------------------------------------------
# Risk score computation
# ---------------------------------------------------------------------------

_SEVERITY_POINTS = {"CRITICAL": 30, "HIGH": 20, "MEDIUM": 10, "LOW": 5}


def compute_risk_score(flagged: List[dict]) -> Tuple[int, str]:
    """
    Compute a numeric risk score and a label from flagged clauses.

    Score: sum of severity points, capped at 100.
    Label: LOW 0–30, MEDIUM 31–60, HIGH 61–80, CRITICAL 81–100.
    """
    total = sum(_SEVERITY_POINTS.get(f["severity"], 0) for f in flagged)
    total = min(total, 100)

    if total >= 81:
        label = "CRITICAL"
    elif total >= 61:
        label = "HIGH"
    elif total >= 31:
        label = "MEDIUM"
    else:
        label = "LOW"

    return total, label
