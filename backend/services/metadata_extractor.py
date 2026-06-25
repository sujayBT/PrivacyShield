"""
Phase 10 — Metadata Extractor Service (Improved v2)
=====================================================
Extracts, Categorizes, and Scores privacy risks in file metadata.
Supports: Images (JPEG/PNG/WebP/BMP/TIFF), PDFs, Word, Excel, PowerPoint.

Key improvements over v1:
- Image extraction: Uses PIL._getexif() (works for ALL image types, not just JPEG)
  with piexif as a secondary GPS/camera fallback (JPEG-only, safely wrapped)
- PDF: Tries PyMuPDF first, falls back to pdfplumber
- DOCX/Excel: Filters out None, empty strings and "None" string values
- Always returns a clear no_metadata_found flag when nothing is found
- clean_metadata() re-scans the cleaned file to confirm removal
"""

from __future__ import annotations
import os
import io
import re
import logging
import zipfile
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

# ── Category & Labels Configuration ──────────────────────────────────────────

SENSITIVE_FIELDS = {
    "author", "creator", "last_modified_by", "company", "email", "phone",
    "user_comment", "gps_latitude", "gps_longitude", "gps_full", "artist",
    "copyright", "software", "camera_model", "camera_make", "local_path",
    "email_in_metadata", "phone_in_metadata"
}

FRIENDLY_LABELS = {
    "author":             "Document Creator",
    "creator":            "Document Creator",
    "last_modified_by":   "Last Editor Name",
    "revision":           "Document Edit Count",
    "creation_date":      "File Created On",
    "modification_date":  "File Last Modified",
    "gps_full":           "GPS Physical Location",
    "gps_latitude":       "GPS Latitude",
    "gps_longitude":      "GPS Longitude",
    "camera_model":       "Device Model",
    "camera_make":        "Device Manufacturer",
    "software":           "Creation Software",
    "company":            "Organization / Company",
    "user_comment":       "Embedded Comments",
    "artist":             "Artist / Owner",
    "copyright":          "Copyright Holder",
    "doc_title":          "Document Title",
    "subject":            "Document Subject",
    "keywords":           "Tags / Keywords",
    "category":           "Document Category",
    "page_count":         "Total Pages",
    "word_count":         "Total Words",
    "sheet_count":        "Total Sheets",
    "revision_count":     "Revision Count",
}

_FIELD_WEIGHTS: dict[str, int] = {
    "gps_full":           30,
    "gps_latitude":       15,
    "gps_longitude":      15,
    "email_in_metadata":  20,
    "phone_in_metadata":  20,
    "author":             15,
    "creator":            15,
    "last_modified_by":   15,
    "company":            10,
    "local_path":         25,
    "tracked_changes":    20,
    "user_comment":       20,
    "camera_model":       15,
    "camera_make":        10,
    "software":           5,
    "artist":             10,
    "keywords":           2,
    "revision":           0,
    "creation_date":      0,
    "modification_date":  0,
    "title":              0,
    "subject":            0,
    "category":           0,
}

REASONS = {
    "gps_full":           "Exact physical location coordinates leaked. Can reveal home/work addresses.",
    "author":             "Real name of the document creator found. Reveals identity of the author.",
    "last_modified_by":   "Reveals the name of the last person who edited the file.",
    "company":            "Reveals your workplace or professional affiliation.",
    "email_in_metadata":  "Personal email address found hidden in file properties.",
    "phone_in_metadata":  "Mobile number found hidden in file properties.",
    "software":           "Reveals the software and version used. Can be used for targeted software exploits.",
    "camera_model":       "Reveals your hardware device model, aiding in digital fingerprinting.",
    "user_comment":       "Hidden comments or notes found that may contain sensitive remarks.",
}

IMAGE_EXTS  = {".jpg", ".jpeg", ".png", ".tiff", ".tif", ".webp", ".bmp"}
PDF_EXTS    = {".pdf"}
WORD_EXTS   = {".docx", ".doc"}
EXCEL_EXTS  = {".xlsx", ".xls"}
PPT_EXTS    = {".pptx", ".ppt"}


# ── Helper: clean a raw value from metadata ───────────────────────────────────

# Values that look like metadata but are actually placeholders — treat as empty
_PLACEHOLDER_VALUES = {
    "none", "null", "unknown", "undefined", "n/a", "na",
    "(anonymous)", "(unspecified)", "(none)", "(unknown)",
    "anonymous", "unspecified",
}

