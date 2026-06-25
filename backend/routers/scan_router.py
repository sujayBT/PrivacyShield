import os
import shutil
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from backend import models, schemas, auth
from backend.database import get_db
from backend.services.detection import analyze_document
from backend.services.blurring import blur_image
from backend.services.recommendations import generate_recommendations
from backend.services.report import (
    generate_full_report,
    generate_sensitive_summary,
    generate_metadata_report,
    generate_attack_simulation,
    generate_score_history,
    generate_batch_report,
    generate_remediation_pdf,
)
from backend.services.ai_detection import (
    analyze_with_spacy,
    enrich_regex_findings,
    score_ai_findings,
    get_ai_engine_info,
)
from backend.services.vision_detection import (
    run_vision_analysis,
    score_vision_findings,
    get_vision_engine_info,
)

router = APIRouter(prefix="/api/scans", tags=["scans"])

from backend.config import UPLOAD_DIR, REPORTS_DIR


@router.post("/upload", response_model=schemas.ScanRecord)
def upload_file(
    file: UploadFile = File(...),
    source: Optional[str] = Query(default="file"),  # file | screen | social
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    file_path = os.path.join(UPLOAD_DIR, f"{current_user.id}_{file.filename}")
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # ── Step 1: Regex-based detection ─────────────────────────────────────
    analysis = analyze_document(file_path)
    extracted_text = analysis.get("text", "")
    regex_findings = analysis.get("findings", [])

    # ── Step 2: Enrich regex findings with confidence scores ───────────────
    enriched_regex = enrich_regex_findings(regex_findings)

    # ── Step 3: spaCy NER — detect new PII types (names, locations, orgs) ──
    ai_findings = analyze_with_spacy(extracted_text)

    # ── Step 4: Vision Analysis (Phase 6) ─────────────────────────────────
    vision_result  = run_vision_analysis(file_path, extracted_text)
    vision_findings = vision_result.get("findings", [])

    # ── Step 5: Merge all findings and recalculate score ───────────────────
    all_findings = enriched_regex + ai_findings + vision_findings
    
    # Apply Document Type Intelligence boost
    doc_type  = analysis.get("document_type", "generic")
    doc_label = analysis.get("document_type_label", "General Document")
    doc_boost = analysis.get("document_type_boost", 0)
    doc_conf  = analysis.get("document_type_confidence", 0.0)
    ai_method = analysis.get("ai_doc_method", "keyword")
    # NOTE: do NOT prepend [Document Type: ...] to extracted_text — it pollutes OCR display

    ai_score_boost     = score_ai_findings(ai_findings, doc_type=doc_type)
    vision_score_boost = score_vision_findings(vision_findings)

    # Cap total score at 100
    final_score = min(analysis["score"] + ai_score_boost + vision_score_boost + doc_boost, 100.0)

    # Downscale ONLY for specifically identified low-risk doc types (project synopses, ML notebooks)
    # Do NOT include "generic" here — generic means unidentified, not safe
    _LOW_RISK_DOC_TYPES = {"project_synopsis", "ml_notebook"}
    if doc_type in _LOW_RISK_DOC_TYPES:
        # Check for critical PII in findings
        has_critical = any(f.get("type") in {"aadhaar", "pan_card", "credit_card", "cvv", "password"}
                          for f in all_findings)
        if not has_critical:
            # Confirmed academic/code doc with no real PII → cap score
            final_score = min(final_score * 0.1, 12.0)

    # Recalculate risk with final score — CRITICAL requires hard PII
    has_hard_pii = any(f.get("type") in {"aadhaar", "pan_card", "credit_card", "cvv", "password"}
                       for f in all_findings)
    if final_score >= 80 and has_hard_pii:
        final_risk = "CRITICAL"
    elif final_score >= 75:
        final_risk = "HIGH"
    elif final_score >= 35:
        final_risk = "HIGH"
    elif final_score >= 15:
        final_risk = "MEDIUM"
    elif final_score > 0 or len(all_findings) > 0:
        final_risk = "LOW"
    else:
        final_risk = "SAFE"

    # ── Step 5: Persist to DB ──────────────────────────────────────────────
    db_scan = models.ScanRecord(
        filename=file.filename,
        score=final_score,
        risk_level=final_risk,
        original_path=file_path,
        extracted_text=extracted_text,
        source=source or "file",
        owner_id=current_user.id,
        vision_doc_type=vision_result["document"].get("doc_type"),
        vision_face_count=vision_result["faces"].get("count", 0),
        vision_is_id_doc=vision_result["document"].get("is_id_document", False),
        # Persist AI doc classification so GET /scans/{id} can return it
        ai_doc_type_label=doc_label if doc_type != "generic" else None,
        ai_doc_confidence=float(doc_conf) if isinstance(doc_conf, (int, float)) else None,
    )
    db.add(db_scan)
    db.commit()
    db.refresh(db_scan)

    for finding in all_findings:
        db.add(models.Finding(
            type=finding["type"],
            value=finding["value"],
            ai_confidence=finding.get("confidence"),
            ai_label=finding.get("ai_label"),
            scan_id=db_scan.id
        ))

    db.commit()
    db_scan = db.query(models.ScanRecord).filter(models.ScanRecord.id == db_scan.id).first()

    # Return enriched response with AI document classification info
    # (these fields are not stored in DB but passed through for the frontend)
    from backend.schemas import ScanRecord as ScanRecordSchema, Finding as FindingSchema
    scan_dict = {
        "id":                db_scan.id,
        "filename":          db_scan.filename,
        "score":             db_scan.score,
        "risk_level":        db_scan.risk_level,
        "upload_date":       db_scan.upload_date.isoformat() if db_scan.upload_date else None,
        "original_path":     db_scan.original_path,
        "blurred_path":      db_scan.blurred_path,
        "extracted_text":    db_scan.extracted_text,
        "source":            db_scan.source,
        "source_url":        db_scan.source_url,
        "vision_doc_type":   db_scan.vision_doc_type,
        "vision_face_count": db_scan.vision_face_count,
        "vision_is_id_doc":  db_scan.vision_is_id_doc,
        # AI Document Classification — shown in results panel
        "ai_doc_type_label": doc_label if doc_type != "generic" else None,
        "ai_doc_confidence": float(doc_conf) if isinstance(doc_conf, (int, float)) else None,
        "findings": [
            {
                "id":            f.id,
                "type":          f.type,
                "value":         f.value,
                "ai_confidence": f.ai_confidence,
                "ai_label":      f.ai_label,
            }
            for f in db_scan.findings
        ],
    }
    return scan_dict


@router.get("/ai-info", response_model=dict)
def ai_engine_info(
    current_user: models.User = Depends(auth.get_current_user)
):
    """Returns info about the active AI detection engine."""
    return get_ai_engine_info()


@router.get("/vision-info", response_model=dict)
def vision_engine_info(
    current_user: models.User = Depends(auth.get_current_user)
):
    """Returns info about the Phase 6 vision detection engine."""
    return get_vision_engine_info()


@router.get("/", response_model=List[schemas.ScanRecord])
def list_scans(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    return db.query(models.ScanRecord).filter(
        models.ScanRecord.owner_id == current_user.id
    ).order_by(models.ScanRecord.upload_date.desc()).all()


@router.get("/{scan_id}", response_model=schemas.ScanRecord)
def get_scan(
    scan_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    import re as _re
    scan = db.query(models.ScanRecord).filter(
        models.ScanRecord.id == scan_id,
        models.ScanRecord.owner_id == current_user.id
    ).first()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")

    # Strip old [Document Type: ...] prefix from extracted_text if present (legacy format)
    if scan.extracted_text:
        m = _re.match(r"^\[Document Type:\s*(.+?)\]\n?", scan.extracted_text)
        if m:
            # If DB doesn't have the label yet, backfill from old prefix
            if not scan.ai_doc_type_label:
                scan.ai_doc_type_label = m.group(1).strip()
            scan.extracted_text = scan.extracted_text[m.end():]

    # Build response using the persisted DB values
    result = schemas.ScanRecord.model_validate(scan).model_dump()
    result["ai_doc_type_label"] = scan.ai_doc_type_label
    result["ai_doc_confidence"] = scan.ai_doc_confidence
    return result


@router.post("/{scan_id}/blur", response_model=schemas.ScanRecord)
def blur_scan(
    scan_id: int,
    blur_faces: bool = Query(default=True, description="Whether to blur detected faces"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    scan = db.query(models.ScanRecord).filter(
        models.ScanRecord.id == scan_id,
        models.ScanRecord.owner_id == current_user.id
    ).first()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")

    if not scan.original_path.lower().endswith((".png", ".jpg", ".jpeg")):
        raise HTTPException(status_code=400, detail="Only images can be blurred currently")

    blurred_path = os.path.join(UPLOAD_DIR, f"blurred_{current_user.id}_{scan.filename}")
    try:
        # Optionally detect and blur face bounding boxes
        face_boxes = []
        if blur_faces:
            try:
                from backend.services.vision_detection import _load_image, detect_faces
                img_bgr = _load_image(scan.original_path)
                is_id_doc = getattr(scan, "vision_is_id_doc", False)
                face_result = detect_faces(img_bgr, is_id_doc=is_id_doc)
                face_boxes = face_result.get("bounding_boxes", [])
            except Exception:
                pass  # Vision not available — skip face blur silently

        finding_values = [f.value for f in scan.findings if f.type != "document_type"]
        blur_image(scan.original_path, blurred_path, finding_values, face_boxes=face_boxes)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    scan.blurred_path = blurred_path
    db.commit()
    db.refresh(scan)
    return scan


@router.get("/{scan_id}/image/original")
def get_original_image(
    scan_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    scan = db.query(models.ScanRecord).filter(
        models.ScanRecord.id == scan_id,
        models.ScanRecord.owner_id == current_user.id
    ).first()
    if not scan or not scan.original_path or not os.path.exists(scan.original_path):
        raise HTTPException(status_code=404, detail="Original image not found")
    return FileResponse(scan.original_path)


@router.get("/{scan_id}/image/blurred")
def get_blurred_image(
    scan_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    scan = db.query(models.ScanRecord).filter(
        models.ScanRecord.id == scan_id,
        models.ScanRecord.owner_id == current_user.id
    ).first()
    if not scan or not scan.blurred_path or not os.path.exists(scan.blurred_path):
        raise HTTPException(status_code=404, detail="Blurred image not found")
    return FileResponse(scan.blurred_path)


@router.get("/{scan_id}/recommendations")
def get_recommendations(
    scan_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    scan = db.query(models.ScanRecord).filter(
        models.ScanRecord.id == scan_id,
        models.ScanRecord.owner_id == current_user.id
    ).first()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")

    findings = db.query(models.Finding).filter(models.Finding.scan_id == scan_id).all()
    findings_list = [{"type": f.type, "value": f.value} for f in findings]

    recommendations = generate_recommendations(
        emails=[],
        phones=[],
        passwords=[],
        score=scan.score,
        risk_level=scan.risk_level,
        findings=findings_list,
    )
    return {"scan_id": scan_id, "recommendations": recommendations}


@router.post("/{scan_id}/report")
def generate_report(
    scan_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    scan = db.query(models.ScanRecord).filter(
        models.ScanRecord.id == scan_id,
        models.ScanRecord.owner_id == current_user.id
    ).first()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")

    findings = db.query(models.Finding).filter(models.Finding.scan_id == scan_id).all()
    findings_list = [{"type": f.type, "value": f.value} for f in findings]

    recommendations = generate_recommendations(
        emails=[],
        phones=[],
        passwords=[],
        score=scan.score,
        risk_level=scan.risk_level,
        findings=findings_list,
    )

    report_path = os.path.join(REPORTS_DIR, f"report_{current_user.id}_{scan.id}.pdf")
    generate_full_report(
        output_path=report_path,
        filename=scan.filename,
        text=scan.extracted_text or "",
        score=scan.score,
        risk_level=scan.risk_level,
        findings=findings_list,
        recommendations=recommendations
    )

    return FileResponse(
        report_path,
        media_type="application/pdf",
        filename=f"privacy_report_{scan.filename}.pdf"
    )


# ────────────────────────────────────────────────────────────────────────────
# 2. Sensitive Data Summary
# ────────────────────────────────────────────────────────────────────────────
@router.post("/{scan_id}/report/sensitive-summary")
def report_sensitive_summary(
    scan_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    scan = db.query(models.ScanRecord).filter(
        models.ScanRecord.id == scan_id, models.ScanRecord.owner_id == current_user.id
    ).first()
    if not scan: raise HTTPException(status_code=404, detail="Scan not found")
    findings = [{"type": f.type, "value": f.value} for f in db.query(models.Finding).filter(models.Finding.scan_id == scan_id).all()]
    out = os.path.join(REPORTS_DIR, f"summary_{current_user.id}_{scan.id}.pdf")
    generate_sensitive_summary(out, scan.filename, scan.score, scan.risk_level, findings)
    return FileResponse(out, media_type="application/pdf", filename=f"sensitive_summary_{scan.filename}.pdf")


# ────────────────────────────────────────────────────────────────────────────
# 3. Metadata Report
# ────────────────────────────────────────────────────────────────────────────
@router.post("/{scan_id}/report/metadata")
def report_metadata(
    scan_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    scan = db.query(models.ScanRecord).filter(
        models.ScanRecord.id == scan_id, models.ScanRecord.owner_id == current_user.id
    ).first()
    if not scan: raise HTTPException(status_code=404, detail="Scan not found")
    
    from backend.services.metadata_extractor import extract_metadata
    
    # Extract real file metadata if available
    data = {}
    if scan.original_path and os.path.exists(scan.original_path):
        try:
            data = extract_metadata(scan.original_path)
        except Exception:
            pass

    # Gather informational fields
    informational_fields = data.get("informational_fields", [])
    
    # Enrich with Vision AI results
    if getattr(scan, "vision_doc_type", None):
        informational_fields.append({
            "field": "vision_doc_type",
            "label": "AI Detected Doc Type",
            "value": str(scan.vision_doc_type).replace("_", " ").title()
        })
    if getattr(scan, "vision_face_count", 0) is not None:
        informational_fields.append({
            "field": "vision_face_count",
            "label": "AI Detected Face Count",
            "value": str(scan.vision_face_count)
        })

    # Prepare findings and recommendations
    findings_list = data.get("sensitive_findings", [])
    recommendations_list = data.get("recommendations", [])
    
    out = os.path.join(REPORTS_DIR, f"meta_{current_user.id}_{scan.id}.pdf")
    
    generate_metadata_report(
        output_path=out,
        filename=scan.filename,
        score=scan.score,
        risk_level=scan.risk_level,
        findings=findings_list,
        upload_date=scan.upload_date,
        source=scan.source or "file",
        informational=informational_fields,
        recommendations=recommendations_list
    )
    return FileResponse(out, media_type="application/pdf", filename=f"metadata_report_{scan.filename}.pdf")


# ────────────────────────────────────────────────────────────────────────────
# 4. Attack Simulation Report
# ────────────────────────────────────────────────────────────────────────────
@router.post("/{scan_id}/report/attack-simulation")
def report_attack_simulation(
    scan_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    scan = db.query(models.ScanRecord).filter(
        models.ScanRecord.id == scan_id, models.ScanRecord.owner_id == current_user.id
    ).first()
    if not scan: raise HTTPException(status_code=404, detail="Scan not found")
    findings = [{"type": f.type, "value": f.value} for f in db.query(models.Finding).filter(models.Finding.scan_id == scan_id).all()]
    out = os.path.join(REPORTS_DIR, f"attack_{current_user.id}_{scan.id}.pdf")
    generate_attack_simulation(out, scan.filename, scan.score, scan.risk_level, findings)
    return FileResponse(out, media_type="application/pdf", filename=f"attack_simulation_{scan.filename}.pdf")


# ────────────────────────────────────────────────────────────────────────────
# 5. Score History Report
# ────────────────────────────────────────────────────────────────────────────
@router.post("/report/score-history")
def report_score_history(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    """Score History Report — file upload scans only (excludes social/url/batch/monitor)."""
    from sqlalchemy import or_
    all_scans = db.query(models.ScanRecord).filter(
        models.ScanRecord.owner_id == current_user.id,
        or_(
            models.ScanRecord.source == "file",    # normal file uploads
            models.ScanRecord.source == None,       # legacy records with NULL source
        )
    ).order_by(models.ScanRecord.upload_date.asc()).all()
    scans_data = [{
        "id": s.id, "filename": s.filename, "score": s.score,
        "risk_level": s.risk_level, "upload_date": str(s.upload_date),
        "finding_count": len(s.findings)
    } for s in all_scans]
    out = os.path.join(REPORTS_DIR, f"history_{current_user.id}.pdf")
    generate_score_history(out, scans_data)
    return FileResponse(out, media_type="application/pdf", filename="score_history_report.pdf")


# ────────────────────────────────────────────────────────────────────────────
# 6. Batch Scan Report
# ────────────────────────────────────────────────────────────────────────────
@router.post("/report/batch")
def report_batch(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    """Batch Scan Report — contains ONLY Batch Screenshot Scanner results."""
    all_scans = db.query(models.ScanRecord).filter(
        models.ScanRecord.owner_id == current_user.id,
        models.ScanRecord.source == "batch_screenshot",   # batch scanner only
    ).order_by(models.ScanRecord.upload_date.desc()).limit(20).all()

    if not all_scans:
        raise HTTPException(
            status_code=404,
            detail="No batch screenshot scans found. Run the Batch Screenshot Scanner first."
        )

    scans_data = []
    for s in all_scans:
        findings = [{"type": f.type, "value": f.value} for f in s.findings]
        scans_data.append({
            "scan": {"id": s.id, "filename": s.filename, "score": s.score, "risk_level": s.risk_level},
            "findings": findings
        })
    out = os.path.join(REPORTS_DIR, f"batch_{current_user.id}.pdf")
    generate_batch_report(out, scans_data)
    return FileResponse(out, media_type="application/pdf", filename="batch_scan_report.pdf")


# ────────────────────────────────────────────────────────────────────────────
# Phase 16 — Remediation Plan
# ────────────────────────────────────────────────────────────────────────────
@router.get("/{scan_id}/remediation")
def get_remediation_plan(
    scan_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    """Return per-finding step-by-step remediation plan with legal refs."""
    from backend.services.remediation import generate_remediation_plan
    scan = db.query(models.ScanRecord).filter(
        models.ScanRecord.id == scan_id,
        models.ScanRecord.owner_id == current_user.id
    ).first()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    findings = [{"type": f.type, "value": f.value} for f in scan.findings]
    return generate_remediation_plan(findings, scan.risk_level)


# ────────────────────────────────────────────────────────────────────────────
# Phase 17 — Remediation PDF Report
# ────────────────────────────────────────────────────────────────────────────
@router.post("/{scan_id}/report/remediation")
def report_remediation(
    scan_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    """Export the full remediation action plan as a downloadable PDF."""
    from backend.services.remediation import generate_remediation_plan
    scan = db.query(models.ScanRecord).filter(
        models.ScanRecord.id == scan_id,
        models.ScanRecord.owner_id == current_user.id
    ).first()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    findings = [{"type": f.type, "value": f.value} for f in scan.findings]
    plan = generate_remediation_plan(findings, scan.risk_level)
    out = os.path.join(REPORTS_DIR, f"remediation_{current_user.id}_{scan.id}.pdf")
    generate_remediation_pdf(out, scan.filename, scan.score, scan.risk_level, plan)
    return FileResponse(out, media_type="application/pdf",
                        filename=f"remediation_plan_{scan.filename}.pdf")
