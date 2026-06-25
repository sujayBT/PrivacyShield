"""
Phase 7 — Cloud Scan Router
============================
Endpoints:
  POST /api/cloud/scan-link      — scan a public cloud share link
  POST /api/cloud/batch-upload   — scan multiple uploaded files at once
  GET  /api/cloud/history        — list cloud scans for current user
  GET  /api/cloud/history/{id}   — get a specific cloud scan
"""

from __future__ import annotations
import os, shutil
from typing import List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Body
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from backend import models, auth
from backend.database import get_db
from backend.services.cloud_fetcher import download_cloud_file
from backend.services.detection import analyze_document
from backend.services.ai_detection import analyze_with_spacy, enrich_regex_findings, score_ai_findings
from backend.services.vision_detection import run_vision_analysis, score_vision_findings
from backend.services.recommendations import generate_recommendations

router = APIRouter(prefix="/api/cloud", tags=["cloud"])

from backend.config import UPLOAD_DIR, REPORTS_DIR


# ── Shared analysis pipeline ─────────────────────────────────────────────────

def _run_full_analysis(file_path: str, filename: str, source: str,
                       source_url: str | None, user_id: int, db: Session) -> models.ScanRecord:
    """Run full Regex + AI + Vision pipeline and persist to DB."""
    analysis       = analyze_document(file_path)
    extracted_text = analysis.get("text", "")
    regex_findings = analysis.get("findings", [])

    enriched_regex = enrich_regex_findings(regex_findings)
    ai_findings    = analyze_with_spacy(extracted_text)
    vision_result  = run_vision_analysis(file_path, extracted_text)
    vision_findings = vision_result.get("findings", [])

    all_findings       = enriched_regex + ai_findings + vision_findings
    
    # Apply Document Type Intelligence boost
    doc_type = analysis.get("document_type", "generic")
    doc_label = analysis.get("document_type_label", "Generic Document")
    doc_boost = analysis.get("document_type_boost", 0)
    doc_conf = analysis.get("document_type_confidence", "LOW")

    if doc_type != "generic":
        extracted_text = f"[Document Type: {doc_label}]\n" + extracted_text

    ai_score_boost     = score_ai_findings(ai_findings, doc_type=doc_type)
    vision_score_boost = score_vision_findings(vision_findings)
    final_score        = min(analysis["score"] + ai_score_boost + vision_score_boost + doc_boost, 100.0)

    # Only suppress for explicitly identified academic/code docs — NOT generic
    _LOW_RISK_DOC_TYPES = {"project_synopsis", "ml_notebook"}
    if doc_type in _LOW_RISK_DOC_TYPES:
        has_critical = any(f.get("type") in {"aadhaar", "pan_card", "credit_card", "cvv", "password"}
                          for f in all_findings)
        if not has_critical:
            final_score = min(final_score * 0.1, 12.0)

    # CRITICAL requires hard PII + high score
    has_hard_pii = any(f.get("type") in {"aadhaar", "pan_card", "credit_card", "cvv", "password"}
                       for f in all_findings)
    if final_score >= 80 and has_hard_pii: final_risk = "CRITICAL"
    elif final_score >= 75:                final_risk = "HIGH"
    elif final_score >= 35:                final_risk = "HIGH"
    elif final_score >= 15:                final_risk = "MEDIUM"
    else:                                  final_risk = "LOW"

    db_scan = models.ScanRecord(
        filename      = filename,
        score         = final_score,
        risk_level    = final_risk,
        original_path = file_path,
        extracted_text = extracted_text,
        source        = source,
        source_url    = source_url,
        owner_id      = user_id,
        vision_doc_type   = vision_result["document"].get("doc_type"),
        vision_face_count = vision_result["faces"].get("count", 0),
        vision_is_id_doc  = vision_result["document"].get("is_id_document", False),
    )
    db.add(db_scan)
    db.commit()
    db.refresh(db_scan)

    for f in all_findings:
        db.add(models.Finding(
            type          = f["type"],
            value         = f["value"],
            ai_confidence = f.get("confidence"),
            ai_label      = f.get("ai_label"),
            scan_id       = db_scan.id,
        ))
    db.commit()
    db.refresh(db_scan)
    return db_scan


# ── 1. Scan a public cloud share link ────────────────────────────────────────

class CloudLinkRequest(BaseModel):
    url: str