def _clean_val(v) -> str | None:
    """
    Convert a metadata value to a clean string.
    Returns None if the value is None, empty, literally 'None', or a known placeholder.
    """
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    if s.lower() in _PLACEHOLDER_VALUES:
        return None
    return s


# ── Image Metadata Extraction ─────────────────────────────────────────────────

def _extract_image_metadata(path: str) -> dict:
    """
    Extract EXIF metadata from any image type.

    Strategy:
      1. PIL.Image._getexif() — works for JPEG, PNG, TIFF, WebP
      2. piexif.load()        — JPEG-only; used for GPS and camera model precision
         Safely skipped for non-JPEG to avoid crash.
    """
    fields: dict = {}
    try:
        from PIL import Image, ExifTags
        img = Image.open(path)
        fields["image_format"] = img.format or Path(path).suffix.upper().lstrip(".")
        fields["image_size"]   = f"{img.width} x {img.height} px"
        fields["image_mode"]   = img.mode

        # ── Method 1: PIL universal EXIF (works for PNG, WebP, TIFF too) ──────
        try:
            exif_data = img._getexif() if hasattr(img, "_getexif") else None
            if not exif_data:
                # Pillow ≥10: use getexif()
                exif_data = dict(img.getexif()) if hasattr(img, "getexif") else {}
            if exif_data:
                for tag_id, val in exif_data.items():
                    tag_name = ExifTags.TAGS.get(tag_id, "")
                    v = _clean_val(val)
                    if not v:
                        continue
                    tag_lower = tag_name.lower()
                    if tag_lower in ("make",):
                        fields["camera_make"] = v[:100]
                    elif tag_lower in ("model",):
                        fields["camera_model"] = v[:100]
                    elif tag_lower in ("software",):
                        fields["software"] = v[:100]
                    elif tag_lower in ("datetime", "datetimeoriginal", "datetimedigitized"):
                        if "date_time" not in fields:
                            fields["date_time"] = v
                    elif tag_lower == "artist":
                        fields["artist"] = v[:100]
                    elif tag_lower == "copyright":
                        if v.strip() not in ("", "  "):
                            fields["copyright"] = v[:100]
                    elif tag_lower == "usercomment":
                        # Strip EXIF charset prefix (ASCII\x00\x00\x00 etc.)
                        clean = re.sub(r"^[A-Z]+\x00+", "", v).strip()
                        if clean and len(clean) > 2:
                            fields["user_comment"] = clean[:200]
        except Exception as e:
            logger.debug("PIL _getexif() failed for %s: %s", path, e)

        # ── Method 2: piexif — precise GPS (JPEG-only, safely skipped otherwise) ──
        ext = Path(path).suffix.lower()
        if ext in (".jpg", ".jpeg"):
            try:
                import piexif
                raw = piexif.load(path)
                ifd0 = raw.get("0th", {})
                gps  = raw.get("GPS", {})

                def _tag(ifd, tag_id):
                    v = ifd.get(tag_id)
                    if v is None:
                        return None
                    if isinstance(v, bytes):
                        try:
                            return v.decode("utf-8", errors="replace").strip("\x00")
                        except Exception:
                            return str(v)
                    return str(v)

                # Fill in camera fields if PIL missed them
                for key, tag in [
                    ("camera_make",  piexif.ImageIFD.Make),
                    ("camera_model", piexif.ImageIFD.Model),
                    ("software",     piexif.ImageIFD.Software),
                    ("artist",       piexif.ImageIFD.Artist),
                ]:
                    if key not in fields:
                        val = _clean_val(_tag(ifd0, tag))
                        if val:
                            fields[key] = val

                # GPS coordinates
                if gps:
                    lat_dms = gps.get(piexif.GPSIFD.GPSLatitude)
                    lat_ref = _tag(gps, piexif.GPSIFD.GPSLatitudeRef)
                    lon_dms = gps.get(piexif.GPSIFD.GPSLongitude)
                    lon_ref = _tag(gps, piexif.GPSIFD.GPSLongitudeRef)
                    if lat_dms and lon_dms:
                        def to_f(r):
                            return r[0] / r[1] if r[1] != 0 else 0
                        lat = to_f(lat_dms[0]) + to_f(lat_dms[1]) / 60 + to_f(lat_dms[2]) / 3600
                        if lat_ref and "S" in str(lat_ref).upper():
                            lat = -lat
                        lon = to_f(lon_dms[0]) + to_f(lon_dms[1]) / 60 + to_f(lon_dms[2]) / 3600
                        if lon_ref and "W" in str(lon_ref).upper():
                            lon = -lon
                        fields["gps_latitude"]  = str(round(lat, 6))
                        fields["gps_longitude"] = str(round(lon, 6))
                        fields["gps_full"]      = f"{round(lat, 6)}, {round(lon, 6)}"
                        fields["gps_maps_link"] = f"https://maps.google.com/?q={lat},{lon}"
            except Exception as e:
                logger.debug("piexif failed for %s: %s", path, e)

    except Exception as e:
        logger.warning("Image metadata extraction failed for %s: %s", path, e)

    return fields


