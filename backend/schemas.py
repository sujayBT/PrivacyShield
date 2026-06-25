from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class UserBase(BaseModel):
    username: str

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: int
    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class FindingBase(BaseModel):
    type: str
    value: str

class Finding(FindingBase):
    id: int
    ai_confidence: Optional[float] = None
    ai_label: Optional[str] = None
    class Config:
        from_attributes = True

class ScanBase(BaseModel):
    filename: str
    score: float
    risk_level: str

class ScanRecord(ScanBase):
    id: int
    upload_date: datetime
    original_path: str
    blurred_path: Optional[str] = None
    extracted_text: Optional[str] = None
    source: Optional[str] = "file"
    source_url: Optional[str] = None
    findings: List[Finding] = []
    # Phase 6 — Vision
    vision_doc_type:   Optional[str]  = None
    vision_face_count: Optional[int]  = 0
    vision_is_id_doc:  Optional[bool] = False
    # AI Document Classification (mDeBERTa)
    ai_doc_type_label:  Optional[str]   = None   # e.g. "Project Report / Academic Document"
    ai_doc_confidence:  Optional[float] = None   # 0.0-1.0

    class Config:
        from_attributes = True
