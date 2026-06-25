from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from backend.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)

    scans = relationship("ScanRecord", back_populates="owner")

class ScanRecord(Base):
    __tablename__ = "scans"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String)
    upload_date = Column(DateTime, default=datetime.utcnow)
    score = Column(Float)
    risk_level = Column(String)
    original_path = Column(String)
    blurred_path = Column(String, nullable=True)
    extracted_text = Column(String, nullable=True)
    source = Column(String, default="file")        # file | url | screen | social
    source_url = Column(String, nullable=True)     # for URL/social scans
    
    owner_id = Column(Integer, ForeignKey("users.id"))
    owner = relationship("User", back_populates="scans")
    
    findings = relationship("Finding", back_populates="scan")

    # Phase 6 — Vision detection results
    vision_doc_type    = Column(String,  nullable=True)   # e.g. aadhaar_card, bank_statement
    vision_face_count  = Column(Integer, nullable=True, default=0)
    vision_is_id_doc   = Column(Boolean, nullable=True, default=False)

    # AI document classifier results — persisted for GET /scans/{id}
    ai_doc_type_label  = Column(String,  nullable=True)   # e.g. "Project Report / Academic Document"
    ai_doc_confidence  = Column(Float,   nullable=True)   # 0.0–1.0

class Finding(Base):
    __tablename__ = "findings"

    id = Column(Integer, primary_key=True, index=True)
    type = Column(String)                          # email, phone, password, aadhaar, etc.
    value = Column(String)
    ai_confidence = Column(Float, nullable=True)   # 0.0–1.0 from AI scorer
    ai_label = Column(String, nullable=True)       # HIGH_CONFIDENCE | MEDIUM_CONFIDENCE | LOW_CONFIDENCE
    
    scan_id = Column(Integer, ForeignKey("scans.id"))
    scan = relationship("ScanRecord", back_populates="findings")


# Phase 8 — Screenshot Monitoring Sessions
class ScreenshotSession(Base):
    __tablename__ = "screenshot_sessions"

    id            = Column(Integer, primary_key=True, index=True)
    started_at    = Column(DateTime, default=datetime.utcnow)
    ended_at      = Column(DateTime, nullable=True)
    owner_id      = Column(Integer, ForeignKey("users.id"))
    alert_count   = Column(Integer, default=0)
    scan_count    = Column(Integer, default=0)
    status        = Column(String, default="active")  # active | stopped

    owner  = relationship("User")
    alerts = relationship("ScreenshotAlert", back_populates="session")


class ScreenshotAlert(Base):
    __tablename__ = "screenshot_alerts"

    id          = Column(Integer, primary_key=True, index=True)
    session_id  = Column(Integer, ForeignKey("screenshot_sessions.id"))
    timestamp   = Column(DateTime, default=datetime.utcnow)
    score       = Column(Float)
    risk_level  = Column(String)                      # LOW/MEDIUM/HIGH/CRITICAL
    finding_types = Column(String)                    # JSON list of detected types
    image_path  = Column(String, nullable=True)       # saved screenshot path
    scan_id     = Column(Integer, ForeignKey("scans.id"), nullable=True)

    session = relationship("ScreenshotSession", back_populates="alerts")
    scan    = relationship("ScanRecord")


# Phase 13 — Batch Screenshot Scanner Jobs
class BatchScanJob(Base):
    __tablename__ = "batch_scan_jobs"

    id           = Column(Integer, primary_key=True, index=True)
    owner_id     = Column(Integer, ForeignKey("users.id"))
    label        = Column(String, default="")
    created_at   = Column(DateTime, default=datetime.utcnow)
    file_count   = Column(Integer, default=0)
    alert_count  = Column(Integer, default=0)
    avg_score    = Column(Float,   default=0.0)
    max_score    = Column(Float,   default=0.0)
    highest_risk = Column(String,  default="SAFE")
    results_json = Column(String,  default="[]")   # JSON list of per-file results
    errors_json  = Column(String,  default="[]")   # JSON list of errors

    owner = relationship("User")
