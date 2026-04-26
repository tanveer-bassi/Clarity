"""
test_vision_ocr.py -- Sanity check for Google Cloud Vision OCR.

Usage:
  # Print credential status only:
  python test_vision_ocr.py

  # Also send a test image to Vision API:
  python test_vision_ocr.py path\\to\\image.png
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sep(label: str = "") -> None:
    if label:
        print(f"\n--- {label} ---")
    else:
        print("-" * 50)


def _ok(msg: str) -> None:
    print(f"  [OK]   {msg}")


def _fail(msg: str) -> None:
    print(f"  [FAIL] {msg}")


def _warn(msg: str) -> None:
    print(f"  [WARN] {msg}")


def _info(msg: str) -> None:
    print(f"  [INFO] {msg}")


# ---------------------------------------------------------------------------
# Credential checks
# ---------------------------------------------------------------------------

def check_credentials() -> bool:
    """Print a full credential status report. Returns True if Vision is ready."""
    _sep("Google Cloud Vision -- Credential Status")

    creds = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")

    # 1. Is the env var set?
    if not creds:
        _fail("GOOGLE_APPLICATION_CREDENTIALS is not set.")
        _info("Add it to backend/.env, e.g.:")
        _info("  GOOGLE_APPLICATION_CREDENTIALS=C:\\...\\backend\\credentials\\clarity-vision-key.json")
        return False
    _ok(f"GOOGLE_APPLICATION_CREDENTIALS is set.")

    # 2. Is it a placeholder?
    placeholders = ("/path/to", "C:\\absolute\\", "your-", "/abs/")
    if any(creds.startswith(p) for p in placeholders):
        _fail(f"Value looks like a placeholder: '{creds}'")
        _info("Replace the placeholder in backend/.env with the real absolute path.")
        return False
    _ok(f"Value does not look like a placeholder.")

    # 3. Does the file exist?
    path = Path(creds)
    _info(f"Credential path: {creds}")
    if not path.exists():
        _fail(f"File does not exist at that path.")
        return False
    if not path.is_file():
        _fail(f"Path exists but is not a file.")
        return False
    _ok(f"File exists ({path.stat().st_size:,} bytes).")

    # 4. Can we import the Vision client?
    _sep("Google Cloud Vision -- Import Check")
    try:
        from google.cloud import vision  # noqa: F401
        _ok("google-cloud-vision package imported successfully.")
    except ImportError as exc:
        _fail(f"Cannot import google-cloud-vision: {exc}")
        _info("Run: pip install google-cloud-vision")
        return False

    # 5. Can we instantiate the client?
    try:
        from google.cloud import vision as v
        client = v.ImageAnnotatorClient()
        _ok("ImageAnnotatorClient() instantiated successfully.")
    except Exception as exc:
        _fail(f"ImageAnnotatorClient() failed: {exc}")
        return False

    _sep()
    _ok("Google Vision appears AVAILABLE. Image OCR is enabled.")
    return True


# ---------------------------------------------------------------------------
# Live image test
# ---------------------------------------------------------------------------

def test_image(image_path: str) -> None:
    _sep(f"Live API Test -- {image_path}")

    path = Path(image_path)
    if not path.is_file():
        _fail(f"Image file not found: '{image_path}'")
        return

    _info(f"File size: {path.stat().st_size:,} bytes")

    try:
        from google.cloud import vision

        client = vision.ImageAnnotatorClient()
        content = path.read_bytes()
        image = vision.Image(content=content)

        _info("Sending to Vision API (document_text_detection)...")
        response = client.document_text_detection(image=image)

        if response.error.message:
            _fail(f"Vision API error: {response.error.message}")
            return

        text = response.full_text_annotation.text
        if text and text.strip():
            preview = text.strip()[:300].replace("\n", " | ")
            _ok(f"OCR succeeded! Extracted {len(text.strip())} characters.")
            _info(f"Preview: \"{preview}\"")
        else:
            _warn("Vision API responded but extracted no text.")
            _info("Check that the image is clear and contains readable text.")

    except Exception as exc:
        _fail(f"Vision API call failed: {exc}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    # Load .env from the backend directory
    try:
        from dotenv import load_dotenv
        env_path = Path(__file__).parent / ".env"
        if env_path.is_file():
            load_dotenv(env_path)
            _info(f"Loaded environment from: {env_path}")
        else:
            _warn(f"No .env found at {env_path} -- using system environment only.")
    except ImportError:
        _warn("python-dotenv not available -- using system environment only.")

    print()

    creds_ok = check_credentials()

    if len(sys.argv) > 1:
        if creds_ok:
            test_image(sys.argv[1])
        else:
            _warn("Skipping live API test because credentials are not valid.")
    else:
        _sep()
        _info("No image path provided. To test a live image upload, run:")
        _info("  python test_vision_ocr.py path\\to\\image.png")

    print()


if __name__ == "__main__":
    main()
