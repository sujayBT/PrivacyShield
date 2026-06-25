"""
Phase 6 — Vision Detection Engine
===================================
Uses OpenCV + heuristic document classification to detect:

  1. Faces         — OpenCV Haar Cascade (no model download)
  2. Document Type — heuristic rules on OCR text + image structure
  3. QR / Barcode  — OpenCV contour detection proxy
  4. Signatures    — ink-stroke density heuristic on thresholded image

Each result is returned as a structured dict so the frontend
can render VisionBadge components.

Gracefully returns empty results if the file is not an image.
"""

from __future__ import annotations
import logging
import os
import re
from pathlib import Path

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# ─── Load Haar Cascade (singleton) ───────────────────────────────────────────

_face_cascade: cv2.CascadeClassifier | None = None

def _get_face_cascade() -> cv2.CascadeClassifier:
    global _face_cascade
    if _face_cascade is not None:
        return _face_cascade
    path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    _face_cascade = cv2.CascadeClassifier(path)
    if _face_cascade.empty():
        logger.warning("Haar cascade failed to load from %s", path)
    else:
        logger.info("Haar cascade loaded from %s", path)
    return _face_cascade


# ─── Image loader helper ─────────────────────────────────────────────────────

def _load_image(file_path: str):
    """Load image as BGR numpy array. Returns None for PDFs or missing files."""
    ext = Path(file_path).suffix.lower()
    if ext not in {".png", ".jpg", ".jpeg", ".bmp", ".webp"}:
        return None
    if not os.path.exists(file_path):
        return None
    img = cv2.imread(file_path)
    return img  # may be None if corrupt


# ─── 1. Face Detection ────────────────────────────────────────────────────────

def detect_faces(img_bgr, is_id_doc: bool = False) -> dict:
    """
    Detect human faces using Haar Cascade.
    Strict settings to eliminate false positives on:
      - handwritten notes / scanned papers
      - WhatsApp screenshots with text
      - documents with lines and curves
    Returns:
      { found: bool, count: int, confidence: float,
        bounding_boxes: [[x,y,w,h], ...] }
    """
    if img_bgr is None:
        return {"found": False, "count": 0, "confidence": 0.0, "bounding_boxes": []}

    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    cascade = _get_face_cascade()

    if cascade.empty():
        return {"found": False, "count": 0, "confidence": 0.0, "bounding_boxes": []}

    # ── Pre-check: skip face detection for handwriting/document images ─────────
    # Handwritten notes have high contrast thin lines → many dark pixels in edges
    # Real photos have smooth gradients
    h_img, w_img = gray.shape
    edges = cv2.Canny(gray, 50, 150)
    edge_density = edges.sum() / (255.0 * h_img * w_img)
    # If more than 12% of pixels are edges → document/handwriting, not a photo with faces
    # Bypassed if we already know it is an ID document (Aadhaar, PAN, Passport, etc.)
    if edge_density > 0.12 and not is_id_doc:
        return {"found": False, "count": 0, "confidence": 0.0, "bounding_boxes": []}

    # Also reject if image looks like a dark-on-light scan (low std deviation → plain page)
    std_dev = float(gray.std())
    if std_dev < 18:
        return {"found": False, "count": 0, "confidence": 0.0, "bounding_boxes": []}

    # ── Strict Haar cascade settings ──────────────────────────────────────────
    # minNeighbors=12: requires many overlapping detections → far fewer false positives
    # minSize=80: only detect real human-sized faces (not text/pattern noise)
    faces = cascade.detectMultiScale(
        gray,
        scaleFactor=1.1,
        minNeighbors=12,
        minSize=(80, 80),
        flags=cv2.CASCADE_SCALE_IMAGE,
    )

    if len(faces) == 0:
        return {"found": False, "count": 0, "confidence": 0.0, "bounding_boxes": []}

    # Additional post-filter: reject boxes that are too small relative to image
    img_area = h_img * w_img
    valid_boxes = [
        [int(x), int(y), int(w), int(h)]
        for x, y, w, h in faces
        if (w * h) / img_area > 0.005  # face must be at least 0.5% of image
    ]

    if not valid_boxes:
        return {"found": False, "count": 0, "confidence": 0.0, "bounding_boxes": []}

    conf = min(0.65 + len(valid_boxes) * 0.12, 0.97)
    return {
        "found":         True,
        "count":         len(valid_boxes),
        "confidence":    round(conf, 2),
        "bounding_boxes": valid_boxes,
    }


