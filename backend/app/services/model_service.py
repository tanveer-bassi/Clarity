"""
model_service.py — Hybrid clause classifier.

Loads the custom DistilBERT model with a cascading strategy:
  1. Local directory  (CLEARCONSENT_MODEL_DIR or ../ml/clearconsent-distilbert-v2)
  2. Hugging Face Hub (CLEARCONSENT_HF_MODEL_ID or 1Ghoul1/clearconsent-distilbert-v2)
  3. Rule-based only  (no model needed)

Combines DistilBERT with deterministic rule-based predictions for must-catch
categories (arbitration, waiver, financial liability, auto-renewal,
liability limitation).
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import List, Literal, Tuple

logger = logging.getLogger("clearconsent.model")

# ---------------------------------------------------------------------------
# Model source resolution
# ---------------------------------------------------------------------------

_DEFAULT_MODEL_DIR = str(
    Path(__file__).resolve().parent.parent.parent.parent / "ml" / "clearconsent-distilbert-v2"
)
MODEL_DIR = os.getenv("CLEARCONSENT_MODEL_DIR", _DEFAULT_MODEL_DIR)

_DEFAULT_HF_MODEL_ID = "1Ghoul1/clearconsent-distilbert-v2"
HF_MODEL_ID = os.getenv("CLEARCONSENT_HF_MODEL_ID", _DEFAULT_HF_MODEL_ID)

# ---------------------------------------------------------------------------
# Lazy-loaded model & tokenizer (populated on first call)
# ---------------------------------------------------------------------------

_tokenizer = None
_model = None
_device = None
_model_available = False
_model_source: Literal["local", "huggingface", "rules_only"] = "rules_only"


def _load_model() -> bool:
    """
    Attempt to load the DistilBERT model once using a cascading strategy:
      1. Local directory (CLEARCONSENT_MODEL_DIR)
      2. Hugging Face Hub (CLEARCONSENT_HF_MODEL_ID)
      3. Falls back to rules_only if both fail.

    Returns True if the model was loaded successfully.
    """
    global _tokenizer, _model, _device, _model_available, _model_source

    if _model_available:
        return True

    try:
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        _device = "cuda" if torch.cuda.is_available() else "cpu"

        # --- Strategy 1: Local directory ---
        local_path = Path(MODEL_DIR)
        if local_path.exists() and any(local_path.iterdir()):
            logger.info("Loading model from local directory: %s", MODEL_DIR)
            _tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR)
            _model = AutoModelForSequenceClassification.from_pretrained(MODEL_DIR)
            _model.to(_device)
            _model.eval()
            _model_available = True
            _model_source = "local"
            logger.info(
                "DistilBERT loaded on %s from local path: %s", _device, MODEL_DIR
            )
            return True

        logger.info(
            "Local model directory not found or empty: %s — trying Hugging Face",
            MODEL_DIR,
        )

    except Exception as exc:
        logger.warning(
            "Failed to load model from local directory: %s — trying Hugging Face",
            exc,
        )

    # --- Strategy 2: Hugging Face Hub ---
    try:
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        if _device is None:
            _device = "cuda" if torch.cuda.is_available() else "cpu"

        logger.info("Loading model from Hugging Face: %s", HF_MODEL_ID)
        _tokenizer = AutoTokenizer.from_pretrained(HF_MODEL_ID)
        _model = AutoModelForSequenceClassification.from_pretrained(HF_MODEL_ID)
        _model.to(_device)
        _model.eval()
        _model_available = True
        _model_source = "huggingface"
        logger.info(
            "DistilBERT loaded on %s from Hugging Face: %s", _device, HF_MODEL_ID
        )
        return True

    except Exception as exc:
        logger.warning(
            "Failed to load model from Hugging Face (%s): %s — falling back to rules only",
            HF_MODEL_ID,
            exc,
        )

    # --- Strategy 3: Rules only ---
    _model_source = "rules_only"
    logger.info("Model unavailable — using rule-based classification only")
    return False


def is_model_loaded() -> bool:
    return _model_available


def get_model_source() -> str:
    """Return the source of the loaded model: 'local', 'huggingface', or 'rules_only'."""
    return _model_source


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
    "EMPLOYMENT_RESTRICTION": [
        "non-compete",
        "non-solicit",
        "competing business",
        "restricted period",
        "may not work for a competitor",
        "solicit customers",
        "solicit employees",
    ],
    "TERMINATION": [
        "contract termination",
        "terminate this agreement",
        "upon termination",
        "cancel this contract",
        "right to terminate",
        "immediate termination",
    ],
}

GLOBAL_NEGATION_PATTERNS = [
    "avoids risky clauses",
    "does not include",
    "not included",
]

NEGATION_PATTERNS = {
    "AUTO_RENEWAL": [
        "no automatic renewal",
        "does not automatically renew",
        "will not automatically renew",
        "no automatic renewal, subscription, or recurring charge",
        "there is no automatic renewal",
        "without automatic renewal",
    ],
    "ARBITRATION": [
        "no binding arbitration",
        "not subject to binding arbitration",
        "does not require arbitration",
        "avoids binding arbitration",
        "without binding arbitration",
    ],
    "WAIVER_OF_RIGHTS": [
        "no lawsuit waiver",
        "no lawsuit waivers",
        "does not waive the right",
        "does not waive your right",
        "no waiver of rights",
    ],
    "FINANCIAL_LIABILITY": [
        "no surprise fees",
        "no unexpected financial responsibility",
        "costs will be explained before services are provided",
        "you may ask for a cost estimate",
    ],
    "LIABILITY_LIMITATION": [
        "no limitation of liability",
        "does not limit liability",
        "no broad liability limits",
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
        lower_clause = clause.lower()
        global_negation_hit = next((p for p in GLOBAL_NEGATION_PATTERNS if p in lower_clause), None)

        # -- Rule-based --
        for category, conf in _rule_classify(clause):
            if global_negation_hit:
                logger.info(f"Skipped {category} because clause contained global negation pattern: {global_negation_hit}")
                continue
            cat_negation_hit = next((p for p in NEGATION_PATTERNS.get(category, []) if p in lower_clause), None)
            if cat_negation_hit:
                logger.info(f"Skipped {category} because clause contained negation pattern: {cat_negation_hit}")
                continue

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
            if global_negation_hit:
                logger.info(f"Skipped DistilBERT {category} because clause contained global negation pattern: {global_negation_hit}")
                continue
            cat_negation_hit = next((p for p in NEGATION_PATTERNS.get(category, []) if p in lower_clause), None)
            if cat_negation_hit:
                logger.info(f"Skipped DistilBERT {category} because clause contained negation pattern: {cat_negation_hit}")
                continue

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
                # Deterministic hallucination shield:
                # If a category is historically noisy or high-risk, we REQUIRE a rule hit.
                # If there's no rule hit (not in 'seen'), we discard the DistilBERT prediction.
                if category in [
                    "FINANCIAL_LIABILITY", "WAIVER_OF_RIGHTS", "ARBITRATION", 
                    "LIABILITY_LIMITATION", "EMPLOYMENT_RESTRICTION", "TERMINATION"
                ]:
                    continue

                seen[key] = {
                    "type": category,
                    "original_text": clause,
                    "confidence": conf,
                    "severity": _severity(category, conf),
                    "source": "distilbert",
                }

    # Deduplicate by category: keep the highest confidence hit for each category
    deduped: dict[str, dict] = {}
    for item in seen.values():
        cat = item["type"]
        if cat not in deduped or item["confidence"] > deduped[cat]["confidence"]:
            deduped[cat] = item

    # Sort: CRITICAL > HIGH > MEDIUM > LOW, then by confidence descending
    severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    results = sorted(
        deduped.values(),
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
