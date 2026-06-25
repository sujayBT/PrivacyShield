"""
backend/config.py
=================
Central configuration for PrivacyShield backend.

To change the document classifier model, set the environment variable:
    MODEL_NAME=facebook/bart-large-mnli

Or edit .env in the project root. No code changes required.

Supported models (any HuggingFace zero-shot-classification model):
    MoritzLaurer/mDeBERTa-v3-base-mnli-xnli  ← default (smaller, faster)
    facebook/bart-large-mnli                  ← alternative
    MoritzLaurer/DeBERTa-v3-large-mnli        ← higher accuracy
    any custom HuggingFace zero-shot model
"""
from __future__ import annotations

import os
from pathlib import Path

# ── Load .env file if present (no external dependency — pure stdlib) ───────────
def _load_dotenv(env_path: Path) -> None:
    """Minimal .env parser — supports KEY=value and KEY="value" formats."""
    if not env_path.exists():
        return
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            # Only set if not already in environment (env vars take priority)
            if key and key not in os.environ:
                os.environ[key] = val

# Look for .env in project root (one level above backend/)
_PROJECT_ROOT = Path(__file__).parent.parent
_load_dotenv(_PROJECT_ROOT / ".env")

# ── Document Classifier Configuration ─────────────────────────────────────────

#: The HuggingFace model to use for zero-shot document classification.
#: Override via environment variable MODEL_NAME or .env file.
CLASSIFIER_MODEL: str = os.environ.get(
    "MODEL_NAME",
    "MoritzLaurer/mDeBERTa-v3-base-mnli-xnli",   # default
)

#: Hard timeout (seconds) for AI inference before falling back to keyword classifier.
CLASSIFIER_TIMEOUT: float = float(os.environ.get("CLASSIFIER_TIMEOUT", "2.0"))

#: Max characters of document text fed to the model (fewer = faster).
CLASSIFIER_SNIPPET_CHARS: int = int(os.environ.get("CLASSIFIER_SNIPPET_CHARS", "512"))

# ── Uploads, Reports, and Screenshots directories ─────────────────────────────
_data_dir = os.environ.get("PRIVACY_DATA_DIR", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if os.environ.get("PRIVACY_DATA_DIR"):
    UPLOAD_DIR = os.path.join(_data_dir, "uploads")
    REPORTS_DIR = os.path.join(_data_dir, "reports")
    SCREENSHOT_DIR = os.path.join(_data_dir, "screenshots")
else:
    # Dev mode
    UPLOAD_DIR = os.path.join(str(_PROJECT_ROOT), "backend", "uploads")
    REPORTS_DIR = os.path.join(str(_PROJECT_ROOT), "backend", "reports")
    SCREENSHOT_DIR = os.path.join(str(_PROJECT_ROOT), "backend", "screenshots")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(REPORTS_DIR, exist_ok=True)
os.makedirs(SCREENSHOT_DIR, exist_ok=True)
