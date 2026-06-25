"""
Phase 12 — Score History Router
==================================
GET /api/history/timeline      → All scans over time (chart data, grouped by date)
GET /api/history/summary       → Stats: avg, max, min, trend, counts by risk level
GET /api/history/by-source     → Breakdown by source (file, url, social, metadata, screen)
GET /api/history/recent        → Last N scans (table view)
GET /api/history/trend         → 7-day / 30-day moving average
"""
from __future__ import annotations
import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend import models, auth
from backend.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/history", tags=["history"])

SOURCE_LABELS = {
    "file":          "Upload & Scan",
    "url":           "URL Scanner",
    "social":        "Social Scanner",
    "cloud":         "Cloud Scanner",
    "screen":        "Screen Monitor",
    "metadata_image":"Metadata (Image)",
    "metadata_word": "Metadata (Word)",
    "metadata_excel":"Metadata (Excel)",
    "metadata_pdf":  "Metadata (PDF)",
    "custom":        "Custom",
}

SOURCE_COLORS = {
    "file":          "#60a5fa",
    "url":           "#22d3ee",
    "social":        "#c084fc",
    "cloud":         "#38bdf8",
    "screen":        "#f87171",
    "metadata_image":"#fb923c",
    "metadata_word": "#fb923c",
    "metadata_excel":"#fb923c",
    "metadata_pdf":  "#fb923c",
    "custom":        "#94a3b8",
}

RISK_ORDER = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1, "SAFE": 0}


def _source_color(src: str) -> str:
    return SOURCE_COLORS.get(src, "#94a3b8")

def _source_label(src: str) -> str:
    if src and src.startswith("metadata"):
        return "Metadata Scanner"
    return SOURCE_LABELS.get(src, src or "Unknown")

def _risk_color(risk: str) -> str:
    return {"CRITICAL":"#dc2626","HIGH":"#ef4444","MEDIUM":"#f59e0b","LOW":"#22c55e","SAFE":"#6b7280"}.get(risk,"#6b7280")


# ── 1. Timeline (all scans chronologically, chart-ready) ──────────────────────

@router.get("/timeline")
def get_timeline(
    days:  int = Query(30, ge=1, le=365),
    db:    Session = Depends(get_db),
    user:  models.User = Depends(auth.get_current_user),
):
    """Returns every scan in the last `days` days, sorted by date — for a line chart."""
    since = datetime.utcnow() - timedelta(days=days)
    scans = (
        db.query(models.ScanRecord)
        .filter(
            models.ScanRecord.owner_id == user.id,
            models.ScanRecord.upload_date >= since,
        )
        .order_by(models.ScanRecord.upload_date.asc())
        .all()
    )

    points = []
    for s in scans:
        points.append({
            "scan_id":    s.id,
            "filename":   s.filename,
            "date":       s.upload_date.strftime("%Y-%m-%d") if s.upload_date else None,
            "datetime":   s.upload_date.isoformat() if s.upload_date else None,
            "score":      round(s.score or 0, 1),
            "risk_level": s.risk_level or "SAFE",
            "risk_color": _risk_color(s.risk_level or "SAFE"),
            "source":     s.source or "file",
            "source_label": _source_label(s.source or "file"),
            "source_color": _source_color(s.source or "file"),
            "finding_count": len(s.findings),
        })

    return {"points": points, "total": len(points), "days": days}


# ── 2. Summary stats ─────────────────────────────────────────────────────────

