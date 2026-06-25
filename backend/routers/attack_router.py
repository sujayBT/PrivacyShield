"""
Phase 11 — Attack Simulation Router
======================================
POST /api/attack/simulate/scan/{scan_id}   → Simulate from any existing scan
POST /api/attack/simulate/custom           → Simulate from manually supplied findings
GET  /api/attack/history                   → List recent simulations for the user
GET  /api/attack/scenarios                 → List all available attack scenario types
"""
from __future__ import annotations
import logging
import json
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend import models, auth
from backend.database import get_db
from backend.services.attack_simulation import run_attack_simulation, SCENARIOS

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/attack", tags=["attack"])


# ── Pydantic Schemas ─────────────────────────────────────────────────────────

class FindingItem(BaseModel):
    type:  str
    value: str

class CustomSimulateRequest(BaseModel):
    findings:   List[FindingItem]
    score:      float = 0.0
    risk_level: str   = "SAFE"
    label:      str   = "Custom Simulation"


# ── 1. Simulate from existing scan ─────────────────────────────────────────────

@router.post("/simulate/scan/{scan_id}")
def simulate_from_scan(
    scan_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Run attack simulation against an existing scan record (any phase)."""
    scan = db.query(models.ScanRecord).filter(
        models.ScanRecord.id == scan_id,
        models.ScanRecord.owner_id == current_user.id,
    ).first()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")

    findings = [
        {"type": f.type, "value": f.value}
        for f in scan.findings
    ]

    result = run_attack_simulation(
        findings   = findings,
        score      = scan.score or 0.0,
        risk_level = scan.risk_level or "SAFE",
        source     = scan.source or "file",
    )

    return {
        **result,
        "scan_id":   scan_id,
        "filename":  scan.filename,
        "source":    scan.source,
        "score":     scan.score,
        "risk_level":scan.risk_level,
    }


# ── 2. Simulate from custom/manual findings ────────────────────────────────────

@router.post("/simulate/custom")
def simulate_custom(
    req: CustomSimulateRequest,
    current_user: models.User = Depends(auth.get_current_user),
):
    """Run attack simulation from manually supplied findings (no existing scan needed)."""
    findings = [{"type": f.type, "value": f.value} for f in req.findings]
    result = run_attack_simulation(
        findings   = findings,
        score      = req.score,
        risk_level = req.risk_level,
        source     = "custom",
    )
    return {
        **result,
        "label": req.label,
    }


# ── 3. Simulate from ALL user scans (aggregate) ────────────────────────────────

@router.get("/simulate/aggregate")
def simulate_aggregate(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """
    Aggregate all findings across ALL scans for this user and run a combined
    attack simulation — shows the worst-case scenario from all their data.
    """
    scans = db.query(models.ScanRecord).filter(
        models.ScanRecord.owner_id == current_user.id,
    ).all()

    all_findings = []
    max_score = 0.0
    for scan in scans:
        for f in scan.findings:
            all_findings.append({"type": f.type, "value": f.value})
        if scan.score and scan.score > max_score:
            max_score = scan.score

    result = run_attack_simulation(
        findings   = all_findings,
        score      = max_score,
        risk_level = _score_to_risk(max_score),
        source     = "aggregate",
    )

    return {
        **result,
        "total_scans":    len(scans),
        "total_findings": len(all_findings),
    }


# ── 4. List available scenarios ────────────────────────────────────────────────

@router.get("/scenarios")
def list_scenarios(
    current_user: models.User = Depends(auth.get_current_user),
):
    """Return all available attack scenario definitions (no PII required)."""
    return [
        {
            "id":          s["id"],
            "name":        s["name"],
            "icon":        s["icon"],
            "severity":    s["severity"],
            "color":       s["color"],
            "description": s["description"],
            "requires":    s["requires"],
        }
        for s in SCENARIOS
    ]


# ── 5. Recent scans list (for the UI scan picker) ──────────────────────────────

@router.get("/scans")
def list_user_scans(
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Return recent scans for the user so they can pick one to simulate."""
    scans = (
        db.query(models.ScanRecord)
        .filter(models.ScanRecord.owner_id == current_user.id)
        .order_by(models.ScanRecord.id.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "scan_id":       s.id,
            "filename":      s.filename,
            "source":        s.source or "file",
            "score":         s.score or 0.0,
            "risk_level":    s.risk_level or "SAFE",
            "finding_count": len(s.findings),
            "created_at":    str(s.upload_date) if s.upload_date else "",
        }
        for s in scans
    ]


# ── Helper ────────────────────────────────────────────────────────────────────

def _score_to_risk(score: float) -> str:
    if score >= 75: return "CRITICAL"
    if score >= 35: return "HIGH"
    if score >= 15: return "MEDIUM"
    return "LOW"
    return "SAFE"
