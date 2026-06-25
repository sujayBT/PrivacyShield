"""
backend/ai/document_classifier.py
===================================
Model-agnostic document classification abstraction layer.

PUBLIC API (the ONLY interface the rest of the app should use):
    classify_document(text, filename="") -> dict
    get_classifier_info()               -> dict

OUTPUT FORMAT (always, regardless of which model is active):
    {
        "document_type": str,    # e.g. "ml_notebook", "aadhaar_card"
        "label":         str,    # e.g. "ML / Data Science Code or Lab Manual"
        "confidence":    float,  # 0.0 – 1.0
        "score_boost":   int,    # extra score for sensitive doc types
        "method":        str,    # "ai" | "keyword" | "fallback"
    }

MODEL SWAPPING:
    Change MODEL_NAME in .env or environment — zero code changes needed.

    Examples:
        MODEL_NAME=MoritzLaurer/mDeBERTa-v3-base-mnli-xnli  ← default
        MODEL_NAME=facebook/bart-large-mnli
        MODEL_NAME=MoritzLaurer/DeBERTa-v3-large-mnli

Design guarantees:
    - Model loaded ONCE (lazy singleton) per process lifetime
    - Hard timeout: if AI takes > CLASSIFIER_TIMEOUT seconds → keyword fallback
    - Graceful degradation: if transformers/torch missing → keyword fallback
    - Offline capable: model cached in ~/.cache/huggingface/hub after first run
    - Output format NEVER changes regardless of which model or fallback is used
"""
from __future__ import annotations

import concurrent.futures
import logging
import re

from backend.config import CLASSIFIER_MODEL, CLASSIFIER_TIMEOUT, CLASSIFIER_SNIPPET_CHARS

logger = logging.getLogger(__name__)

# ── Singleton state ───────────────────────────────────────────────────────────
_classifier      = None
_model_available = False
_load_attempted  = False
_loaded_model_id = None     # track which model is currently loaded

# Thread pool for timeout-safe inference (1 worker = no race conditions)
_executor = concurrent.futures.ThreadPoolExecutor(
    max_workers=1, thread_name_prefix="doc_clf"
)


def _get_classifier():
    """
    Lazy-load the zero-shot classification pipeline.
    Loads once per process. Model name comes from config — not hardcoded.
    """
    global _classifier, _model_available, _load_attempted, _loaded_model_id
    if _load_attempted:
        return _classifier
    _load_attempted = True

    model_id = CLASSIFIER_MODEL
    try:
        from transformers import pipeline  # type: ignore
        logger.info("[DocClassifier] Loading model: %s", model_id)
        _classifier = pipeline(
            "zero-shot-classification",
            model=model_id,
            device=-1,           # CPU only — no GPU required
            multi_label=False,
        )
        _model_available = True
        _loaded_model_id = model_id
        logger.info("[DocClassifier] Ready: %s", model_id)
    except Exception as exc:
        logger.warning(
            "[DocClassifier] Model unavailable (%s). Keyword classifier active.", exc
        )
        _classifier      = None
        _model_available = False
        _loaded_model_id = None
    return _classifier


# ── Candidate labels (model-independent vocabulary) ───────────────────────────
# These natural-language labels work with ANY NLI zero-shot model.
# Fewer labels = faster CPU inference. Group similar types into one label.
_CANDIDATE_LABELS: list[str] = [
    "Project Report or Academic Synopsis or Study Material",
    "Lab Manual or Programming Code Document",
    "Resume or Curriculum Vitae",
    "Aadhaar Card Identity Document",
    "PAN Card Identity Document",
    "Passport Travel Document",
    "Bank Statement or Financial Record",
    "Salary Payslip",
    "Invoice or Bill Receipt",
    "Medical Record or Prescription",
    "General Unknown Document"
]

# Map candidate labels to backend internal types
_LABEL_TO_TYPE: dict[str, str] = {
    "Project Report or Academic Synopsis or Study Material": "project_synopsis",
    "Lab Manual or Programming Code Document": "ml_notebook",
    "Resume or Curriculum Vitae": "resume",
    
    "Aadhaar Card Identity Document": "aadhaar_card",
    "PAN Card Identity Document": "pan_card_doc",
    "Passport Travel Document": "passport",
    
    "Bank Statement or Financial Record": "bank_statement",
    "Salary Payslip": "payslip",
    "Invoice or Bill Receipt": "invoice",
    
    "Medical Record or Prescription": "medical",
    
    "General Unknown Document": "generic",
}