@router.get("/summary")
def get_summary(
    db:   Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    """Overall stats: avg score, max, min, risk distribution, trend direction."""
    all_scans = (
        db.query(models.ScanRecord)
        .filter(models.ScanRecord.owner_id == user.id)
        .order_by(models.ScanRecord.upload_date.asc())
        .all()
    )

    if not all_scans:
        return {
            "total_scans": 0, "avg_score": 0, "max_score": 0, "min_score": 0,
            "risk_distribution": {}, "trend": "neutral", "trend_value": 0,
            "first_scan": None, "latest_scan": None,
            "most_common_risk": "SAFE", "total_findings": 0,
        }

    scores = [s.score or 0 for s in all_scans]
    risks  = [s.risk_level or "SAFE" for s in all_scans]

    # Risk distribution
    risk_dist: dict[str, int] = defaultdict(int)
    for r in risks:
        risk_dist[r] += 1

    # Trend: compare last 5 vs first 5 avg
    trend, trend_val = "neutral", 0.0
    if len(scores) >= 2:
        half = max(1, len(scores) // 2)
        first_avg = sum(scores[:half]) / half
        last_avg  = sum(scores[-half:]) / half
        trend_val = round(last_avg - first_avg, 1)
        if trend_val > 5:   trend = "worsening"
        elif trend_val < -5: trend = "improving"
        else:               trend = "stable"

    total_findings = sum(len(s.findings) for s in all_scans)

    return {
        "total_scans":       len(all_scans),
        "avg_score":         round(sum(scores) / len(scores), 1),
        "max_score":         round(max(scores), 1),
        "min_score":         round(min(scores), 1),
        "risk_distribution": dict(risk_dist),
        "trend":             trend,
        "trend_value":       trend_val,
        "first_scan":        all_scans[0].upload_date.isoformat() if all_scans[0].upload_date else None,
        "latest_scan":       all_scans[-1].upload_date.isoformat() if all_scans[-1].upload_date else None,
        "most_common_risk":  max(risk_dist, key=risk_dist.get),
        "total_findings":    total_findings,
    }


# ── 3. By-source breakdown ────────────────────────────────────────────────────

@router.get("/by-source")
def get_by_source(
    db:   Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    """Score breakdown grouped by source (file, url, social, metadata, screen)."""
    scans = (
        db.query(models.ScanRecord)
        .filter(models.ScanRecord.owner_id == user.id)
        .all()
    )

    groups: dict[str, list] = defaultdict(list)
    for s in scans:
        # Normalise metadata sub-sources to single "metadata" group
        src = s.source or "file"
        if src.startswith("metadata"):
            src = "metadata"
        groups[src].append(s.score or 0)

    result = []
    for src, score_list in sorted(groups.items()):
        avg = round(sum(score_list) / len(score_list), 1) if score_list else 0
        result.append({
            "source":       src,
            "label":        _source_label(src),
            "color":        _source_color(src),
            "count":        len(score_list),
            "avg_score":    avg,
            "max_score":    round(max(score_list), 1),
            "min_score":    round(min(score_list), 1),
        })

    # Sort by avg_score descending (most risky first)
    result.sort(key=lambda x: x["avg_score"], reverse=True)
    return {"sources": result}


# ── 4. Recent scans table ─────────────────────────────────────────────────────

@router.get("/recent")
def get_recent(
    limit: int = Query(20, ge=1, le=100),
    db:    Session = Depends(get_db),
    user:  models.User = Depends(auth.get_current_user),
):
    """Last N scans — for the history table view."""
    scans = (
        db.query(models.ScanRecord)
        .filter(models.ScanRecord.owner_id == user.id)
        .order_by(models.ScanRecord.upload_date.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "scan_id":       s.id,
            "filename":      s.filename,
            "date":          s.upload_date.strftime("%d %b %Y, %H:%M") if s.upload_date else "—",
            "score":         round(s.score or 0, 1),
            "risk_level":    s.risk_level or "SAFE",
            "risk_color":    _risk_color(s.risk_level or "SAFE"),
            "source":        s.source or "file",
            "source_label":  _source_label(s.source or "file"),
            "source_color":  _source_color(s.source or "file"),
            "finding_count": len(s.findings),
        }
        for s in scans
    ]


# ── 5. Daily average (for moving-average chart) ───────────────────────────────

@router.get("/daily-avg")
def get_daily_avg(
    days: int = Query(30, ge=7, le=365),
    db:   Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    """Groups scans by calendar day and returns avg score per day."""
    since = datetime.utcnow() - timedelta(days=days)
    scans = (
        db.query(models.ScanRecord)
        .filter(
            models.ScanRecord.owner_id == user.id,
            models.ScanRecord.upload_date >= since,
        )
        .order_by(models.ScanRecord.upload_date.asc())
        .all()
    )

    daily: dict[str, list[float]] = defaultdict(list)
    for s in scans:
        if s.upload_date:
            day = s.upload_date.strftime("%Y-%m-%d")
            daily[day].append(s.score or 0)

    # Fill all days in range (even with no scans) so chart is continuous
    result = []
    for i in range(days):
        day = (datetime.utcnow() - timedelta(days=days - 1 - i)).strftime("%Y-%m-%d")
        vals = daily.get(day, [])
        result.append({
            "date":       day,
            "avg_score":  round(sum(vals) / len(vals), 1) if vals else None,
            "scan_count": len(vals),
        })

    return {"daily": result, "days": days}
