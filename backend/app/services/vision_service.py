"""
vision_service.py — Google Cloud Vision OCR with mock fallback.

If GOOGLE_APPLICATION_CREDENTIALS (or GOOGLE_CLOUD_VISION_KEY) is set, uses
the real Vision API.  Otherwise returns realistic mock OCR text so the demo
always works.
"""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import UploadFile

logger = logging.getLogger("clearconsent.vision")

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
# Real Vision OCR
# ---------------------------------------------------------------------------


async def _real_extract(file: UploadFile) -> str:
    """Use Google Cloud Vision API to extract text from the uploaded file."""
    try:
        from google.cloud import vision  # type: ignore

        client = vision.ImageAnnotatorClient()

        content = await file.read()
        await file.seek(0)

        image = vision.Image(content=content)
        response = client.text_detection(image=image)

        if response.error.message:
            raise RuntimeError(response.error.message)

        texts = response.text_annotations
        if texts:
            return texts[0].description
        return ""
    except Exception as exc:
        logger.error("Vision API error: %s — returning None", exc)
        return None


# ---------------------------------------------------------------------------
# Mock OCR text — crafted to exercise every must-catch demo category
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


def _mock_text() -> str:
    return MOCK_OCR_TEXT.strip()


import io
from typing import Literal

# Type alias for OCR mode reporting
OcrMode = Literal["google_vision", "pdf_text_extraction", "fallback_mock"]

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

async def extract_text_from_upload(file: UploadFile) -> tuple[str, bool, OcrMode]:
    """
    Extract text from an uploaded file using a cascading strategy.
    Returns (extracted_text, used_google_vision, ocr_mode).
    """
    content = await file.read()
    await file.seek(0)

    filename = (file.filename or "").lower()
    is_pdf = filename.endswith(".pdf") or file.content_type == "application/pdf"

    if _vision_available():
        logger.info("Attempting Google Cloud Vision OCR...")
        text = await _real_extract(file)
        if text:
            return text, True, "google_vision"
        logger.warning("Vision returned empty text; falling back")

    if is_pdf:
        logger.info("Attempting local PDF text extraction (PyPDF2)...")
        text = _extract_pdf_text(content)
        if text:
            logger.info("PyPDF2 extracted %d chars from PDF", len(text))
            return text, False, "pdf_text_extraction"
        logger.warning("PyPDF2 could not extract text (scanned PDF or image-only?)")

    logger.warning("No text extraction succeeded for '%s' — returning mock OCR text.", file.filename)
    return _mock_text(), False, "fallback_mock"
