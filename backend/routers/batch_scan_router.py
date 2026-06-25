"""
Phase 13 — Batch Screenshot Scanner Router
============================================
Endpoints:
  POST /api/batch-scan/upload        — Upload & scan multiple screenshots at once (multipart)
  GET  /api/batch-scan/jobs          — List all batch jobs for current user
  GET  /api/batch-scan/jobs/{id}     — Single batch job detail + per-file results
  DELETE /api/batch-scan/jobs/{id}   — Delete a batch job
  GET  /api/batch-scan/aggregate     — Aggregate PII stats across all batch jobs
"""
from __future__ import annotations
import json
import uuid
import logging
from datetime import datetime
from collections import defaultdict
from typing import List

import os, shutil
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session

from backend import models, auth
from backend.database import get_db
from backend.services.screenshot_monitor import save_screenshot
from backend.services.detection import analyze_document
from backend.services.ai_detection import analyze_with_spacy, enrich_regex_findings, score_ai_findings
from backend.services.vision_detection import run_vision_analysis, score_vision_findings
from backend.services.recommendations import generate_recommendations

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/batch-scan", tags=["batch-scan"])

RISK_ORDER = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1, "SAFE": 0}


def _risk_color(risk: str) -> str:
    return {
        "CRITICAL": "#dc2626", "HIGH": "#ef4444",
        "MEDIUM": "#f59e0b", "LOW": "#22c55e", "SAFE": "#6b7280"
    }.get(risk, "#6b7280")


# ── Helper: run one image through the FULL scan pipeline ─────────────────────

from backend.config import UPLOAD_DIR

RISK_THRESHOLD = 10   # alert if score >= this

async def _scan_one(image_bytes: bytes, filename: str, owner_id: int, db: Session) -> dict:
    """
    Analyze one image using the full detection pipeline:
    Step 1: analyze_document  — regex patterns + OCR text extraction + document type detection
    Step 2: enrich_regex_findings — add confidence scores to regex matches
    Step 3: analyze_with_spacy — AI NER (names, locations, organizations)
    Step 4: run_vision_analysis — Vision AI (Aadhaar, ID card, face, bank statement detection)
    Step 5: Merge, score, persist.
    """
    # Save image to disk first so analyze_document/vision can read it
    safe_name = f"batch_{owner_id}_{filename}"
    img_path = os.path.join(UPLOAD_DIR, safe_name)
    with open(img_path, "wb") as f:
        f.write(image_bytes)

    # Pre-initialize defaults so the fallback path always has these variables
    all_findings   = []
    final_score    = 0.0
    final_risk     = "SAFE"
    face_count     = 0
    extracted_text = ""
    vision_result  = {"document": {}, "faces": {"count": 0}}

    try:
        # ── Step 1: Regex-based detection + full OCR text extraction ──────────
        analysis = analyze_document(img_path)
        extracted_text  = analysis.get("text", "")
        regex_findings  = analysis.get("findings", [])

        # ── Step 2: Enrich regex findings with confidence scores ───────────────
        enriched_regex = enrich_regex_findings(regex_findings)

        # ── Step 3: spaCy NER — detect names, locations, orgs ─────────────────
        ai_findings = analyze_with_spacy(extracted_text)

        # ── Step 4: Vision AI — detect ID cards, Aadhaar, faces, etc. ─────────
        vision_result   = run_vision_analysis(img_path, extracted_text)
        vision_findings = vision_result.get("findings", [])

        # ── Step 5: Merge all findings ─────────────────────────────────────────
        all_findings = enriched_regex + ai_findings + vision_findings

        # Apply Document Type Intelligence boost
        doc_type  = analysis.get("document_type", "generic")
        doc_label = analysis.get("document_type_label", "Generic Document")
        doc_boost = analysis.get("document_type_boost", 0)
        doc_conf  = analysis.get("document_type_confidence", "LOW")



        ai_score_boost     = score_ai_findings(ai_findings, doc_type=doc_type)
        vision_score_boost = score_vision_findings(vision_findings)

        final_score = min(analysis["score"] + ai_score_boost + vision_score_boost + doc_boost, 100.0)

        # Only suppress for explicitly identified academic/code documents — NOT generic
        _LOW_RISK_DOC_TYPES = {"project_synopsis", "ml_notebook"}
        if doc_type in _LOW_RISK_DOC_TYPES:
            has_critical = any(f.get("type") in {"aadhaar", "pan_card", "credit_card", "cvv", "password"}
                              for f in all_findings)
            if not has_critical:
                final_score = min(final_score * 0.1, 12.0)

        # Recalculate risk — CRITICAL requires hard PII
        has_hard_pii = any(f.get("type") in {"aadhaar", "pan_card", "credit_card", "cvv", "password"}
                           for f in all_findings)
        if   final_score >= 80 and has_hard_pii: final_risk = "CRITICAL"
        elif final_score >= 75: final_risk = "HIGH"
        elif final_score >= 35: final_risk = "HIGH"
        elif final_score >= 15: final_risk = "MEDIUM"
        elif final_score >= RISK_THRESHOLD: final_risk = "LOW"
        else:                   final_risk = "SAFE"

        face_count = vision_result.get("faces", {}).get("count", 0)

    except Exception as e:
        logger.error("Full pipeline failed for %s, falling back: %s", filename, e)
        # Minimal fallback
        all_findings = []
        final_score  = 0.0
        final_risk   = "SAFE"
        face_count   = 0
        extracted_text = ""

    # Persist ScanRecord
    db_scan = models.ScanRecord(
        filename       = filename,
        score          = final_score,
        risk_level     = final_risk,
        original_path  = img_path,
        extracted_text = extracted_text[:2000],
        source         = "batch_screenshot",
        source_url     = None,
        owner_id       = owner_id,
        vision_doc_type   = vision_result.get("document", {}).get("doc_type"),
        vision_face_count = face_count,
        vision_is_id_doc  = vision_result.get("document", {}).get("is_id_document", False),
    )
    db.add(db_scan)
    db.flush()

    for f in all_findings:
        db.add(models.Finding(
            type          = f["type"],
            value         = f["value"],
            ai_confidence = f.get("confidence"),
            ai_label      = f.get("ai_label"),
            scan_id       = db_scan.id,
        ))

    return {
        "scan_id":       db_scan.id,
        "filename":      filename,
        "score":         final_score,
        "risk_level":    final_risk,
        "risk_color":    _risk_color(final_risk),
        "should_alert":  final_score >= RISK_THRESHOLD,
        "finding_count": len(all_findings),
        "finding_types": list({f["type"] for f in all_findings}),
        "face_count":    face_count,
        "findings":      all_findings,
    }