@router.post("/scan-link")
def scan_cloud_link(
    body: CloudLinkRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """
    Download and scan a publicly shared file from:
    Google Drive, Dropbox, OneDrive, or any direct download URL.
    """
    try:
        dl = download_cloud_file(body.url, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Download failed: {e}")

    db_scan = _run_full_analysis(
        file_path  = dl["path"],
        filename   = dl["filename"],
        source     = dl["source"],
        source_url = body.url,
        user_id    = current_user.id,
        db         = db,
    )

    return {
        "scan_id":     db_scan.id,
        "filename":    db_scan.filename,
        "source":      db_scan.source,
        "source_url":  db_scan.source_url,
        "score":       db_scan.score,
        "risk_level":  db_scan.risk_level,
        "finding_count": len(db_scan.findings),
        "findings":    [{"type": f.type, "value": f.value, "ai_confidence": f.ai_confidence} for f in db_scan.findings],
        "vision_doc_type":   db_scan.vision_doc_type,
        "vision_face_count": db_scan.vision_face_count,
        "vision_is_id_doc":  db_scan.vision_is_id_doc,
        "upload_date": str(db_scan.upload_date),
        "size_bytes":  dl["size_bytes"],
    }


# ── 2. Batch upload (multiple files) ─────────────────────────────────────────

@router.post("/batch-upload")
def batch_upload(
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """
    Upload and scan up to 10 files at once.
    Returns a list of scan results.
    """
    if len(files) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 files per batch")

    results = []
    for file in files:
        file_path = os.path.join(UPLOAD_DIR, f"batch_{current_user.id}_{file.filename}")
        with open(file_path, "wb") as buf:
            shutil.copyfileobj(file.file, buf)

        try:
            db_scan = _run_full_analysis(
                file_path  = file_path,
                filename   = file.filename,
                source     = "batch_upload",
                source_url = None,
                user_id    = current_user.id,
                db         = db,
            )
            results.append({
                "scan_id":      db_scan.id,
                "filename":     db_scan.filename,
                "score":        db_scan.score,
                "risk_level":   db_scan.risk_level,
                "finding_count": len(db_scan.findings),
                "findings":     [{"type": f.type, "value": f.value} for f in db_scan.findings],
                "vision_doc_type":  db_scan.vision_doc_type,
                "upload_date":  str(db_scan.upload_date),
                "error":        None,
            })
        except Exception as e:
            results.append({
                "scan_id":      None,
                "filename":     file.filename,
                "score":        0,
                "risk_level":   "LOW",
                "finding_count": 0,
                "findings":     [],
                "error":        str(e),
            })

    return {"batch_count": len(files), "results": results}


# ── 3. History ────────────────────────────────────────────────────────────────

@router.get("/history")
def cloud_history(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """All cloud-sourced scans for the current user."""
    scans = db.query(models.ScanRecord).filter(
        models.ScanRecord.owner_id == current_user.id,
        models.ScanRecord.source.in_(["gdrive", "dropbox", "onedrive", "direct_url", "batch_upload"]),
    ).order_by(models.ScanRecord.upload_date.desc()).all()

    return [
        {
            "scan_id":     s.id,
            "filename":    s.filename,
            "source":      s.source,
            "source_url":  s.source_url,
            "score":       s.score,
            "risk_level":  s.risk_level,
            "finding_count": len(s.findings),
            "vision_doc_type": s.vision_doc_type,
            "upload_date": str(s.upload_date),
        }
        for s in scans
    ]


# ── 4. Single cloud scan detail ───────────────────────────────────────────────

@router.get("/history/{scan_id}")
def cloud_scan_detail(
    scan_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    scan = db.query(models.ScanRecord).filter(
        models.ScanRecord.id == scan_id,
        models.ScanRecord.owner_id == current_user.id,
    ).first()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")

    findings_list = [{"type": f.type, "value": f.value, "ai_confidence": f.ai_confidence} for f in scan.findings]
    recs = generate_recommendations(
        emails=[], phones=[], passwords=[],
        score=scan.score, risk_level=scan.risk_level,
        findings=findings_list,
    )
    return {
        "scan_id":     scan.id,
        "filename":    scan.filename,
        "source":      scan.source,
        "source_url":  scan.source_url,
        "score":       scan.score,
        "risk_level":  scan.risk_level,
        "findings":    findings_list,
        "recommendations": recs,
        "vision_doc_type":   scan.vision_doc_type,
        "vision_face_count": scan.vision_face_count,
        "vision_is_id_doc":  scan.vision_is_id_doc,
        "upload_date": str(scan.upload_date),
        "extracted_text_preview": (scan.extracted_text or "")[:400],
    }