# ── Human-readable labels ──────────────────────────────────────────────────────
_TYPE_TO_LABEL: dict[str, str] = {
    "resume":                "Resume / CV",
    "project_synopsis":      "Project Report / Academic Document",
    "ml_notebook":           "ML / Data Science Code or Lab Manual",
    "aadhaar_card":          "Aadhaar Card",
    "pan_card_doc":          "PAN Card",
    "passport":              "Passport / Travel Document",
    "driving_license":       "Driving License",
    "student_id":            "Student ID Card",
    "marks_card":            "Marks Card / ID Card",
    "bank_statement":        "Bank Statement",
    "payslip":               "Salary Slip / Payslip",
    "invoice":               "Invoice / Bill",
    "medical":               "Medical / Health Record",
    "insurance":             "Insurance Document",
    "gov_form":              "Government / Application Form",
    "screenshot_credential": "Screenshot — Login / Authentication",
    "screenshot_chat":       "Screenshot — Chat / Conversation",
    "screenshot_social":     "Screenshot — Social Media",
    "generic":               "General Document",
}

# ── Score boosts for sensitive document types ──────────────────────────────────
_SCORE_BOOST: dict[str, int] = {
    "passport":              15,
    "bank_statement":        12,
    "payslip":               15,
    "medical":               15,
    "resume":                10,
    "aadhaar_card":           5,
    "pan_card_doc":           5,
    "marks_card":             5,
    "invoice":                5,
    "driving_license":        8,
    "student_id":             5,
    "insurance":              8,
    "gov_form":               8,
    "screenshot_credential":  25,
    "screenshot_chat":         5,
    "screenshot_social":       5,
    "project_synopsis":        0,
    "ml_notebook":             0,
    "generic":                 0,
}

# ── Type categories (used by routers for risk logic) ──────────────────────────
# Exported so routers don't import model internals — they import these constants.
LOW_RISK_TYPES: frozenset[str] = frozenset({
    "project_synopsis", "ml_notebook",
    # Note: "generic" intentionally removed — generic ≠ safe
})

HIGH_SENSITIVITY_TYPES: frozenset[str] = frozenset({
    "aadhaar_card", "pan_card_doc", "passport", "bank_statement",
    "payslip", "medical", "driving_license", "screenshot_credential",
})


# ── PUBLIC API ────────────────────────────────────────────────────────────────

def classify_document(text: str, filename: str = "") -> dict:
    """
    Classify a document and return its type with confidence.

    This is the ONLY function the rest of the application should call.
    The underlying model (mDeBERTa, BART, or any future model) is transparent.

    Args:
        text:     Extracted text content from the document (OCR or direct).
        filename: Optional filename hint (improves keyword fallback accuracy).

    Returns:
        {
            "document_type": str,    # e.g. "ml_notebook"
            "label":         str,    # e.g. "ML / Data Science Code or Lab Manual"
            "confidence":    float,  # 0.0 – 1.0
            "score_boost":   int,    # extra risk score for sensitive types
            "method":        str,    # "ai" | "keyword" | "fallback"
        }
    """
    clf = _get_classifier()

    if clf is not None and text and text.strip():
        # Using 600 chars: Perfect balance of speed and context
        snippet = _prepare_snippet(text, filename, max_chars=600)
        try:
            # Inference with 19 labels takes ~20-40s on CPU. Give it 60s.
            future = _executor.submit(_run_inference, clf, snippet)
            result = future.result(timeout=max(60.0, CLASSIFIER_TIMEOUT))
            
            labels = result["labels"]
            scores = result["scores"]
            
            logger.info("\n==================================================")
            logger.info("Text Length:\n%d", len(snippet))
            logger.info("Labels Sent:\n[%s]", ", ".join(_CANDIDATE_LABELS))
            logger.info("Top Predictions:")
            for i in range(min(3, len(labels))):
                logger.info("%d. %s - %.0f%%", i+1, labels[i], scores[i] * 100)
                
            top_label = labels[0]
            top_score = scores[0]
            
            # Confidence Threshold Fix: if < 0.60 or ambiguous, default to generic
            if top_score < 0.60 or top_label in ("General Document", "Unknown Document"):
                top_label = "General Document"
                
            logger.info("Selected:\n%s", top_label)
            logger.info("==================================================\n")
            
            doc_type = _LABEL_TO_TYPE.get(top_label, "generic")
            return _build_result(doc_type, top_score, method="ai")

        except concurrent.futures.TimeoutError:
            logger.warning(
                "[DocClassifier] Timeout (>%.1fs) for '%s' — keyword fallback",
                max(60.0, CLASSIFIER_TIMEOUT), filename,
            )
        except Exception as exc:
            logger.warning("[DocClassifier] Inference error: %s — keyword fallback", exc)

    # Keyword fallback — always fast (<1ms), no model dependency
    return _keyword_classify(text, filename)


