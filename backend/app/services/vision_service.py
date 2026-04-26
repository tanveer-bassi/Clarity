"""
vision_service.py — Text extraction with cascading strategy.

1. Google Cloud Vision API  (if GOOGLE_APPLICATION_CREDENTIALS is set)
2. Local PDF text extraction (PyPDF2 — works for text-based PDFs)
3. Mock OCR text             (only for /api/analyze/mock or as last resort)

The key principle: /api/analyze must read the ACTUAL uploaded file.
Mock text is only for the explicit /api/analyze/mock demo endpoint.
"""

from __future__ import annotations

import io
import logging
import os
from typing import Literal

from fastapi import UploadFile

logger = logging.getLogger("clearconsent.vision")

# Type alias for OCR mode reporting
OcrMode = Literal["google_vision", "pdf_text_extraction", "fallback_mock"]


# ---------------------------------------------------------------------------
# Configuration check
# ---------------------------------------------------------------------------


def _vision_available() -> bool:
    """Return True when Google Cloud Vision credentials are configured."""
    return bool(
        os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        or os.getenv("GOOGLE_CLOUD_VISION_KEY")
    )


# ---------------------------------------------------------------------------
# Strategy 1: Real Google Cloud Vision OCR
# ---------------------------------------------------------------------------


async def _google_vision_extract(content: bytes) -> str | None:
    """Use Google Cloud Vision API. Returns text or None on failure."""
    try:
        from google.cloud import vision  # type: ignore

        client = vision.ImageAnnotatorClient()
        image = vision.Image(content=content)
        response = client.text_detection(image=image)

        if response.error.message:
            raise RuntimeError(response.error.message)

        texts = response.text_annotations
        if texts:
            return texts[0].description
        return None
    except Exception as exc:
        logger.warning("Google Vision API error: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Strategy 2: Local PDF text extraction (PyPDF2)
# ---------------------------------------------------------------------------


def _extract_pdf_text(content: bytes) -> str | None:
    """Extract text from a PDF using PyPDF2. Returns text or None."""
    try:
        from PyPDF2 import PdfReader

        reader = PdfReader(io.BytesIO(content))
        pages_text = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                pages_text.append(text.strip())

        full_text = "\n\n".join(pages_text).strip()
        if len(full_text) > 20:
            return full_text
        return None
    except Exception as exc:
        logger.warning("PyPDF2 extraction failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Mock OCR text — only used by /api/analyze/mock or as absolute last resort
# ---------------------------------------------------------------------------

MOCK_OCR_TEXT = """PATIENT CONSENT AND TREATMENT AGREEMENT

Acme Regional Medical Center — Patient Services Division

Section 1: Consent to Treatment
The patient hereby consents to the medical and surgical procedures recommended by their attending physician. The patient acknowledges that medicine is not an exact science and that no guarantees have been made regarding the outcome of treatment.

Section 2: Waiver of Rights
By signing this document, the patient agrees to waive the right to bring a lawsuit against Acme Regional Medical Center or its affiliated physicians. The patient releases the hospital from all claims, demands, and causes of action arising from treatment provided. The patient agrees not to sue the hospital or any staff member for any reason related to care received.

Section 3: Arbitration Agreement
Any dispute, claim, or controversy arising out of or relating to this agreement shall be resolved exclusively through binding arbitration administered by a neutral arbitrator. The patient agrees that claims will not be resolved through a jury trial or class action proceeding. This constitutes a class action waiver.

Section 4: Financial Responsibility
The patient accepts full financial responsibility for all charges, fees, deductibles, and unpaid balances not covered by insurance, including out-of-network provider fees. The patient agrees to indemnify and hold harmless the hospital from any costs, including reasonable attorney fees, incurred in collection efforts.

Section 5: Auto-Renewal of Services
This agreement will automatically renew for successive one-year terms unless either party provides written notice of cancellation at least thirty (30) days before the renewal term begins. The renewal term carries the same conditions as the initial agreement.

Section 6: Limitation of Liability
In no event shall Acme Regional Medical Center's total liability exceed the amount of fees paid by the patient in the twelve months preceding the claim. The hospital disclaims all liability for consequential damages, incidental damages, lost wages, or emotional distress arising from treatment.

Section 7: General Provisions
This agreement shall be governed by the laws of the State of California. The patient acknowledges that they have read, understood, and voluntarily agreed to the terms set forth herein. All notices required under this agreement shall be delivered in writing to the addresses on file.

Patient Signature: _________________________  Date: ____________
"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def extract_text_from_upload(file: UploadFile) -> tuple[str, bool, OcrMode]:
    """
    Extract text from an uploaded file using a cascading strategy.

    Returns (extracted_text, used_google_vision, ocr_mode).
    """
    content = await file.read()
    await file.seek(0)

    filename = (file.filename or "").lower()
    is_pdf = filename.endswith(".pdf") or file.content_type == "application/pdf"

    # --- Strategy 1: Google Cloud Vision ---
    if _vision_available():
        logger.info("Attempting Google Cloud Vision OCR...")
        text = await _google_vision_extract(content)
        if text:
            logger.info("Google Vision extracted %d chars", len(text))
            return text, True, "google_vision"
        logger.warning("Google Vision returned no text")

    # --- Strategy 2: Local PDF text extraction ---
    if is_pdf:
        logger.info("Attempting local PDF text extraction (PyPDF2)...")
        text = _extract_pdf_text(content)
        if text:
            logger.info("PyPDF2 extracted %d chars from PDF", len(text))
            return text, False, "pdf_text_extraction"
        logger.warning("PyPDF2 could not extract text (scanned PDF or image-only?)")

    # --- Strategy 3: Fallback mock text ---
    logger.warning(
        "No text extraction succeeded for '%s' — returning mock OCR text. "
        "This means the result will NOT reflect the actual document content.",
        file.filename,
    )
    return MOCK_OCR_TEXT.strip(), False, "fallback_mock"


def get_mock_text() -> str:
    """Return the mock OCR text. Used explicitly by /api/analyze/mock."""
    return MOCK_OCR_TEXT.strip()