# ─── 2. Document Type Classification ─────────────────────────────────────────

# Keyword rules — match against OCR text
_DOC_RULES: list[tuple[str, list[str], float]] = [
    # (doc_type, keywords, base_confidence)
    ("aadhaar_card",    ["aadhaar", "uid", "unique identification", "enrolment", "dise"], 0.88),
    ("pan_card",        ["permanent account number", "income tax department", "income tax"], 0.87),
    ("passport",        ["republic of india", "passport", "nationality", "place of birth", "date of issue"], 0.86),
    ("driving_license", ["driving licence", "driving license", "transport", "vehicle", "dl no"], 0.85),
    ("bank_statement",  ["account number", "ifsc", "statement of account", "balance", "transaction", "debit", "credit", "upi"], 0.82),
    ("medical_record",  ["patient", "diagnosis", "prescription", "hospital", "doctor", "medication", "dosage", "clinical"], 0.80),
    ("tax_document",    ["income tax", "gst", "tds", "form 16", "pan", "assessment year", "tax return"], 0.79),
    ("insurance",       ["policy", "premium", "insured", "sum assured", "nominee", "insurance"], 0.78),
    ("screenshot",      ["notification", "battery", "signal", "wifi", "pm", "am", "home", "settings"], 0.62),
]

def classify_document(ocr_text: str, img_bgr=None) -> dict:
    """
    Classify document type from OCR text + optional image structure analysis.
    Returns:
      { doc_type: str, confidence: float, is_id_document: bool }
    """
    if not ocr_text:
        return {"doc_type": "unknown", "confidence": 0.0, "is_id_document": False}

    text_lower = ocr_text.lower()
    best_type = "unknown"
    best_conf = 0.0

    for doc_type, keywords, base_conf in _DOC_RULES:
        hits = sum(1 for kw in keywords if re.search(r'\b' + re.escape(kw) + r'\b', text_lower))
        if hits == 0:
            continue
        # Scale confidence by fraction of keywords matched
        conf = base_conf * (0.6 + 0.4 * min(hits / max(len(keywords), 1), 1.0))
        if conf > best_conf:
            best_conf = conf
            best_type = doc_type

    # Image structure boost: ID documents tend to be small fixed-size rectangles
    if img_bgr is not None and best_type in ("aadhaar_card", "pan_card", "passport", "driving_license"):
        h, w = img_bgr.shape[:2]
        aspect = w / max(h, 1)
        # Credit-card aspect ~1.586 — if close, boost confidence
        if 1.3 <= aspect <= 1.9:
            best_conf = min(best_conf + 0.08, 0.97)

    id_doc_types = {"aadhaar_card", "pan_card", "passport", "driving_license"}
    return {
        "doc_type": best_type,
        "confidence": round(best_conf, 2),
        "is_id_document": best_type in id_doc_types,
    }


# ─── 3. Signature Detection ───────────────────────────────────────────────────

def detect_signature(img_bgr) -> dict:
    """
    Heuristic: a signature region has dark ink strokes on white background,
    concentrated in a small area. Uses Otsu thresholding + contour analysis.
    Returns: { found: bool, confidence: float }
    """
    if img_bgr is None:
        return {"found": False, "confidence": 0.0}

    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    # Invert so ink = white, paper = black
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    # Find contours
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # Signature heuristic: many small thin contours (pen strokes)
    h, w = img_bgr.shape[:2]
    total_px = h * w
    ink_ratio = cv2.countNonZero(thresh) / max(total_px, 1)

    # Look for elongated thin contours typical of handwriting
    pen_strokes = 0
    for c in contours:
        area = cv2.contourArea(c)
        if area < 10:
            continue
        x, y, cw, ch = cv2.boundingRect(c)
        aspect = max(cw, ch) / max(min(cw, ch), 1)
        if aspect > 2.5 and area < total_px * 0.02:
            pen_strokes += 1

    # Signature present if: moderate ink coverage + many pen strokes
    found = 0.005 < ink_ratio < 0.18 and pen_strokes >= 5
    confidence = round(min(0.4 + pen_strokes * 0.04, 0.85), 2) if found else 0.0

    return {"found": found, "confidence": confidence}


# ─── 4. QR / Barcode Presence ────────────────────────────────────────────────