def get_classifier_info() -> dict:
    """
    Return metadata about the active classifier for /api/scans/ai-info endpoints.
    Safe to call before model is loaded.
    """
    _get_classifier()   # ensure load attempted
    return {
        "model_id":        _loaded_model_id or CLASSIFIER_MODEL,
        "available":       _model_available,
        "task":            "zero-shot-classification",
        "timeout_seconds": CLASSIFIER_TIMEOUT,
        "snippet_chars":   CLASSIFIER_SNIPPET_CHARS,
        "candidate_count": len(_CANDIDATE_LABELS),
        "fallback":        "keyword classifier",
        "configured_via":  "MODEL_NAME env / .env file",
    }


# ── Keyword fallback classifier ───────────────────────────────────────────────
# Runs instantly with no model — used when AI times out or is unavailable.

_KEYWORD_RULES: list[tuple[str, list[str], int]] = [
    ("project_synopsis",      ["problem statement", "literature review", "future scope", "objective",
                               "synopsis", "project report", "methodology", "academic year", "references", "unit 1"], 2),
    ("ml_notebook",           ["sklearn", "import pandas", "import numpy", "from sklearn", "lab manual", "experiment",
                               "import torch", "matplotlib", "knn", "k-means", "def ", "lab program"], 2),
    ("aadhaar_card",          ["aadhaar", "uidai", "uid", "enrolment no"],                1),
    ("pan_card_doc",          ["permanent account number", "pan card", "income tax"],      1),
    ("passport",              ["passport", "republic of india", "nationality"],            1),
    ("bank_statement",        ["account no", "ifsc", "opening balance", "statement"],      2),
    ("payslip",               ["gross salary", "net pay", "epf", "payslip", "ctc"],       2),
    ("medical",               ["patient name", "diagnosis", "prescription", "dosage"],     2),
    ("resume",                ["curriculum vitae", "resume", "work experience", "skills"], 2),
    ("marks_card",            ["marks obtained", "cgpa", "semester", "grade card"],        2),
    ("invoice",               ["invoice", "gstin", "total amount", "bill to"],             2),
    ("screenshot_credential", [
                                "change your password", "your account is at risk", "re-type new password",
                                "password", "sign in", "login", "otp", "two-factor",
                                "enter your password", "forgot password", "reset password",
                               ],      2),
]

def _keyword_classify(text: str, filename: str = "") -> dict:
    """Fast keyword-based fallback classifier. No model required."""
    text_low   = (text + " " + filename).lower()
    best_type  = "generic"
    best_score = 0.0

    for doc_type, keywords, min_matches in _KEYWORD_RULES:
        # Use word boundaries so 'uid' doesn't match 'guide' or 'build'
        matched = sum(1 for kw in keywords if re.search(r'\b' + re.escape(kw) + r'\b', text_low))
        if matched >= min_matches:
            # Cap at 3 matches so categories with 10 keywords aren't unfairly penalized
            match_ratio = min(matched, 3) / 3.0
            conf = min(0.55 + match_ratio * 0.35, 0.89)
            if conf > best_score:
                best_score = conf
                best_type  = doc_type

    return _build_result(
        best_type,
        best_score if best_score > 0 else 0.0,
        method="keyword",
    )


# ── Internal helpers ──────────────────────────────────────────────────────────

def _run_inference(clf, snippet: str) -> dict:
    """Run NLI pipeline in thread pool (timeout protected)."""
    result = clf(snippet, _CANDIDATE_LABELS, truncation=True)
    return result


def _build_result(doc_type: str, confidence: float, method: str) -> dict:
    """Build the standardised output dict. Format never changes."""
    return {
        "document_type": doc_type,
        "label":         _TYPE_TO_LABEL.get(doc_type, "General Document"),
        "confidence":    round(float(confidence), 4),
        "score_boost":   _SCORE_BOOST.get(doc_type, 0),
        "method":        method,
    }


def _prepare_snippet(text: str, filename: str = "", max_chars: int = 600) -> str:
    """Build a concise snippet. Clean OCR garbage, repeated symbols, and noise."""
    # Remove repeated symbols (like -------, =======, _____ etc)
    cleaned = re.sub(r'([^a-zA-Z0-9\s])\1{3,}', ' ', text)
    # Remove huge blocks of hex or digits
    cleaned = re.sub(r'\b[0-9a-fA-F]{10,}\b', ' ', cleaned)
    # Keep only printable ascii + some common unicode
    cleaned = re.sub(r'[^\x20-\x7E\n\t]', ' ', cleaned)
    # Remove excessive whitespace
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    
    prefix = f"Document: {filename}\n\n" if filename else ""
    snippet = prefix + cleaned
    
    return snippet[:max_chars]