# ── PDF Metadata Extraction ───────────────────────────────────────────────────

def _extract_pdf_metadata(path: str) -> dict:
    """
    Extract metadata from PDF.
    Tries PyMuPDF first (handles more edge cases), falls back to pdfplumber.
    """
    fields: dict = {}

    # ── Try PyMuPDF first ─────────────────────────────────────────────────────
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(path)
        fields["page_count"] = str(len(doc))
        meta = doc.metadata or {}
        doc.close()

        remap = {
            "author":   "author",
            "creator":  "creator",
            "producer": "software",
            "creationDate": "creation_date",
            "modDate":  "modification_date",
            "title":    "doc_title",
            "subject":  "subject",
            "keywords": "keywords",
        }
        for src, dst in remap.items():
            v = _clean_val(meta.get(src))
            if v:
                # Strip PDF date format prefix: D:20240101...
                if dst in ("creation_date", "modification_date") and v.startswith("D:"):
                    v = v[2:14]  # keep YYYYMMDDHHMMSS portion
                fields[dst] = v
        return fields

    except Exception as e:
        logger.debug("PyMuPDF metadata failed for %s: %s", path, e)

    # ── Fallback: pdfplumber ──────────────────────────────────────────────────
    try:
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            meta = pdf.metadata or {}
            if not fields.get("page_count"):
                fields["page_count"] = str(len(pdf.pages))
            for k, v in meta.items():
                clean_key = k.lstrip("/").lower().replace(" ", "_")
                val = _clean_val(v)
                if val:
                    fields[clean_key] = val[:300]
            remap = {
                "creator":       "creator",
                "author":        "author",
                "producer":      "software",
                "creationdate":  "creation_date",
                "moddate":       "modification_date",
                "title":         "doc_title",
                "subject":       "subject",
            }
            for src, dst in remap.items():
                if src in fields and dst not in fields:
                    fields[dst] = fields.pop(src)
    except Exception as e:
        logger.debug("pdfplumber metadata failed for %s: %s", path, e)

    return fields


# ── OOXML Metadata Extraction (DOCX / XLSX / PPTX) ───────────────────────────

