"""
Phase 8 — Screenshot Monitor Service (v2 - High Accuracy)
==========================================================
Changes from v1:
  - STRICT Aadhaar: requires separator (space/dash) between groups
  - STRICT credit card: 4-4-4-4 format with separators only
  - Phone: only exactly 10 digits starting 6-9, not inside longer number
  - Dedup: a number matching Aadhaar won't also flag as phone
  - Source='screen' in output so popup title says "Screen" not "File"
  - Alert threshold raised to 20 (reduce noise)
  - Face detection: minNeighbors=5 (stricter, less false positives)
"""
from __future__ import annotations
import os, re
from datetime import datetime
import cv2
import numpy as np

# ── OCR (optional graceful fallback) ─────────────────────────────────────────
try:
    import pytesseract
    from PIL import Image
    import io as _io
    _OCR_AVAILABLE = True
except ImportError:
    _OCR_AVAILABLE = False

# ── HIGH-ACCURACY Regex patterns ──────────────────────────────────────────────
_PATTERNS = {
    # Aadhaar: MUST have space or dash between groups
    # Requires Aadhaar-like context: preceded by 'aadhaar', 'uid', 'aadhar', colon, or newline
    # OR: the number doesn't start with 4xxx (Visa) or 5xxx (Mastercard)
    # Negative lookahead: NOT followed by another digit group (would be credit card)
    "aadhaar": re.compile(
        r"(?i)(?:aadhaar|aadhar|uid|\:)\s*(?:\d{4}[\s\-]){2}\d{4}|"
        r"(?<!\d)(?:[0-36-9]\d{3})[\s\-]\d{4}[\s\-]\d{4}(?![\s\-]\d)(?!\d)"
    ),

    # PAN: strict 5 upper letters + 4 digits + 1 upper letter
    "pan": re.compile(r"(?<![A-Z])[A-Z]{5}\d{4}[A-Z](?![A-Z])"),

    # Credit card: ONLY 4-4-4-4 groups with space/dash separators
    "credit_card": re.compile(r"(?<!\d)\d{4}[\s\-]\d{4}[\s\-]\d{4}[\s\-]\d{4}(?!\d)"),

    # Email: standard accurate pattern
    "email": re.compile(r"(?<!\w)[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}(?!\w)"),

    # Phone: exactly 10 digits, starts 6-9, not adjacent to more digits
    "phone": re.compile(r"(?<!\d)[6-9]\d{9}(?!\d)"),

    # Password: only when a label precedes it
    "password": re.compile(r"(?i)(?:password|passwd|pwd|pass)\s*[=:\-]\s*\S{4,}"),

    # OTP: explicit label + 4-8 digit code
    "otp": re.compile(r"(?i)\b(?:otp|one[\s\-]time[\s\-](?:password|pin|code)|verification\s+code)\b.{0,30}\b\d{4,8}\b"),

    # DOB: strict dd/mm/yyyy only, years 1900-2009 (actual date of birth years)
    # Excludes 2010-2099 to avoid flagging current/future dates as DOB
    "dob": re.compile(r"(?<!\d)(?:0[1-9]|[12]\d|3[01])[/\-](?:0[1-9]|1[0-2])[/\-](?:19\d{2}|200\d)(?!\d)"),
}

_WEIGHTS = {
    "aadhaar":       50,
    "pan":           45,
    "credit_card":   40,
    "password":      40,
    "otp":           35,
    "dob":           25,
    "email":         18,
    "phone":         15,
    "face_detected": 20,
}

# Raised from 10 → 20: only alert when score is meaningful
RISK_THRESHOLD = 20
from backend.config import SCREENSHOT_DIR

# Load Haar cascade once
try:
    _FACE_CASCADE = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )
except Exception:
    _FACE_CASCADE = None


