"""
Phase 10 — Metadata Scanner Router (Professional Overhaul)
=========================================================
POST /api/metadata/scan           → Upload file, extract + score metadata
POST /api/metadata/clean          → Remove metadata from a file and download
GET  /api/metadata/scan/{scan_id} → Get metadata for an already-uploaded scan
GET  /api/metadata/history        → List metadata scan records
"""
from __future__ import annotations
import logging
import os
import tempfile
import uuid
from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from backend import models, auth
from backend.database import get_db
from backend.services.metadata_extractor import extract_metadata, clean_metadata

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/metadata", tags=["metadata"])

ALLOWED_EXTS = {
    ".jpg", ".jpeg", ".png", ".tiff", ".tif", ".webp", ".bmp",
    ".pdf", ".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt"
}
MAX_MB = 25


# ── 1. Upload + scan ──────────────────────────────────────────────────────────

@router.post("/scan")
async def metadata_scan(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTS:
        raise HTTPException(status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {sorted(ALLOWED_EXTS)}")

    content = await file.read()
    if len(content) > MAX_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"File too large (max {MAX_MB} MB)")

    try:
        # Create a unique temp name for persistence
        temp_dir = tempfile.gettempdir()
        temp_name = f"scan_{uuid.uuid4().hex}{ext}"
        tmp_path = os.path.join(temp_dir, temp_name)
        
        with open(tmp_path, "wb") as f:
            f.write(content)

        result = extract_metadata(tmp_path)

        # Persist as a ScanRecord
        db_scan = models.ScanRecord(
            filename      = file.filename or "unknown",
            score         = result["score"],
            risk_level    = result["risk_level"],
            original_path = tmp_path,
            extracted_text= _fields_to_text(result),
            source        = f"metadata_{result['file_type']}",
            owner_id      = current_user.id,
        )
        db.add(db_scan)
        db.flush()

        # Persist findings
        for f in result["sensitive_findings"]:
            db.add(models.Finding(
                type          = f["field"],
                value         = f["value"][:500],
                ai_label      = f["risk"],
                scan_id       = db_scan.id,
            ))

        db.commit()
        db.refresh(db_scan)

        return {
            **result,
            "scan_id": db_scan.id,
        }

    except Exception as e:
        logger.error(f"Metadata scan failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Scan failed: {str(e)[:200]}")


# ── 2. Metadata Cleaner ───────────────────────────────────────────────────────

@router.post("/clean")
async def metadata_clean_endpoint(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Strip metadata from an uploaded file and return the cleaned version."""
    ext = os.path.splitext(file.filename or "")[1].lower()
    content = await file.read()
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        clean_path = clean_metadata(tmp_path)
        
        # Ensure cleanup of temp files after response
        background_tasks.add_task(os.unlink, tmp_path)
        if clean_path != tmp_path:
            background_tasks.add_task(os.unlink, clean_path)

        return FileResponse(
            clean_path, 
            filename=f"CLEANED_{file.filename}",
            media_type="application/octet-stream"
        )
    except Exception as e:
        logger.error(f"Cleaning failed: {e}")
        raise HTTPException(500, detail="Metadata cleaning failed.")


# ── 3. History & Retrieval ───────────────────────────────────────────────────

@router.get("/scan/{scan_id}")
def get_scan_metadata(
    scan_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    scan = db.query(models.ScanRecord).filter(
        models.ScanRecord.id == scan_id,
        models.ScanRecord.owner_id == current_user.id,
    ).first()
    if not scan: raise HTTPException(404, "Scan not found")

    if scan.original_path and os.path.exists(scan.original_path):
        return {**extract_metadata(scan.original_path), "scan_id": scan_id}
    
    # Fallback response (simplified)
    return {
        "scan_id": scan_id, "filename": scan.filename,
        "score": scan.score, "risk_level": scan.risk_level,
        "sensitive_findings": [], "informational_fields": [],
        "note": "Original file no longer available."
    }

@router.get("/history")
def metadata_history(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    scans = db.query(models.ScanRecord).filter(
        models.ScanRecord.owner_id == current_user.id,
        models.ScanRecord.source.like("metadata_%"),
    ).order_by(models.ScanRecord.id.desc()).limit(30).all()

    return [{
        "scan_id": s.id, "filename": s.filename, "score": s.score,
        "risk_level": s.risk_level, "created_at": s.upload_date.isoformat() if s.upload_date else ""
    } for s in scans]


# ── 4. PDF Report ─────────────────────────────────────────────────────────────

@router.post("/scan/{scan_id}/report")
def metadata_pdf_report(
    scan_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    scan = db.query(models.ScanRecord).filter(
        models.ScanRecord.id == scan_id,
        models.ScanRecord.owner_id == current_user.id,
    ).first()
    if not scan: raise HTTPException(404, "Scan not found")

    # Pass the data to the report service
    # We re-extract to get the latest categorization if possible
    data = extract_metadata(scan.original_path) if (scan.original_path and os.path.exists(scan.original_path)) else {}
    
    out_path = os.path.join(tempfile.gettempdir(), f"metadata_report_{scan_id}.pdf")
    try:
        from backend.services.report import generate_metadata_report
        generate_metadata_report(
            output_path       = out_path,
            filename          = scan.filename,
            score             = scan.score,
            risk_level        = scan.risk_level,
            findings          = data.get("sensitive_findings", []),
            upload_date       = scan.upload_date,
            source            = scan.source,
            informational     = data.get("informational_fields", []),
            recommendations   = data.get("recommendations", [])
        )
        return FileResponse(out_path, media_type="application/pdf", filename=f"metadata_report_{scan.filename}.pdf")
    except Exception as e:
        logger.error(f"Metadata PDF failed: {e}")
        raise HTTPException(500, detail="PDF generation failed.")


# ── Helper ────────────────────────────────────────────────────────────────────

def _fields_to_text(res: dict) -> str:
    lines = ["[Sensitive Findings]"]
    for f in res.get("sensitive_findings", []):
        lines.append(f"{f['label']}: {f['value']}")
    lines.append("\n[Informational]")
    for f in res.get("informational_fields", []):
        lines.append(f"{f['label']}: {f['value']}")
    return "\n".join(lines)