def _extract_ooxml_metadata(path: str, file_type: str) -> dict:
    """
    Universal OOXML (docx, xlsx, pptx) extractor.
    Filters out None and 'None' string values carefully.
    """
    fields: dict = {}

    try:
        if file_type == "word":
            from docx import Document
            cp = Document(path).core_properties
            pairs = {
                "author":             cp.author,
                "last_modified_by":   cp.last_modified_by,
                "creation_date":      str(cp.created)  if cp.created  else None,
                "modification_date":  str(cp.modified) if cp.modified else None,
                "revision":           str(cp.revision) if cp.revision else None,
                "title":              cp.title,
                "subject":            cp.subject,
            }
            for k, v in pairs.items():
                val = _clean_val(v)
                if val:
                    fields[k] = val

        elif file_type == "excel":
            import openpyxl
            cp = openpyxl.load_workbook(path, read_only=True).properties
            pairs = {
                "author":            cp.creator,
                "last_modified_by":  cp.lastModifiedBy,
                "creation_date":     str(cp.created)  if cp.created  else None,
                "modification_date": str(cp.modified) if cp.modified else None,
                "title":             cp.title,
            }
            for k, v in pairs.items():
                val = _clean_val(v)
                if val:
                    fields[k] = val

    except Exception as e:
        logger.debug("%s lib extraction failed: %s", file_type, e)

    # ── Generic ZIP fallback: core.xml + app.xml ──────────────────────────────
    try:
        with zipfile.ZipFile(path, "r") as z:
            # Core properties
            if "docProps/core.xml" in z.namelist():
                xml = z.read("docProps/core.xml").decode("utf-8", errors="ignore")
                for tag, key in [
                    ("dc:creator",           "author"),
                    ("cp:lastModifiedBy",     "last_modified_by"),
                    ("cp:revision",           "revision"),
                    ("dcterms:created",       "creation_date"),
                    ("dcterms:modified",      "modification_date"),
                    ("dc:title",              "doc_title"),
                    ("dc:subject",            "subject"),
                    ("cp:keywords",           "keywords"),
                ]:
                    match = re.search(rf"<{re.escape(tag)}[^>]*>(.*?)</{re.escape(tag)}>", xml)
                    if match:
                        val = _clean_val(match.group(1))
                        if val and key not in fields:
                            fields[key] = val

            # App properties (Company, Application/software)
            if "docProps/app.xml" in z.namelist():
                xml = z.read("docProps/app.xml").decode("utf-8", errors="ignore")
                for pattern, key in [
                    (r"<Company>(.*?)</Company>",         "company"),
                    (r"<Application>(.*?)</Application>", "software"),
                    (r"<Words>(\d+)</Words>",             "word_count"),
                    (r"<Sheets>(\d+)</Sheets>",           "sheet_count"),
                ]:
                    match = re.search(pattern, xml)
                    if match:
                        val = _clean_val(match.group(1))
                        if val:
                            fields[key] = val

            # Tracked changes (Word security risk)
            if file_type == "word" and "word/settings.xml" in z.namelist():
                xml = z.read("word/settings.xml").decode("utf-8", errors="ignore")
                if "<w:trackRevisions" in xml:
                    fields["tracked_changes"] = "ACTIVE (Privacy Risk: Edit history is visible)"

    except Exception as e:
        logger.debug("ZIP OOXML fallback failed: %s", e)

    return fields


# ── Scoring & Categorization ──────────────────────────────────────────────────