# ── 1. Upload & scan batch ────────────────────────────────────────────────────

@router.post("/upload")
async def batch_upload(
    screenshots: List[UploadFile] = File(...),
    label: str = Form(""),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """
    Accept 1-50 screenshot files, scan each one, return aggregate results.
    Also persists a BatchScanJob record so history is kept.
    """
    if not screenshots:
        raise HTTPException(400, "No files provided")
    if len(screenshots) > 50:
        raise HTTPException(400, "Maximum 50 files per batch")

    job_label = label.strip() or f"Batch {datetime.utcnow().strftime('%d %b %H:%M')}"
    results   = []
    errors    = []

    for file in screenshots:
        if not file.filename.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".bmp")):
            errors.append({"filename": file.filename, "error": "Unsupported format — use PNG/JPG/JPEG/WEBP"})
            continue
        try:
            image_bytes = await file.read()
            res = await _scan_one(image_bytes, file.filename, current_user.id, db)
            results.append(res)
        except Exception as e:
            logger.error("Batch scan error for %s: %s", file.filename, e)
            errors.append({"filename": file.filename, "error": str(e)})

    db.commit()

    if not results and errors:
        raise HTTPException(422, detail=f"All files failed: {errors[0]['error']}")

    # ── Build aggregate ──
    scores     = [r["score"] for r in results]
    risks      = [r["risk_level"] for r in results]
    all_findings = []
    for r in results:
        all_findings.extend(r.get("findings", []))

    # Calculate COMBINED EXPOSURE SCORE (score the aggregate findings)
    # This prevents the 'dilution' effect where 1 bad file + 9 safe files = LOW score.
    # We group by type to use the diminishing returns scoring engine.
    from backend.services.detection import calculate_privacy_score
    findings_by_type = defaultdict(list)
    for f in all_findings:
        findings_by_type[f["type"]].append(f["value"])
    
    combined_score, combined_risk = calculate_privacy_score(dict(findings_by_type))

    all_types: dict = defaultdict(int)
    for r in results:
        for t in r["finding_types"]:
            all_types[t] += 1

    highest = max(risks, key=lambda x: RISK_ORDER.get(x, 0), default="SAFE") if risks else "SAFE"
    avg_score = combined_score # Use the aggregated score as the primary batch score
    max_score = round(max(scores), 1) if scores else 0
    alerts = [r for r in results if r["should_alert"]]

    # Persist batch job record
    job = models.BatchScanJob(
        owner_id    = current_user.id,
        label       = job_label,
        file_count  = len(results),
        alert_count = len(alerts),
        avg_score   = avg_score,
        max_score   = max_score,
        highest_risk= combined_risk, # Use aggregated risk
        results_json= json.dumps(results),
        errors_json = json.dumps(errors),
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    try:
        emails    = [f["value"] for f in all_findings if f.get("type") == "email"]
        phones    = [f["value"] for f in all_findings if f.get("type") == "phone"]
        passwords = [f["value"] for f in all_findings if f.get("type") == "password"]
        recommendations = generate_recommendations(emails, phones, passwords, avg_score, combined_risk, all_findings)
    except Exception:
        recommendations = []

    return {
        "job_id":          job.id,
        "label":           job_label,
        "total_files":     len(screenshots),
        "processed":       len(results),
        "errors":          errors,
        "avg_score":       avg_score,
        "max_score":       max_score,
        "highest_risk":    combined_risk,
        "risk_color":      _risk_color(combined_risk),
        "alert_count":     len(alerts),
        "pii_type_counts": dict(all_types),
        "results":         results,
        "recommendations": recommendations[:5],
        "created_at":      job.created_at.isoformat() if job.created_at else None,
    }



# ── 2. List batch jobs ────────────────────────────────────────────────────────

@router.get("/jobs")
def list_jobs(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    jobs = db.query(models.BatchScanJob).filter(
        models.BatchScanJob.owner_id == current_user.id
    ).order_by(models.BatchScanJob.created_at.desc()).all()

    return [
        {
            "job_id":       j.id,
            "label":        j.label,
            "file_count":   j.file_count,
            "alert_count":  j.alert_count,
            "avg_score":    j.avg_score,
            "max_score":    j.max_score,
            "highest_risk": j.highest_risk,
            "risk_color":   _risk_color(j.highest_risk or "SAFE"),
            "created_at":   j.created_at.strftime("%d %b %Y, %H:%M") if j.created_at else "—",
        }
        for j in jobs
    ]


# ── 3. Job detail ─────────────────────────────────────────────────────────────

@router.get("/jobs/{job_id}")
def job_detail(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    job = db.query(models.BatchScanJob).filter(
        models.BatchScanJob.id == job_id,
        models.BatchScanJob.owner_id == current_user.id,
    ).first()
    if not job:
        raise HTTPException(404, "Batch job not found")

    try:
        results = json.loads(job.results_json or "[]")
        errors  = json.loads(job.errors_json  or "[]")
    except Exception:
        results, errors = [], []

    return {
        "job_id":       job.id,
        "label":        job.label,
        "file_count":   job.file_count,
        "alert_count":  job.alert_count,
        "avg_score":    job.avg_score,
        "max_score":    job.max_score,
        "highest_risk": job.highest_risk,
        "risk_color":   _risk_color(job.highest_risk or "SAFE"),
        "created_at":   job.created_at.isoformat() if job.created_at else None,
        "results":      results,
        "errors":       errors,
    }


# ── 4. Delete job ─────────────────────────────────────────────────────────────

@router.delete("/jobs/{job_id}")
def delete_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    job = db.query(models.BatchScanJob).filter(
        models.BatchScanJob.id == job_id,
        models.BatchScanJob.owner_id == current_user.id,
    ).first()
    if not job:
        raise HTTPException(404, "Batch job not found")
    db.delete(job)
    db.commit()
    return {"message": f"Batch job {job_id} deleted"}


# ── 5. Aggregate stats ────────────────────────────────────────────────────────

@router.get("/aggregate")
def aggregate_stats(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Overall stats across all batch jobs for this user."""
    jobs = db.query(models.BatchScanJob).filter(
        models.BatchScanJob.owner_id == current_user.id
    ).all()

    if not jobs:
        return {"total_jobs": 0, "total_files": 0, "total_alerts": 0,
                "avg_score": 0, "max_score": 0, "pii_type_counts": {}}

    total_files  = sum(j.file_count  for j in jobs)
    total_alerts = sum(j.alert_count for j in jobs)
    all_scores   = [j.avg_score for j in jobs if j.avg_score is not None]

    # Aggregate PII types across all jobs
    all_pii: dict = defaultdict(int)
    for j in jobs:
        try:
            results = json.loads(j.results_json or "[]")
            for r in results:
                for t in r.get("finding_types", []):
                    all_pii[t] += 1
        except Exception:
            pass

    highest = max(
        (j.highest_risk for j in jobs if j.highest_risk),
        key=lambda x: RISK_ORDER.get(x, 0), default="SAFE"
    )

    return {
        "total_jobs":      len(jobs),
        "total_files":     total_files,
        "total_alerts":    total_alerts,
        "avg_score":       round(sum(all_scores)/len(all_scores), 1) if all_scores else 0,
        "max_score":       round(max(j.max_score for j in jobs if j.max_score), 1) if jobs else 0,
        "highest_risk":    highest,
        "risk_color":      _risk_color(highest),
        "pii_type_counts": dict(sorted(all_pii.items(), key=lambda x: -x[1])),
    }
