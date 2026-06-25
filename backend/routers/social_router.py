"""
Phase 9 — Social Media Scanner Router (v2 Rebuilt)
====================================================
POST   /api/social/scan          → Scan a public social media profile URL
GET    /api/social/history       → List all social scans for current user
GET    /api/social/history/{id}  → Full detail + recommendations for a scan
DELETE /api/social/history/{id}  → Delete a scan record

Detection is social-specific only:
- email, phone, website, location, display_name
- NO Aadhaar, PAN, OTP, password, credit card, DOB
Scoring uses social-appropriate weights (not document weights).
"""
from __future__ import annotations
import logging, re, tempfile, os
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend import models, auth
from backend.database import get_db
from backend.services.social_scraper import (
    scrape_profile, download_avatar, detect_platform, PLATFORM_IGNORE_ENTITIES, classify_profile_exposure
)
from backend.services.vision_detection import run_vision_analysis
from backend.services.recommendations import generate_recommendations

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/social", tags=["social"])

# ── Social-specific detection patterns ───────────────────────────────────────
# Only patterns relevant to public social profiles.
# Document-only patterns (Aadhaar, PAN, OTP, credit card, password) are excluded.

_SOCIAL_PATTERNS = {
    "email":   re.compile(r"\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}\b"),
    "phone":   re.compile(
        r"(?:"
        r"\b[6-9]\d{9}\b"                        # Indian 10-digit mobile
        r"|(?:\+\d{1,3}[\s\-]?)?\(?\d{3}\)?[\s\-]\d{3}[\s\-]\d{4}\b"  # intl format
        r")"
    ),
    "website": re.compile(r"https?://(?!(?:www\.)?(?:instagram|twitter|reddit|linkedin|facebook|youtube|tiktok|x)\.com)[^\s<>\"']{6,}"),
}

# Weights — profile fields always scored, text patterns add on top
_SOCIAL_WEIGHTS = {
    "email":        25,  # public email is sensitive
    "phone":        28,  # public phone is sensitive
    "website":       8,  # profile website links
    "username":      5,  # handle
    "display_name":  6,  # real name
    "location":     10,  # location in profile
    "bio":           7,  # bio text content
    "company":       6,  # company/org on GitHub profile
    "face_detected": 8,  # face in avatar
    "id_card_visible": 40, # ID card as avatar
}

# Risk thresholds for social context
def _social_risk(score: float) -> str:
    if   score >= 45: return "CRITICAL"
    elif score >= 25: return "HIGH"
    elif score >= 12: return "MEDIUM"
    elif score >=  5: return "LOW"
    else:             return "SAFE"


def _scan_social_text(text: str) -> tuple[list[dict], float]:
    """
    Run social-specific regex detection on profile text.
    Returns (findings, score).
    """
    findings: list[dict] = []
    score = 0.0
    seen: set[str] = set()

    for ptype, pat in _SOCIAL_PATTERNS.items():
        matches = pat.findall(text)
        unique = list(dict.fromkeys(str(m).strip() for m in matches))
        for val in unique[:3]:   # max 3 per type
            key = f"{ptype}:{val}"
            if key in seen:
                continue
            seen.add(key)
            findings.append({
                "type": ptype,
                "value": val[:200],
                "source": "regex",
                "confidence": None,
            })
            score += _SOCIAL_WEIGHTS.get(ptype, 3)

    return findings, min(round(score, 1), 100.0)


def _run_spacy_social(text: str) -> tuple[list[dict], float]:
    """
    Run spaCy NER but filter out platform entity names.
    Only keeps PERSON, ORG (non-platform), GPE, LOC entities.
    Score boost is small — social NER is context-limited.
    """
    try:
        from backend.services.ai_detection import analyze_with_spacy
        raw_findings = analyze_with_spacy(text)
        filtered = []
        score_boost = 0.0
        for f in raw_findings:
            val = f.get("value", "").strip().lower()
            # Skip platform names
            if val in PLATFORM_IGNORE_ENTITIES:
                continue
            # Skip short generic tokens
            if len(val) < 3:
                continue
            ftype = f.get("type", "")
            # Only keep meaningful social entity types
            if ftype in ("PERSON", "ORG", "GPE", "LOC", "EMAIL", "PHONE"):
                f["source"] = "ai"
                filtered.append(f)
                # Small score boost for real person/org names on profiles
                boost = {"PERSON": 5, "ORG": 3, "GPE": 4, "LOC": 4, "EMAIL": 20, "PHONE": 22}
                score_boost += boost.get(ftype, 2)
        return filtered, min(round(score_boost, 1), 30.0)   # cap NER boost at 30
    except Exception as e:
        logger.warning(f"spaCy NER failed: {e}")
        return [], 0.0


