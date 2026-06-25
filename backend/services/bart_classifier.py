"""
backend/services/bart_classifier.py
=====================================
DEPRECATED — kept for backward compatibility only.

All callers should migrate to:
    from backend.ai.document_classifier import classify_document

This module now delegates entirely to the model-agnostic abstraction layer.
The underlying model is controlled by MODEL_NAME in .env / environment.
"""
from backend.ai.document_classifier import (
    classify_document as _classify,
    get_classifier_info,
)


def classify_document_bart(text: str) -> dict:
    """Deprecated. Use backend.ai.document_classifier.classify_document instead."""
    result = _classify(text)
    # Translate to legacy field names for any old callers
    return {
        "document_type": result["document_type"],
        "label":         result["label"],
        "score_boost":   result["score_boost"],
        "confidence":    "HIGH" if result["confidence"] >= 0.70
                         else "MEDIUM" if result["confidence"] >= 0.45
                         else "LOW",
        "bart_score":    result["confidence"],
        "bart_label":    result["label"],
        "method":        result["method"],
    }


def get_bart_info() -> dict:
    """Deprecated. Use backend.ai.document_classifier.get_classifier_info instead."""
    return get_classifier_info()