def _run_ocr(image_bytes: bytes) -> str:
    """Run Tesseract OCR. Upscales small images for better accuracy."""
    if not _OCR_AVAILABLE:
        return ""
    try:
        img = Image.open(_io.BytesIO(image_bytes))
        w, h = img.size
        if w < 1200:
            scale = max(2, 1200 // w)
            img = img.resize((w * scale, h * scale), Image.LANCZOS)
        return pytesseract.image_to_string(img, config="--psm 6 --oem 1")
    except Exception:
        return ""


def _detect_faces(img_bgr: np.ndarray) -> int:
    if _FACE_CASCADE is None:
        return 0
    gray  = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    faces = _FACE_CASCADE.detectMultiScale(
        gray, scaleFactor=1.1, minNeighbors=5, minSize=(40, 40)
    )
    return len(faces) if len(faces) > 0 else 0


def _dedup_findings(findings: list) -> list:
    """
    Remove overlapping matches:
    - Phone whose digits are inside an Aadhaar we found → drop phone
    - Aadhaar whose 12 digits are a prefix of a credit card we found → drop Aadhaar
    - Exact duplicate type+value pairs → drop duplicate
    """
    # Collect credit card digit strings
    cc_digits = set()
    for f in findings:
        if f["type"] == "credit_card":
            cc_digits.add(re.sub(r"\D", "", f["value"]))

    # Collect Aadhaar digit strings
    aadhaar_digits = set()
    for f in findings:
        if f["type"] == "aadhaar":
            d = re.sub(r"\D", "", f["value"])
            # Only collect if NOT a prefix of a credit card
            if not any(d == cc[:12] for cc in cc_digits):
                aadhaar_digits.add(d)

    seen = set()
    result = []
    for f in findings:
        key = (f["type"], f["value"])
        if key in seen:
            continue
        digits = re.sub(r"\D", "", f["value"])
        # Drop phone if its 10 digits appear inside an Aadhaar
        if f["type"] == "phone":
            if any(digits in a for a in aadhaar_digits):
                continue
        # Drop Aadhaar if its 12 digits are the first 12 of a credit card
        if f["type"] == "aadhaar":
            if any(digits == cc[:12] for cc in cc_digits):
                continue
        seen.add(key)
        result.append(f)
    return result


def analyze_screenshot(image_bytes: bytes, ocr_text: str = "") -> dict:
    """
    Analyze a screenshot for PII.
    source='screen' differentiates from Background Agent (source='file').
    """
    findings   = []
    score      = 0.0
    face_count = 0
    ocr_used   = False

    # 1. Auto-OCR if no text provided
    if not ocr_text.strip():
        ocr_text = _run_ocr(image_bytes)
        ocr_used = True

    # 2. Strict regex scan
    for ptype, pattern in _PATTERNS.items():
        matches = pattern.findall(ocr_text)
        for m in matches:
            raw = str(m).strip()
            if not raw:
                continue
            # Clean context prefix: strip leading word chars / punctuation (for Aadhaar context variant)
            # e.g. "aadhaar: 1234 5678 9012" → "1234 5678 9012"
            cleaned = re.sub(r"^(?:\w+\s*[:=\-]\s*)", "", raw).strip()
            val = cleaned if cleaned else raw
            w = _WEIGHTS.get(ptype, 5)
            findings.append({"type": ptype, "value": val[:80], "weight": w, "source": "screen"})


    # 3. Dedup (remove phone that overlaps with Aadhaar)
    findings = _dedup_findings(findings)
    score    = sum(f["weight"] for f in findings)

    # 4. Face detection
    try:
        arr = np.frombuffer(image_bytes, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is not None:
            face_count = _detect_faces(img)
            if face_count > 0:
                w = _WEIGHTS["face_detected"]
                findings.append({"type": "face_detected", "value": f"{face_count} face(s) detected", "weight": w, "source": "screen"})
                score += w
    except Exception:
        face_count = 0

    score = min(score, 100.0)

    if   score >= 75: risk = "CRITICAL"
    elif score >= 45: risk = "HIGH"
    elif score >= 20: risk = "MEDIUM"
    elif score >= 10: risk = "LOW"
    else:             risk = "SAFE"

    return {
        "score":         round(score, 1),
        "risk_level":    risk,
        "findings":      findings,
        "face_count":    face_count,
        "should_alert":  score >= RISK_THRESHOLD,
        "finding_types": list({f["type"] for f in findings}),
        "ocr_text_len":  len(ocr_text),
        "ocr_auto_ran":  ocr_used,
        "source":        "screen",
    }


def save_screenshot(image_bytes: bytes, session_id: int) -> str:
    fname = f"screen_{session_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S%f')}.png"
    path  = os.path.join(SCREENSHOT_DIR, fname)
    with open(path, "wb") as f:
        f.write(image_bytes)
    return path
