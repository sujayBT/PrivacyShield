"""
Phase 8 — Screenshot Monitor Router
=====================================
Endpoints:
  POST /api/monitor/session/start     — start a new monitoring session
  POST /api/monitor/session/stop/{id} — stop a session
  POST /api/monitor/analyze           — analyze one screenshot frame
  GET  /api/monitor/sessions          — list all sessions
  GET  /api/monitor/sessions/{id}     — session detail + alerts
  GET  /api/monitor/alerts            — all alerts for current user
  DELETE /api/monitor/sessions/{id}   — delete a session
"""
from __future__ import annotations
import json
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from pydantic import BaseModel

from backend import models, auth
from backend.database import get_db
from backend.services.screenshot_monitor import analyze_screenshot, save_screenshot
from backend.services.recommendations import generate_recommendations
from backend.services.notify import send_risk_alert

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/monitor", tags=["monitor"])


# ── 1. Start session ──────────────────────────────────────────────────────────

@router.post("/session/start")
def start_session(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    session = models.ScreenshotSession(
        owner_id=current_user.id,
        status="active",
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return {
        "session_id": session.id,
        "status":     session.status,
        "started_at": str(session.started_at),
        "message":    "Monitoring session started. Send screenshots to /analyze.",
    }


# ── 2. Stop session ───────────────────────────────────────────────────────────

@router.post("/session/stop/{session_id}")
def stop_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    session = db.query(models.ScreenshotSession).filter(
        models.ScreenshotSession.id == session_id,
        models.ScreenshotSession.owner_id == current_user.id,
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session.status   = "stopped"
    session.ended_at = datetime.utcnow()
    db.commit()
    db.refresh(session)
    return {
        "session_id":  session.id,
        "status":      session.status,
        "ended_at":    str(session.ended_at),
        "scan_count":  session.scan_count,
        "alert_count": session.alert_count,
    }


# ── 3. Analyze one screenshot frame ──────────────────────────────────────────

@router.post("/analyze")
async def analyze_frame(
    session_id: int = Form(...),
    ocr_text: str = Form(""),
    save_image: bool = Form(False),
    screenshot: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """
    Receive a screenshot (PNG/JPG) + optional OCR text.
    Run fast analysis. If score >= threshold, save alert to DB.
    """
    # Validate session
    session = db.query(models.ScreenshotSession).filter(
        models.ScreenshotSession.id == session_id,
        models.ScreenshotSession.owner_id == current_user.id,
        models.ScreenshotSession.status == "active",
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Active session not found")

    # Read image bytes
    image_bytes = await screenshot.read()

    # Analyze
    result = analyze_screenshot(image_bytes, ocr_text)

    # Increment scan count
    session.scan_count += 1

    alert_id = None
    scan_id   = None

    if result["should_alert"]:
        # Save image if requested
        img_path = None
        if save_image:
            img_path = save_screenshot(image_bytes, session_id)

        # Persist as a ScanRecord so it shows in history
        db_scan = models.ScanRecord(
            filename       = f"screenshot_{session_id}_{session.scan_count}.png",
            score          = result["score"],
            risk_level     = result["risk_level"],
            original_path  = img_path or "",
            extracted_text = ocr_text[:2000] if ocr_text else "",
            source         = "screenshot",
            source_url     = None,
            owner_id       = current_user.id,
        )
        db.add(db_scan)
        db.flush()

        for f in result["findings"]:
            db.add(models.Finding(
                type    = f["type"],
                value   = f["value"],
                scan_id = db_scan.id,
            ))

        scan_id = db_scan.id

        # Persist alert
        alert = models.ScreenshotAlert(
            session_id    = session_id,
            score         = result["score"],
            risk_level    = result["risk_level"],
            finding_types = json.dumps(result["finding_types"]),
            image_path    = img_path,
            scan_id       = scan_id,
        )
        db.add(alert)
        db.flush()
        alert_id = alert.id
        session.alert_count += 1

        # ── Fire OS desktop notification (like antivirus) ───────────────
        try:
            send_risk_alert(
                source="screen",
                name=f"Session #{session_id}",
                score=result["score"],
                risk=result["risk_level"],
                finding_types=result["finding_types"],
            )
        except Exception as e:
            logger.debug(f"Screen notification failed: {e}")

    db.commit()

    return {
        "session_id":    session_id,
        "scan_number":   session.scan_count,
        "score":         result["score"],
        "risk_level":    result["risk_level"],
        "should_alert":  result["should_alert"],
        "finding_count": len(result["findings"]),
        "finding_types": result["finding_types"],
        "face_count":    result["face_count"],
        "alert_id":      alert_id,
        "scan_id":       scan_id,
        "findings":      result["findings"],
    }


# ── 4. List sessions ──────────────────────────────────────────────────────────

@router.get("/sessions")
def list_sessions(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    sessions = db.query(models.ScreenshotSession).filter(
        models.ScreenshotSession.owner_id == current_user.id,
    ).order_by(models.ScreenshotSession.started_at.desc()).all()

    return [
        {
            "session_id":  s.id,
            "status":      s.status,
            "started_at":  str(s.started_at),
            "ended_at":    str(s.ended_at) if s.ended_at else None,
            "scan_count":  s.scan_count,
            "alert_count": s.alert_count,
        }
        for s in sessions
    ]


# ── 5. Session detail + alerts ────────────────────────────────────────────────

@router.get("/sessions/{session_id}")
def session_detail(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    session = db.query(models.ScreenshotSession).filter(
        models.ScreenshotSession.id == session_id,
        models.ScreenshotSession.owner_id == current_user.id,
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    alerts = []
    for a in session.alerts:
        try:
            ftypes = json.loads(a.finding_types or "[]")
        except Exception:
            ftypes = []
        alerts.append({
            "alert_id":     a.id,
            "timestamp":    str(a.timestamp),
            "score":        a.score,
            "risk_level":   a.risk_level,
            "finding_types": ftypes,
            "scan_id":      a.scan_id,
        })

    return {
        "session_id":  session.id,
        "status":      session.status,
        "started_at":  str(session.started_at),
        "ended_at":    str(session.ended_at) if session.ended_at else None,
        "scan_count":  session.scan_count,
        "alert_count": session.alert_count,
        "alerts":      alerts,
    }


# ── 6. All alerts ─────────────────────────────────────────────────────────────

@router.get("/alerts")
def all_alerts(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    sessions = db.query(models.ScreenshotSession).filter(
        models.ScreenshotSession.owner_id == current_user.id,
    ).all()
    session_ids = [s.id for s in sessions]

    alerts = db.query(models.ScreenshotAlert).filter(
        models.ScreenshotAlert.session_id.in_(session_ids),
    ).order_by(models.ScreenshotAlert.timestamp.desc()).limit(100).all()

    result = []
    for a in alerts:
        try:
            ftypes = json.loads(a.finding_types or "[]")
        except Exception:
            ftypes = []
        result.append({
            "alert_id":      a.id,
            "session_id":    a.session_id,
            "timestamp":     str(a.timestamp),
            "score":         a.score,
            "risk_level":    a.risk_level,
            "finding_types": ftypes,
            "scan_id":       a.scan_id,
        })
    return result


# ── 7. Delete session ─────────────────────────────────────────────────────────

@router.delete("/sessions/{session_id}")
def delete_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    session = db.query(models.ScreenshotSession).filter(
        models.ScreenshotSession.id == session_id,
        models.ScreenshotSession.owner_id == current_user.id,
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    db.query(models.ScreenshotAlert).filter(
        models.ScreenshotAlert.session_id == session_id
    ).delete()
    db.delete(session)
    db.commit()
    return {"message": f"Session {session_id} deleted"}