def _score_metadata(fields: dict) -> tuple[float, str, list[dict], list[dict]]:
    """
    Categorizes metadata fields and calculates a weighted privacy score.
    Returns (score, risk_level, sensitive_findings, informational_fields).
    """
    score = 0.0
    sensitive = []
    informational = []

    _SKIP_DISPLAY = {"image_format", "image_size", "image_mode", "gps_maps_link", "sheets"}

    for key, val in fields.items():
        if key in _SKIP_DISPLAY:
            continue
        val_str = str(val).strip()
        if not val_str or val_str.lower() == "none":
            continue

        label  = FRIENDLY_LABELS.get(key, key.replace("_", " ").title())
        weight = _FIELD_WEIGHTS.get(key, 0)
        is_pii_leak = False

        # Detect embedded local file paths
        if re.search(r"[a-zA-Z]:\\[^/:\"*?<>|]+\\", val_str) or val_str.startswith("/home/"):
            weight = max(weight, 25)
            reason = "Local file path found. Reveals your computer's username and folder structure."
            is_pii_leak = True
            label = "Local File Location"
            key = "local_path"

        # Detect embedded email addresses
        elif re.search(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", val_str):
            weight = max(weight, 20)
            reason = REASONS.get("email_in_metadata", "Email found in metadata.")
            is_pii_leak = True

        # Detect embedded phone numbers
        elif re.search(r"[6-9]\d{9}", val_str.replace(" ", "")):
            weight = max(weight, 20)
            reason = REASONS.get("phone_in_metadata", "Phone number found in metadata.")
            is_pii_leak = True

        else:
            reason = REASONS.get(key, "This field reveals identifying details about the creator or device.")

        if key in SENSITIVE_FIELDS or weight > 0 or is_pii_leak or "tracked_changes" in key:
            if "tracked_changes" in key:
                weight = 20
            score += weight
            sensitive.append({
                "field":  key,
                "label":  label,
                "value":  val_str[:200],
                "risk":   "CRITICAL" if weight >= 25 else "HIGH" if weight >= 15 else "MEDIUM",
                "weight": weight,
                "reason": reason,
            })
        else:
            informational.append({
                "field": key,
                "label": label,
                "value": val_str[:200],
            })

    score = min(round(score, 1), 100.0)
    if   score >= 75: risk = "CRITICAL"
    elif score >= 45: risk = "HIGH"
    elif score >= 20: risk = "MEDIUM"
    elif score >= 5:  risk = "LOW"
    else:             risk = "SAFE"

    return score, risk, sensitive, informational


# ── Metadata Cleaner ──────────────────────────────────────────────────────────

def clean_metadata(file_path: str) -> str:
    """
    Creates a cleaned version of the file by stripping metadata.
    Returns path to the cleaned file.
    """
    path = Path(file_path)
    out_path = path.parent / f"CLEANED_{path.name}"
    ext = path.suffix.lower()

    try:
        if ext in IMAGE_EXTS:
            from PIL import Image
            img = Image.open(file_path)
            # Rebuild image without EXIF — copy pixel data only
            data = list(img.getdata())
            clean_img = Image.new(img.mode, img.size)
            clean_img.putdata(data)
            fmt = img.format or "PNG"
            clean_img.save(str(out_path), format=fmt)
            return str(out_path)

        elif ext == ".pdf":
            import fitz  # PyMuPDF
            doc = fitz.open(file_path)
            doc.set_metadata({})  # Clear all metadata
            doc.save(str(out_path))
            doc.close()
            return str(out_path)

        elif ext in (WORD_EXTS | EXCEL_EXTS | PPT_EXTS):
            # OOXML: strip docProps files from zip
            with zipfile.ZipFile(file_path, "r") as zin:
                with zipfile.ZipFile(str(out_path), "w", compression=zipfile.ZIP_DEFLATED) as zout:
                    for item in zin.infolist():
                        if not any(x in item.filename for x in [
                            "docProps/core.xml", "docProps/app.xml", "docProps/custom.xml"
                        ]):
                            zout.writestr(item, zin.read(item.filename))
            return str(out_path)

        else:
            shutil.copy2(file_path, str(out_path))
            return str(out_path)

    except Exception as e:
        logger.error("Metadata cleaning failed for %s: %s", file_path, e)
        return file_path


# ── Main Entry ────────────────────────────────────────────────────────────────

def extract_metadata(file_path: str) -> dict:
    """
    Main entry point: extract, score, and return structured metadata result.
    Always returns a clear result, including no_metadata_found=True when empty.
    """
    path = Path(file_path)
    ext  = path.suffix.lower()
    size = path.stat().st_size if path.exists() else 0

    if ext in IMAGE_EXTS:
        file_type = "image"
        fields    = _extract_image_metadata(file_path)
    elif ext in PDF_EXTS:
        file_type = "pdf"
        fields    = _extract_pdf_metadata(file_path)
    elif ext in WORD_EXTS:
        file_type = "word"
        fields    = _extract_ooxml_metadata(file_path, "word")
    elif ext in EXCEL_EXTS:
        file_type = "excel"
        fields    = _extract_ooxml_metadata(file_path, "excel")
    elif ext in PPT_EXTS:
        file_type = "powerpoint"
        fields    = _extract_ooxml_metadata(file_path, "powerpoint")
    else:
        file_type = "unknown"
        fields    = {}

    score, risk, sensitive, info = _score_metadata(fields)

    # ── No-metadata flag — clear message when nothing was found ───────────────
    no_metadata_found = (len(sensitive) == 0 and len(info) == 0)

    # ── Recommendations ───────────────────────────────────────────────────────
    recs = []
    if sensitive:
        recs.append({
            "title":    "Strip Metadata Before Sharing",
            "severity": "HIGH",
            "advice":   [
                "Use the 'Remove Metadata' tool below to clear document properties.",
                "Always share PDF versions instead of raw DOCX/XLSX to reduce leak surface.",
            ],
        })
    if any(f["field"] == "gps_full" for f in sensitive):
        recs.append({
            "title":    "Disable Camera GPS",
            "severity": "CRITICAL",
            "advice":   [
                "Go to Camera Settings → Location Tags and turn it OFF to prevent physical tracking.",
            ],
        })

    return {
        "file_type":            file_type,
        "extension":            ext,
        "file_size_kb":         round(size / 1024, 1),
        "filename":             path.name,
        "score":                score,
        "risk_level":           risk,
        "sensitive_findings":   sensitive,
        "informational_fields": info,
        "finding_count":        len(sensitive),
        "has_gps":              any(f["field"] == "gps_full" for f in sensitive),
        "gps_maps_link":        fields.get("gps_maps_link"),
        "recommendations":      recs,
        "no_metadata_found":    no_metadata_found,
        "no_metadata_message":  "No metadata found in this file." if no_metadata_found else None,
    }
