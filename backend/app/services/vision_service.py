"""
vision_service.py -- Google Cloud Vision OCR with smart fallback.

Public API (consumed by app/routes/analyze.py):
    extract_text_from_upload(file: UploadFile) -> tuple[str, bool, OcrMode]
        Returns (extracted_text, used_google_vision, ocr_mode)

Credential detection:
    GOOGLE_APPLICATION_CREDENTIALS must be set AND point to a file that
    actually exists on disk. If the env var is missing or is a placeholder,
    Vision is marked unavailable and the caller is warned clearly.

Cascade strategy (per upload):
    PDFs:   PyPDF2 first; Vision as fallback for scanned/image-only PDFs.
    Images: Vision when credentials are valid; 422 HTTPException otherwise.
            Mock text is NEVER returned for real image uploads.
"""

from __future__ import annotations

import io
import logging
import os
from pathlib import Path
from typing import Literal, Tuple

from fastapi import HTTPException, UploadFile

logger = logging.getLogger("clearconsent.vision")

OcrMode = Literal[
    "google_vision",
    "pdf_text_extraction",
    "unsupported_image_no_vision",
]

# ---------------------------------------------------------------------------
# Credential helpers
# ---------------------------------------------------------------------------

_PLACEHOLDERS = ("/path/to", "C:\\absolute\\", "your-", "/abs/")


def _get_credentials_path() -> str | None:
    creds = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
    if not creds:
        return None
    if any(creds.startswith(p) for p in _PLACEHOLDERS):
        return None
    return creds


def _vision_available() -> bool:
    """
    Return True only when GOOGLE_APPLICATION_CREDENTIALS is set (non-placeholder)
    AND the file exists on disk.
    """
    creds = _get_credentials_path()
    if not creds:
        return False
    exists = Path(creds).is_file()
    if not exists:
        logger.warning(
            "GOOGLE_APPLICATION_CREDENTIALS is set to '%s' but the file does not exist. "
            "Vision OCR will be unavailable.",
            creds,
        )
    return exists


# ---------------------------------------------------------------------------
# Google Cloud Vision OCR
# ---------------------------------------------------------------------------

async def _vision_ocr(content: bytes, filename: str) -> str | None:
    """
    Call Vision API with raw file bytes.
    Returns extracted text or None on failure / empty result.
    """
    try:
        from google.cloud import vision  # type: ignore

        client = vision.ImageAnnotatorClient()
        image = vision.Image(content=content)
        response = client.document_text_detection(image=image)

        if response.error.message:
            raise RuntimeError(f"Vision API error: {response.error.message}")

        text = response.full_text_annotation.text
        if text and text.strip():
            logger.info(
                "Google Vision extracted %d chars from '%s'", len(text), filename
            )
            return text.strip()

        logger.warning("Google Vision returned empty text for '%s'", filename)
        return None

    except Exception as exc:
        logger.error("Vision API error: %s - returning None", exc)
        return None


# ---------------------------------------------------------------------------
# PDF text extraction
# ---------------------------------------------------------------------------

def _extract_pdf_text(content: bytes) -> str | None:
    """Extract text from a PDF using PyPDF2. Returns text or None."""
    try:
        from PyPDF2 import PdfReader

        reader = PdfReader(io.BytesIO(content))
        pages_text = [
            page.extract_text().strip()
            for page in reader.pages
            if page.extract_text()
        ]
        full_text = "\n\n".join(pages_text).strip()
        return full_text if len(full_text) > 20 else None

    except Exception as exc:
        logger.warning("PyPDF2 extraction failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Public entry point — called by app/routes/analyze.py
# ---------------------------------------------------------------------------

async def extract_text_from_upload(
    file: UploadFile,
) -> Tuple[str, bool, OcrMode]:
    """
    Extract text from an uploaded file.

    Returns:
        (extracted_text: str, used_google_vision: bool, ocr_mode: OcrMode)

    Raises:
        HTTPException 422 -- when text cannot be extracted and no mock is appropriate.
    """
    content = await file.read()
    await file.seek(0)

    filename = (file.filename or "").lower()
    is_pdf = filename.endswith(".pdf") or file.content_type == "application/pdf"
    is_image = (
        any(
            filename.endswith(ext)
            for ext in (".jpg", ".jpeg", ".png", ".heic", ".heif", ".tiff", ".bmp", ".webp")
        )
        or (file.content_type or "").startswith("image/")
    )

    vision_ready = _vision_available()

    # ------------------------------------------------------------------
    # PDF path
    # ------------------------------------------------------------------
    if is_pdf:
        logger.info("Attempting local PDF text extraction (PyPDF2)...")
        text = _extract_pdf_text(content)
        if text:
            logger.info("PyPDF2 extracted %d chars from PDF", len(text))
            return text, False, "pdf_text_extraction"

        logger.warning(
            "PyPDF2 could not extract text from '%s' (scanned/image-only PDF?). "
            "Trying Vision if available.",
            file.filename,
        )
        if vision_ready:
            logger.info("Falling back to Google Vision for scanned PDF...")
            text = await _vision_ocr(content, file.filename or "document.pdf")
            if text:
                return text, True, "google_vision"

        raise HTTPException(
            status_code=422,
            detail=(
                "Could not extract text from the uploaded PDF. "
                "The file may be scanned or image-only. "
                "Enable Google Cloud Vision in the backend to process scanned PDFs."
            ),
        )

    # ------------------------------------------------------------------
    # Image path
    # ------------------------------------------------------------------
    if is_image:
        if vision_ready:
            logger.info(
                "Attempting Google Cloud Vision OCR for image '%s'...", file.filename
            )
            text = await _vision_ocr(content, file.filename or "image")
            if text:
                return text, True, "google_vision"
            raise HTTPException(
                status_code=422,
                detail=(
                    "Google Vision could not extract any text from the uploaded image. "
                    "Please ensure the image is clear and contains readable text."
                ),
            )

        logger.warning(
            "Image file '%s' uploaded but Google Cloud Vision is not configured. "
            "Set GOOGLE_APPLICATION_CREDENTIALS in backend/.env to enable image OCR.",
            file.filename,
        )
        raise HTTPException(
            status_code=422,
            detail=(
                "Image OCR is not available: Google Cloud Vision credentials are not configured. "
                "Please upload a PDF, or contact the administrator to enable image OCR."
            ),
        )

    # ------------------------------------------------------------------
    # Unknown file type
    # ------------------------------------------------------------------
    raise HTTPException(
        status_code=400,
        detail=f"Unsupported file type: '{file.filename}'. Please upload a PDF, JPG, or PNG.",
    )