def _run_avatar_vision(avatar_bytes: bytes) -> tuple[dict, list[dict], float]:
    """
    Run vision pipeline on avatar image.
    Returns (vision_data, findings, score_boost).
    Face detection on profile pic gets small boost (normal for social).
    ID card in profile pic gets large boost (very unusual).
    """
    vision_data: dict = {}
    findings: list[dict] = []
    score_boost = 0.0

    try:
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp.write(avatar_bytes)
            tmp_path = tmp.name
        try:
            result = run_vision_analysis(tmp_path, "")
            face_info = result.get("faces", {})
            doc_info  = result.get("document", {})

            vision_data = {
                "face_count": face_info.get("count", 0),
                "is_id_doc":  doc_info.get("is_id_document", False),
                "doc_type":   doc_info.get("doc_type", ""),
            }

            # Face in profile pic — normal, small boost
            if face_info.get("count", 0) > 0:
                score_boost += _SOCIAL_WEIGHTS.get("face_detected", 5)
                findings.append({
                    "type": "face_detected",
                    "value": f"{face_info['count']} face(s) in profile image",
                    "source": "vision",
                    "confidence": 1.0,
                })

            # ID card shown as profile pic — very suspicious, large boost
            if doc_info.get("is_id_document", False):
                score_boost += 35
                findings.append({
                    "type": "id_card_visible",
                    "value": "Profile image appears to be an ID document",
                    "source": "vision",
                    "confidence": 0.9,
                })
        finally:
            os.unlink(tmp_path)
    except Exception as e:
        logger.warning(f"Avatar vision analysis failed: {e}")

    return vision_data, findings, score_boost


# ── Schema ────────────────────────────────────────────────────────────────────

class SocialScanRequest(BaseModel):
    url: str


# ── Pipeline ──────────────────────────────────────────────────────────────────