def detect_qr_barcode(img_bgr) -> dict:
    """
    Detect QR codes or barcodes.
    STRICT: Only reports a finding when actual data is decoded from the code.
    Logos, patterns, and graphic regions are NOT reported as barcodes.
    """
    if img_bgr is None:
        return {"found": False, "count": 0, "data": []}

    h, w = img_bgr.shape[:2]
    # Skip on small images (logos, icons, thumbnails under 200x200)
    if w < 200 or h < 200:
        return {"found": False, "count": 0, "data": []}

    try:
        detector = cv2.QRCodeDetector()
        data, points, _ = detector.detectAndDecode(img_bgr)
        # STRICT: only fire if actual text/URL data was decoded from the QR code
        if points is not None and data and len(data.strip()) > 3:
            return {"found": True, "count": 1, "data": [data.strip()[:120]]}
    except Exception:
        pass

    return {"found": False, "count": 0, "data": []}


# ─── 5. Master Vision Analysis ───────────────────────────────────────────────

def run_vision_analysis(file_path: str, ocr_text: str = "") -> dict:
    """
    Run full vision pipeline on an image file.
    Returns structured result consumed by scan_router and frontend.

    Result schema:
    {
        "available": bool,       # False if file is not an image
        "faces": {...},
        "document": {...},
        "signature": {...},
        "qr_barcode": {...},
        "findings": [           # Flat list for integration with PII findings
            { "type": str, "value": str, "method": "vision",
              "confidence": float, "weight": int }
        ]
    }
    """
    img = _load_image(file_path)

    if img is None:
        return {
            "available": False,
            "faces": {"found": False, "count": 0},
            "document": {"doc_type": "unknown", "confidence": 0.0, "is_id_document": False},
            "signature": {"found": False, "confidence": 0.0},
            "qr_barcode": {"found": False, "count": 0},
            "findings": [],
        }

    doc_result   = classify_document(ocr_text, img)
    is_id_doc    = doc_result.get("is_id_document", False)
    face_result  = detect_faces(img, is_id_doc=is_id_doc)
    sig_result   = detect_signature(img)
    qr_result    = detect_qr_barcode(img)

    # Build flat findings list
    findings: list[dict] = []

    if face_result["found"]:
        findings.append({
            "type":       "face_detected",
            "value":      f"{face_result['count']} face(s) detected in image",
            "method":     "vision",
            "confidence": face_result["confidence"],
            "weight":     22,
        })

    if doc_result["is_id_document"] and doc_result["confidence"] >= 0.6:
        findings.append({
            "type":       "id_card_visible",
            "value":      f"ID document detected: {doc_result['doc_type'].replace('_', ' ').title()}",
            "method":     "vision",
            "confidence": doc_result["confidence"],
            "weight":     30,
        })

    if sig_result["found"]:
        findings.append({
            "type":       "signature_visible",
            "value":      "Handwritten signature detected",
            "method":     "vision",
            "confidence": sig_result["confidence"],
            "weight":     12,
        })

    if qr_result["found"] and qr_result["data"]:
        # Only add finding when real data was decoded (not a vague guess)
        decoded_data = qr_result["data"][0]
        conf = min(0.85 + len(decoded_data) * 0.001, 0.97)  # longer data = more confident
        findings.append({
            "type":       "qr_barcode",
            "value":      decoded_data,
            "method":     "vision",
            "confidence": round(conf, 2),
            "weight":     15,
        })

    return {
        "available":  True,
        "faces":      face_result,
        "document":   doc_result,
        "signature":  sig_result,
        "qr_barcode": qr_result,
        "findings":   findings,
    }


# ─── Score contribution from vision findings ─────────────────────────────────

def score_vision_findings(vision_findings: list[dict]) -> float:
    """
    Score points from vision-detected findings (1.2× multiplier).
    Uses same diminishing-returns logic as detection.py.
    """
    total = 0.0
    for f in vision_findings:
        total += f.get("weight", 10) * f.get("confidence", 0.7) * 1.2
    return round(min(total, 60.0), 1)   # cap at 60 pts from vision


# ─── Engine info ─────────────────────────────────────────────────────────────

def get_vision_engine_info() -> dict:
    return {
        "engine":     "OpenCV 4 + Haar Cascade",
        "version":    cv2.__version__,
        "available":  True,
        "detectors":  ["face", "document_type", "id_card", "signature", "qr_barcode"],
    }