def _run_social_pipeline(url: str, user_id: int, db: Session) -> dict:
    """
    Social scan pipeline:
    1. Scrape profile metadata only (bio, display name, website, location)
    2. Social-specific regex detection (email, phone, website)
    3. Filtered spaCy NER (no platform names)
    4. Vision AI on avatar (face/ID detection)
    5. Social-appropriate scoring + risk
    6. Persist to DB
    7. Return result dict
    """
    # ── 1. Scrape ──────────────────────────────────────────────────────────────
    profile = scrape_profile(url)
    platform       = profile["platform"]
    title          = profile["title"]
    username       = profile["username"]
    texts          = profile["texts"]
    profile_fields = profile.get("profile_fields", {})

    combined_text = "\n".join(texts).strip()

    # ── 2. Social regex detection on text ─────────────────────────────────────
    findings: list[dict] = []
    score = 0.0

    regex_findings, regex_score = _scan_social_text(combined_text) if combined_text else ([], 0.0)
    findings += regex_findings
    score += regex_score

    # ── 3. Always score PROFILE FIELDS (the key fix — these are scraped but were never scored) ──
    pf = profile_fields

    # Username — every public profile exposes the handle
    if username and username not in ("unknown", ""):
        findings.append({"type": "username", "value": username, "source": "profile"})
        score += _SOCIAL_WEIGHTS["username"]

    # Display name — real name linked to account is extra exposure
    display = pf.get("display_name", "")
    if display and display.lower().strip() != username.lower().strip():
        findings.append({"type": "display_name", "value": display[:100], "source": "profile"})
        score += _SOCIAL_WEIGHTS["display_name"]

    # Location — public location in bio is trackable
    location = pf.get("location", "")
    if location and len(location) > 2:
        findings.append({"type": "location", "value": location[:100], "source": "profile"})
        score += _SOCIAL_WEIGHTS["location"]

    # Website from profile fields (if not already caught by regex)
    website = pf.get("website", "")
    already_found_web = any(f["type"] == "website" for f in findings)
    if website and not already_found_web:
        findings.append({"type": "website", "value": website[:200], "source": "profile"})
        score += _SOCIAL_WEIGHTS["website"]

    # Bio/about text exists — even having a non-empty bio exposes something
    bio = pf.get("bio", "") or pf.get("headline", "")
    if bio and len(bio.strip()) > 10:
        findings.append({"type": "bio", "value": bio[:150], "source": "profile"})
        score += _SOCIAL_WEIGHTS["bio"]

    # Company/org (GitHub-specific)
    company = pf.get("company", "")
    if company and len(company) > 1:
        findings.append({"type": "company", "value": company[:100], "source": "profile"})
        score += _SOCIAL_WEIGHTS["company"]

    # ── 4. spaCy NER (filtered) ────────────────────────────────────────────────
    if combined_text:
        ai_findings, ai_boost = _run_spacy_social(combined_text)
        findings += ai_findings
        score = min(score + ai_boost, 100.0)

    # ── 5. Avatar vision analysis ──────────────────────────────────────────────
    vision_data: dict = {}
    avatar_bytes = download_avatar(profile.get("avatar_url"))
    if avatar_bytes:
        vision_data, vision_findings, vision_boost = _run_avatar_vision(avatar_bytes)
        findings += vision_findings
        score = min(score + vision_boost, 100.0)

    # ── 5.5 Profile Exposure Classification ─────────────────────────────────────
    classification = classify_profile_exposure(platform, profile_fields, findings)
    
    # Apply exposure-specific rules to the score
    if classification["category"] == "public_business":
        # Reduce email/phone weight by 50%
        for f in findings:
            if f["type"] == "email":
                score -= _SOCIAL_WEIGHTS["email"] * 0.5
            elif f["type"] == "phone":
                score -= _SOCIAL_WEIGHTS["phone"] * 0.5
    elif classification["category"] == "personal_exposure":
        # +10 boost
        score += 10.0
    elif classification["category"] == "anonymous":
        # Score stays LOW (under 12.0)
        score = min(score, 11.0)
        
    score = max(0.0, min(round(score, 1), 100.0))
    risk  = _social_risk(score)

    # Add social_classification finding to be persisted and rendered
    findings.append({
        "type": "social_classification",
        "value": f"{classification['label']}: {classification['description']}",
        "source": "profile",
        "confidence": 1.0,
    })

    # ── 6. Persist ScanRecord ──────────────────────────────────────────────────
    safe_title = (title or username or "profile")[:30].replace(" ", "_")
    db_scan = models.ScanRecord(
        filename          = f"{platform}_{safe_title}.txt",
        score             = score,
        risk_level        = risk,
        original_path     = "",
        extracted_text    = combined_text[:5000] if combined_text else str(profile_fields)[:2000],
        source            = f"social_{platform}",
        source_url        = url,
        owner_id          = user_id,
        vision_doc_type   = vision_data.get("doc_type", ""),
        vision_face_count = vision_data.get("face_count", 0),
        vision_is_id_doc  = vision_data.get("is_id_doc", False),
    )
    db.add(db_scan)
    db.flush()

    for f in findings[:60]:
        conf = f.get("confidence") or f.get("ai_confidence")
        db.add(models.Finding(
            type          = f.get("type", "unknown"),
            value         = str(f.get("value", ""))[:500],
            ai_confidence = float(conf) if conf is not None else None,
            ai_label      = f.get("source", "profile"),
            scan_id       = db_scan.id,
        ))

    db.commit()
    db.refresh(db_scan)

    # ── 7. Recommendations ─────────────────────────────────────────────────────
    emails = [f["value"] for f in findings if f.get("type") == "email"]
    phones = [f["value"] for f in findings if f.get("type") == "phone"]
    recs   = generate_recommendations(emails, phones, [], score, risk, findings=findings)

    return {
        "scan_id":       db_scan.id,
        "url":           url,
        "platform":      platform,
        "username":      username,
        "title":         title,
        "score":         score,
        "risk_level":    risk,
        "finding_count": len(findings),
        "findings":      findings[:30],
        "avatar_url":    profile.get("avatar_url"),
        "text_preview":  combined_text[:300] if combined_text else str(profile_fields),
        "vision":        vision_data,
        "recommendations": recs[:10],
        "profile_fields":  profile_fields,
    }


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/scan")
def scan_social_profile(
    body: SocialScanRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    url = body.url.strip()
    if not url.startswith("http"):
        raise HTTPException(status_code=400, detail="URL must start with http:// or https://")

    # Pre-validate: only 5 platforms are supported
    platform = detect_platform(url)
    if platform == "unsupported platform":
        raise HTTPException(
            status_code=422,
            detail="Unsupported platform. Supported: Reddit, Twitter/X, LinkedIn, Instagram, and GitHub profile URLs."
        )

    try:
        return _run_social_pipeline(url, current_user.id, db)
    except Exception as e:
        logger.error(f"Social scan error: {e}", exc_info=True)
        raise HTTPException(status_code=502, detail=f"Scan failed: {str(e)[:200]}")


@router.get("/history")
def social_history(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    scans = (
        db.query(models.ScanRecord)
        .filter(
            models.ScanRecord.owner_id == current_user.id,
            models.ScanRecord.source.like("social_%"),
        )
        .order_by(models.ScanRecord.id.desc())
        .limit(50)
        .all()
    )
    return [
        {
            "scan_id":    s.id,
            "filename":   s.filename,
            "source":     s.source,
            "source_url": s.source_url,
            "score":      s.score,
            "risk_level": s.risk_level,
            "created_at": str(s.created_at) if hasattr(s, "created_at") else "",
        }
        for s in scans
    ]


@router.get("/history/{scan_id}")
def social_detail(
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

    findings = [
        {"type": f.type, "value": f.value, "confidence": f.ai_confidence, "source": f.ai_label or "regex"}
        for f in scan.findings
    ]
    emails = [f["value"] for f in findings if f["type"] == "email"]
    phones = [f["value"] for f in findings if f["type"] == "phone"]
    recs = generate_recommendations(emails, phones, [], scan.score, scan.risk_level, findings=findings)

    return {
        "scan_id":    scan.id,
        "filename":   scan.filename,
        "source":     scan.source,
        "source_url": scan.source_url,
        "score":      scan.score,
        "risk_level": scan.risk_level,
        "findings":   findings,
        "finding_count": len(findings),
        "extracted_text_preview": (scan.extracted_text or "")[:400],
        "vision_doc_type":   scan.vision_doc_type,
        "vision_face_count": scan.vision_face_count,
        "vision_is_id_doc":  scan.vision_is_id_doc,
        "recommendations": recs,
    }


@router.delete("/history/{scan_id}")
def delete_social_scan(
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
    db.query(models.Finding).filter(models.Finding.scan_id == scan_id).delete()
    db.delete(scan)
    db.commit()
    return {"message": f"Scan {scan_id} deleted"}


@router.delete("/history")
def delete_all_social_history(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Delete ALL social scan history for the current user."""
    scans = (
        db.query(models.ScanRecord)
        .filter(
            models.ScanRecord.owner_id == current_user.id,
            models.ScanRecord.source.like("social_%"),
        )
        .all()
    )
    count = 0
    for scan in scans:
        db.query(models.Finding).filter(models.Finding.scan_id == scan.id).delete()
        db.delete(scan)
        count += 1
    db.commit()
    return {"message": f"Deleted {count} social scan(s)"}


@router.delete("/history-purge-legacy")
def purge_legacy_social_scans(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """
    Purge only the old false-positive social scans (score == 100 or risk == CRITICAL
    that came from the broken v1 scanner).  Correct scans are preserved.
    """
    legacy = (
        db.query(models.ScanRecord)
        .filter(
            models.ScanRecord.owner_id == current_user.id,
            models.ScanRecord.source.like("social_%"),
            models.ScanRecord.score >= 75,   # v1 false CRITICAL threshold
        )
        .all()
    )
    count = 0
    for scan in legacy:
        db.query(models.Finding).filter(models.Finding.scan_id == scan.id).delete()
        db.delete(scan)
        count += 1
    db.commit()
    return {"message": f"Purged {count} legacy false-positive social scan(s)"}

