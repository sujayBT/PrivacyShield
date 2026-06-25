"""
Phase 3 — AI-Based Sensitive Content Detection (spaCy NER)
===========================================================
Detects PII that regex CANNOT find:
  PERSON    → full person names
  GPE/LOC   → locations, addresses, countries, cities
  ORG       → organization / company names
  CARDINAL  → potential numeric IDs
  DATE      → date-of-birth candidates
  MONEY     → financial amounts

Each finding carries:
  method:     "ai"
  confidence: float 0.0–1.0
  weight:     int (for scoring contribution)

Also enriches existing regex findings with confidence scores.
"""

from __future__ import annotations
import re
import math
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ─── spaCy singleton ─────────────────────────────────────────────────────────

_nlp: Optional[object] = None
_SPACY_AVAILABLE = False

def _get_nlp():
    global _nlp, _SPACY_AVAILABLE
    if _nlp is not None:
        return _nlp
    try:
        import spacy
        _nlp = spacy.load("en_core_web_sm")
        _SPACY_AVAILABLE = True
        logger.info("spaCy en_core_web_sm loaded successfully")
        return _nlp
    except Exception as e:
        logger.warning("spaCy not available: %s", e)
        _SPACY_AVAILABLE = False
        return None


# ─── Entity → Finding Type Mapping ───────────────────────────────────────────

_ENTITY_MAP = {
    "PERSON":   ("person_name",  20),
    "GPE":      ("location",     12),
    "LOC":      ("location",     12),
    "ORG":      ("organization",  8),
    "CARDINAL": ("id_number",    18),
    "DATE":     ("date",         10),
    "MONEY":    ("financial",    15),
    "NORP":     ("demographic",   6),
}

_SKIP_LABELS = {
    "TIME", "PERCENT", "QUANTITY", "ORDINAL",
    "WORK_OF_ART", "FAC", "PRODUCT", "EVENT",
    "LANGUAGE", "LAW",
    # ORG is disabled — produces too many false positives (algorithm names,
    # document keywords, UI text) and is not a reliable privacy signal.
    "ORG",
}

_MIN_TOKEN_LEN = 3

# Common OCR / UI noise words that spaCy often tags as entities
# This is a comprehensive list covering UI labels, navigation, common words, and OCR fragments.
_FP_WORDS = {
    # UI buttons and navigation
    "enter", "click", "submit", "button", "home", "menu", "scan",
    "upload", "file", "image", "photo", "document", "page", "type",
    "email", "phone", "user", "name", "privacy", "tool", "mode",
    "light", "dark", "password", "login", "logout", "save", "cancel",
    "next", "back", "error", "close", "open", "new", "yes", "no",
    # Days and months (always generic)
    "january", "february", "march", "april", "may", "june", "july",
    "august", "september", "october", "november", "december",
    "monday", "tuesday", "wednesday", "thursday", "friday",
    "saturday", "sunday", "am", "pm", "ok", "na", "none",
    # Academic/project noise words
    "generate", "deliverables", "streamlit", "documentation", "marks",
    "grade", "motivation", "background", "engine", "confidence", "property",
    "intellectual", "readiness", "score", "tracking", "anxiety", "signals",
    "encouragement", "feedback", "week", "month", "year", "today", "tomorrow",
    "yesterday", "relative", "temporal",
    # Screenshot / phone UI noise words
    "right", "left", "done", "edit", "delete", "view", "share", "copy",
    "search", "filter", "sort", "import", "export", "refresh", "reload",
    "settings", "profile", "account", "security", "privacy", "help",
    "support", "about", "terms", "policy", "sign", "register", "forgot",
    "remember", "notification", "message", "inbox", "alert", "reminder",
    "camera", "gallery", "contact", "contacts", "call", "missed", "received",
    "wifi", "bluetooth", "signal", "battery", "volume", "rotate", "lock",
    "unlock", "airplane", "screen", "touch", "swipe", "scroll", "select",
    "check", "enable", "disable", "turn", "start", "stop", "pause", "resume",
    "connect", "disconnect", "sync", "backup", "restore", "update", "install",
    "uninstall", "version", "build", "release", "beta", "alpha",
    # Common English words that look like entities
    "access", "allow", "block", "report", "manage", "control", "monitor",
    "track", "record", "status", "state", "level", "option", "options",
    "choice", "result", "results", "detail", "details", "info", "information",
    "content", "data", "value", "values", "item", "items", "list", "section",
    "group", "already", "always", "never", "often", "sometimes", "usually",
    "every", "each", "both", "either", "neither", "other", "same", "different",
    "similar", "old", "recent", "latest", "first", "second", "third", "last",
    "final", "also", "only", "just", "even", "still", "again", "once",
    # Tech/OS/browser noise
    "android", "windows", "linux", "macos", "chrome", "firefox", "safari",
    "edge", "opera", "browser", "internet", "online", "offline", "website",
    "portal", "platform", "cloud", "app", "apps", "application",
    # OCR fragments commonly detected from screenshots (including keyboard/Gboard spacebars and layout noise)
    "paya", "english", "hindi", "french", "spanish", "se", "paise", "payase", "pay", "space", "spacebar",
    "kannada", "telugu", "tamil", "marathi", "bengali", "gujarati", "punjabi", "malayalam", "qwerty",
    "notification bar", "status bar", "action bar",
    # Social media platform names — never real person names in this context
    "facebook", "instagram", "twitter", "whatsapp", "telegram", "snapchat", "youtube",
    "linkedin", "reddit", "tiktok", "pinterest", "discord",
    # ML / Data-Science pipeline words — single words that appear as entities in code/notebooks
    "load", "dataset", "breast", "cancer", "cluster", "labels", "label",
    "reduce", "dimensions", "neighbors", "nearest", "features", "feature",
    "separate", "split", "train", "test", "accuracy", "predict", "fit",
    "transform", "pipeline", "normalize", "standardize", "encode", "decode",
    "batch", "epoch", "loss", "gradient", "optimizer", "confusion", "matrix",
    "precision", "recall", "fscore", "auc", "roc", "decomposition", "kernel",
    "regression", "classification", "clustering", "extraction", "embedding",
    "visualization", "metrics", "cross", "validation", "parameters", "hyperparameter",
    "initialize", "preprocessing", "postprocessing", "inference",
}


def _confidence(text: str, label: str) -> float:
    """
    Estimate NER confidence 0.0–1.0:
    - Longer = more confident
    - Multi-word = bonus
    - Known false-positive = 0
    """
    stripped = text.strip()
    if stripped.lower() in _FP_WORDS:
        return 0.0
    if len(stripped) < _MIN_TOKEN_LEN:
        return 0.0
    # Reject if the entity is a single short word (spaCy over-tags)
    if len(stripped.split()) == 1 and len(stripped) < 5:
        return 0.0

    words = [w for w in stripped.split() if len(w) >= 2]
    length_score = min(len(stripped) / 22.0, 0.8)
    multi_word_bonus = 0.22 if len(words) >= 2 else 0.0

    # Extra boost for person names (first + last name pattern)
    if label == "PERSON" and len(words) >= 2:
        multi_word_bonus = 0.3

    return round(min(length_score + multi_word_bonus, 1.0), 2)


def _is_ocr_garbage_entity(value: str) -> bool:
    """
    Reject entity values that look like OCR garbage / noise.
    Covers WhatsApp screenshots, scanned documents, and noisy assignment PDFs.
    """
    v = value.strip()
    if not v or len(v) < 2:
        return True

    # Mostly non-alphanumeric
    alpha_ratio = sum(1 for c in v if c.isalnum()) / max(len(v), 1)
    if alpha_ratio < 0.4:
        return True

    # 4+ consecutive repeated characters
    if re.search(r'(.)\1{3,}', v):
        return True

    # Looks like a random symbol dump
    if re.match(r'^[\W_]{2,}$', v):
        return True

    # Contains control characters
    if re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', v):
        return True

    # Contains OCR artifact characters that never appear in real names
    if re.search(r'[|:\\{}\[\]<>@#$%^*+=`~]', v):
        return True

    # First letter is lowercase — real names start with uppercase
    if v[0].islower():
        return True

    # Contains digits mixed with letters in a non-name pattern
    if re.search(r'\d', v) and not re.search(r'(19|20)\d{2}', v):
        return True

    words = [w for w in re.findall(r'[a-zA-Z]+', v) if w]

    # All words ≤3 characters — OCR fragments like "EE Sie", "ek lok"
    if words and all(len(w) <= 3 for w in words):
        return True

    # Contains only uppercase abbreviations with spaces (e.g. "EE NPS ABC")
    if re.match(r'^[A-Z]{1,4}(\s+[A-Z]{1,4})+$', v):
        return True

    # ── WhatsApp / App UI false-positive filters ────────────────────────────────
    # Truncated words ending mid-syllable (e.g. "Applica", "Ledton", "Jooeare")
    # Real names don't end in these common truncation suffixes from WhatsApp UI
    _TRUNCATED_SUFFIXES = (
        'ica', 'ton', 'eare', 'tion', 'ting', 'iver', 'ator', 'ware',
        'orm', 'ork', 'ess', 'ment', 'ance', 'ence', 'ling', 'ered',
    )
    # Only apply truncation check when combined with a suspicious first word
    _APP_FIRST_WORDS = {
        'variovs', 'variou', 'vario', 'conn', 'cosm', 'appl', 'goog',
        'whats', 'micro', 'amazo', 'faceb', 'twitt', 'insta', 'telgr',
        'notif', 'setti', 'dialer', 'messag', 'camer', 'galery', 'galer',
    }
    if words:
        first_word_lower = words[0].lower()
        last_word_lower  = words[-1].lower()
        # If first word looks like a truncated app/platform name
        if first_word_lower in _APP_FIRST_WORDS:
            return True
        # If last word ends in a known truncation suffix AND is not a real surname
        if len(words) >= 2 and any(last_word_lower.endswith(s) for s in _TRUNCATED_SUFFIXES):
            # Allow common real Indian surnames ending in these: Sharma, Verma, etc.
            _REAL_SURNAME_ENDINGS = ('arma', 'erma', 'umar', 'ingh', 'atre', 'ance', 'erce')
            if not any(last_word_lower.endswith(s) for s in _REAL_SURNAME_ENDINGS):
                return True

    # Reject names that appear in browser tab-title patterns like "Sujay Bhat - Facebook"
    # These are pulled from the browser URL/tab bar in screenshots, not real document data.
    _SOCIAL_PLATFORMS = {
        'facebook', 'instagram', 'twitter', 'whatsapp', 'telegram', 'snapchat',
        'youtube', 'linkedin', 'reddit', 'tiktok', 'pinterest', 'discord',
        'google', 'gmail', 'outlook', 'yahoo', 'hotmail',
    }
    # Check if value appears in a line that ends with "- <PlatformName>" (browser tab title)
    import re as _re_in_fn
    for line in v.replace('\n', '|').split('|'):
        line_low = line.strip().lower()
        for plat in _SOCIAL_PLATFORMS:
            if line_low.endswith(f'- {plat}') or line_low.endswith(f'– {plat}'):
                return True

    # Known WhatsApp / Android UI strings that NER wrongly tags as persons
    _KNOWN_UI_STRINGS = {
        'variovs applica', 'conn ledton', 'cosm jooeare', 'various applications',
        'connection ledton', 'cosmic jooeare', 'whatsapp', 'google', 'android',
        'samsung', 'settings', 'notifications', 'battery', 'camera', 'gallery',
        'ball bl', 'foe ball bl', 'foe ball', 'ball', 'bl'
    }
    if v.lower() in _KNOWN_UI_STRINGS:
        return True

    return False


# ─── NER Analysis (new PII types only) ───────────────────────────────────────

# Set of academic headings and campus tags to drop from NER
_EXCLUDE_NER_VALUES = {
    # Campus tags / location placeholders
    "vidyagiri", "sdmit", "ujire", "dharmasthala", "manjunatha",
    # Academic/report headers and noise
    "problem statement", "literature survey", "future scope", "technical specifications",
    "project planning", "abstract", "synopsis", "references", "key concepts", "introduction",
    "applications", "conclusion", "methodology", "acknowledgement", "bachelor of engineering",
    "master of technology", "college of engineering", "computer science", "information science",
    "visvesvaraya technological university", "vtu", "semester", "project report", "academic year",
    "page", "figure", "table", "graph", "chart", "diagram", "appendix", "index",
    "problem", "develop", "technical", "specifications", "coding", "guided by", "submitted by",
    "title", "college", "department", "academic", "year", "project", "details", "specifications & coding",
    # ML Algorithm names — these are never real organizations or person names
    "k-nearest neighbors", "k nearest neighbors", "k-nearest",
    "k-means clustering", "k means clustering", "k-means",
    "random forest", "random forest classifier", "random forest regressor",
    "decision tree", "decision tree classifier",
    "support vector machine", "support vector machines", "support vector classifier",
    "neural network", "neural networks", "deep neural network",
    "logistic regression", "linear regression", "multiple regression",
    "naive bayes", "gradient boosting", "gradient descent",
    "principal component analysis", "linear discriminant analysis",
    "k-fold cross validation", "cross validation", "train test split",
    "confusion matrix", "classification report", "feature extraction",
    "dimensionality reduction", "feature selection", "feature engineering",
    "sklearn.decomposition", "sklearn.cluster", "sklearn.neighbors",
    "sklearn.svm", "sklearn.tree", "sklearn.ensemble", "sklearn.metrics",
    "sklearn.preprocessing", "sklearn.pipeline", "sklearn.model_selection",
    "sklearn.datasets", "sklearn.linear_model", "sklearn.neural_network",
}


# ML/DS verb-phrase pattern — rejects entities like "Load Breast Cancer Dataset",
# "Create KNN", "Reduce Dimensions", "Select Features", etc.
_ML_VERB_PATTERN = re.compile(
    r'^(load|create|reduce|select|separate|train|build|fit|run|compute|'
    r'generate|extract|initialize|prepare|process|evaluate|optimize|'
    r'visualize|plot|display|show|calculate|detect|cluster|classify|'
    r'apply|define|configure|compile|execute|perform|update|delete|'
    r'encode|decode|normalize|standardize|transform|predict|fetch|'
    r'import|export|read|write|save|open|close|check|validate|filter|'
    r'sort|merge|split|combine|convert|parse|format|render|handle)\b',
    re.IGNORECASE
)


def _is_valid_entity(value: str, label: str, is_academic: bool = False) -> bool:
    val_low = value.lower().strip()

    # 1. Skip if value is in explicit exclusion list
    if val_low in _EXCLUDE_NER_VALUES:
        return False

    # Reject common keyboard/language select layout false positives (e.g. "paya se", "english & 'o")
    if val_low in ["paya se", "paya", "se", "paise", "payase", "english & 'o", "english & ‘o"]:
        return False

    # Reject ML/DS verb-phrase patterns: "Load X", "Create X", "Reduce X", etc.
    if _ML_VERB_PATTERN.match(value.strip()):
        return False

    # Check if entity consists entirely of noise words
    # Clean the part to ignore quotes, brackets, and non-alphanumeric punctuation when computing len/word checks
    # Require parts to be at least 3 characters unless they are joined by longer valid words (filters "Paya Se" etc.)
    if all(
        part in _EXCLUDE_NER_VALUES or
        part in _FP_WORDS or
        re.sub(r'[^a-zA-Z0-9]', '', part) in _FP_WORDS or
        len(re.sub(r'[^a-zA-Z0-9]', '', part)) < 3
        for part in val_low.split()
    ):
        return False

    # 2. Skip UI tags or common noise words
    if val_low in _FP_WORDS:
        return False

    # 3. Skip technical symbols/variables
    # - snake_case (contains underscores)
    if '_' in value:
        return False
    # - camelCase / PascalCase (lowercase to uppercase transition)
    if re.search(r'[a-z][A-Z]', value):
        return False
    # - Python module paths like sklearn.decomposition, os.path, tf.keras, etc.
    #   Old check only covered 2-4 char extensions; now covers any length word after dot
    if '/' in value or '\\' in value or re.search(r'\.[a-zA-Z_][a-zA-Z0-9_]{1,}', value):
        return False
    # - K-algorithm abbreviations: K-Nearest, K-Means, K-NN, K-SVM, K-Fold, etc.
    if re.match(r'^k[-\s](nearest|means|fold|nn|svm|pca|medoids|armed|way)', value, re.IGNORECASE):
        return False

    # 4. Filter out section headings that are entirely uppercase (e.g. "PROBLEM", "TECHNICAL SPECIFICATIONS")
    if value.isupper() and len(value) > 4:
        return False

    # ── KEY EXTRA FIX: Robust Computer Science / Tech / Academic Taxonomy Filter ──
    val_words = set(re.findall(r'\b[a-z]{2,}\b', val_low))
    _TECH_CS_KEYWORDS = {
        "dashboard", "database", "databases", "handling", "backend", "frontend", "framework", "frameworks",
        "software", "hardware", "network", "networks", "application", "applications", "system", "systems",
        "development", "developer", "developers", "programming", "program", "programs", "code", "coding",
        "documentation", "document", "documents", "syllabus", "semester", "academic", "synopsis", "report", "reports",
        "library", "libraries", "package", "packages", "module", "modules", "class", "classes", "function", "functions",
        "variable", "variables", "api", "apis", "server", "servers", "client", "clients", "web", "website", "websites",
        "page", "pages", "interface", "interfaces", "ui", "ux", "testing", "test", "tests", "integration", "deployment",
        "security", "privacy", "intelligence", "artificial", "learning", "model", "models", "algorithm", "algorithms",
        "data", "science", "analytics", "analysis", "guided", "guidance", "submitted", "submission", "department",
        "college", "university", "school", "faculty", "student", "students", "instructor", "professor", "course", "courses",
        "subject", "subjects", "syllabus", "exam", "exams", "examination", "examinations", "marks", "grade", "grades",
        "cgpa", "gpa", "credits", "credit", "vtu", "usn", "uucms", "roll", "register", "registration", "admission",
        "admissions", "batch", "foundation", "documentation", "technical", "specifications", "specification", "project",
        "projects", "phase", "milestone", "milestones", "deliverable", "deliverables", "gantt", "chart", "charts",
        "diagram", "diagrams", "flowchart", "flowcharts", "architecture", "design", "designs", "implementation",
        "methodology", "motivation", "background", "abstract", "summary", "conclusions", "conclusion", "introduction",
        "future", "scope", "appendix", "index", "references", "reference", "guided", "guide", "guides",
        "sqlalchemy", "sqlite", "mysql", "postgres", "postgresql", "mongodb", "oracle", "redis", "firebase",
        "supabase", "react", "vue", "angular", "nextjs", "vite", "flask", "django", "fastapi", "streamlit",
        "pandas", "numpy", "matplotlib", "seaborn", "scikit", "sklearn", "keras", "tensorflow", "pytorch",
        "opencv", "tesseract", "spacy", "nltk", "python", "java", "javascript", "typescript", "html", "css",
        "php", "ruby", "rails", "kotlin", "swift", "rust", "golang", "cplusplus", "csharp", "dotnet", "net",
        # ML algorithm words — these NEVER constitute a real org/person in any context
        "nearest", "neighbors", "clustering", "decomposition", "classifier",
        "regression", "boosting", "bagging", "ensemble", "perceptron", "activation",
        "convolutional", "recurrent", "transformer", "embedding", "tokenizer",
        "preprocessing", "dimensionality", "hyperparameter", "overfitting", "underfitting",
        "gradient", "backpropagation", "optimizer", "regularization", "normalization",
        # App/tool feature words — cannot be person names
        "scanner", "scanning", "upload", "download", "detection", "detected",
        "config", "configuration", "array", "list", "dict", "object", "key",
        "files", "file", "folder", "directory", "path", "url", "endpoint",
        "metadata", "payload", "response", "request", "token", "header",
        "batch", "queue", "worker", "thread", "process", "task", "job",
        "blur", "blurred", "redact", "redacted", "masked", "encrypted",
        "exposure", "privacy", "shield", "risk", "score", "level", "high",
        "medium", "low", "critical", "safe", "sensitive", "findings",
        "report", "generate", "generated", "export", "import",
        "monitor", "monitoring", "agent", "background", "history",
        "cloud", "social", "attack", "simulation", "remediation",
        "recommendation", "recommendations", "plan", "guide", "manual",
    }

    if val_words & _TECH_CS_KEYWORDS:
        if is_academic:
            # Under academic/synopsis context, filter all technical/educational words from ORG, PERSON, GPE, LOC
            if label in ["PERSON", "ORG", "GPE", "LOC", "DATE"]:
                return False
        else:
            # In other contexts:
            # - PERSON names cannot contain technical software concepts
            # - GPE/LOC cannot contain technical terminology
            if label in ["PERSON", "GPE", "LOC"]:
                return False
            # - ORG names cannot be standard frameworks, libraries, or languages
            if label == "ORG":
                tech_libs = {"sqlalchemy", "sqlite", "mysql", "postgres", "postgresql", "mongodb", "react", "vue", "angular", 
                             "flask", "django", "fastapi", "streamlit", "pandas", "numpy", "python", "java", "javascript", 
                             "typescript", "html", "css", "documentation", "library", "framework"}
                if val_words & tech_libs:
                    return False

    # 5. For PERSON names, require that they look like actual names
    if label == "PERSON":
        # Skip names containing digits or technical symbols
        if any(c.isdigit() or c in "@#$!%^&*()-+=" for c in value):
            return False
        # Skip single-word names if they match standard dictionary words or are too short
        if len(value.split()) == 1:
            if val_low in _FP_WORDS or len(value) < 4:
                return False

    # 6. For ORG/GPE/LOC, skip if they look like standard headers or academic fields
    if label in ["ORG", "GPE", "LOC"]:
        if any(term in val_low for term in ["department", "engineering", "university", "college", "school"]):
            if "college of" in val_low or "department of" in val_low or val_low in ["sdmit", "vtu"]:
                return False

    # 7. For ORG specifically, filter heading misclassifications and incomplete parses
    if label == "ORG":
        # Heading/Academic terminology noise
        org_noise = {
            "academic year", "problem", "develop", "technical", "specifications",
            "synopsis", "references", "guided by", "submitted by", "motivation",
            "background", "engine", "score", "property", "readiness", "feedback",
            "track", "tracking", "anxiety", "signals", "encouragement", "introduction",
            "conclusion", "abstract", "summary", "requirements", "deliverables",
            "milestones", "objectives", "goals", "aims", "methodology", "architecture",
            "system", "design", "implementation", "testing", "evaluation", "results",
            "analysis", "future", "scope", "guidelines", "appendix", "index",
            "content", "contents", "table", "figure", "diagram", "chart", "intellectual",
            "confidence",
            # ML algorithm names that spaCy misclassifies as ORG
            "k-nearest neighbors", "k nearest neighbors", "k-means clustering", "k means clustering",
            "k-nearest", "k-means", "random forest", "decision tree", "support vector machine",
            "neural network", "logistic regression", "linear regression", "naive bayes",
            "gradient boosting", "principal component analysis", "cross validation",
            "confusion matrix", "classification report", "feature extraction",
            "dimensionality reduction", "input module", "output module", "tracking module",
        }
        if any(noise in val_low for noise in org_noise) or val_low in org_noise:
            return False
        # Reject ORG values where ALL words are ML/tech terms
        org_words = set(re.findall(r'[a-z]{3,}', val_low))
        _ML_ORG_BLOCKLIST = {
            "nearest", "neighbors", "clustering", "decomposition", "classifier",
            "regression", "boosting", "ensemble", "perceptron", "activation",
            "convolutional", "transformer", "embedding", "preprocessing",
            "hyperparameter", "gradient", "optimizer", "regularization",
            "normalization", "backpropagation", "overfitting", "underfitting",
            "sklearn", "scikit", "module", "import", "function", "class",
        }
        if org_words and org_words.issubset(_ML_ORG_BLOCKLIST):
            return False
        # Incomplete parse ending in logical operators or conjunctions
        if val_low.endswith("&") or val_low.endswith("and") or val_low.endswith("or"):
            return False

    # 8. For GPE and LOC specifically, skip common documentation/report fields
    if label in ["GPE", "LOC"]:
        loc_noise = {
            "documentation", "documentation.", "problem", "technical", "specifications",
            "report", "project", "system", "code", "design", "testing", "build"
        }
        if val_low in loc_noise:
            return False

    # 9. For DATE specifically, ignore generic years or relative terms
    if label == "DATE":
        if is_academic:
            return False
        if re.match(r'^\d{4}$', val_low) or re.match(r'^\d{4}-\d{2,4}$', val_low):
            return False
        relative_date_terms = {
            "this", "next", "last", "recent", "week", "month", "year", "today",
            "tomorrow", "yesterday", "relative", "temporal"
        }
        if any(term in val_low for term in relative_date_terms):
            return False
        # Reject credit card numbers appearing as dates (spaCy misclassifies
        # 16-digit card strings like "4532 1234 5678 9012" as DATE entities)
        digits_only = re.sub(r'\s+', '', value)
        if re.match(r'^\d{13,19}$', digits_only):      # 13–19 digits = card number
            return False
        if re.match(r'^\d{4}\s\d{4}\s\d{4}$', value): # Aadhaar format
            return False
        if re.match(r'^\d{4}\s\d{4}\s\d{4}\s\d{4}$', value): # Card format
            return False

    # 10. For MONEY/Financial specifically, require a currency symbol or currency name indicator
    # e.g., ₹, $, Rs, rupee, rupees, dollars, inr, usd. This prevents generic academic years or pure numbers.
    if label == "MONEY":
        val_clean = value.lower()
        has_currency = any(sym in val_clean for sym in ["$", "₹", "€", "£", "¥", "rs", "rupee", "rupees", "dollar", "dollars", "inr", "usd"])
        if not has_currency:
            return False

    # 11. For CARDINAL (id_number), require the value to contain digits
    #     Module paths, algorithm names, and plain words are NOT ID numbers
    if label == "CARDINAL":
        # Must have at least one digit to be a real ID/cardinal number
        if not any(c.isdigit() for c in value):
            return False
        # Reject module paths (contain dots)
        if '.' in value:
            return False
        # Reject values that look like plain English words or ML terms
        if re.match(r'^[a-zA-Z][a-zA-Z\s-]+$', value):
            return False
        # Reject Indian mobile numbers (10 digits starting with 6–9)
        # These are already detected by the phone regex — don't double-tag
        digits_only = re.sub(r'[\s\-]', '', value)
        if re.match(r'^[6-9]\d{9}$', digits_only):
            return False
        # Reject credit card numbers (13–19 digit strings)
        if re.match(r'^\d{13,19}$', digits_only):
            return False
        # Reject Aadhaar numbers (12 digits) — already detected by Aadhaar regex
        if re.match(r'^\d{12}$', digits_only):
            return False

    # 12. Skip USN / Register Numbers / UUCMS Numbers
    if re.match(r'^\d[a-zA-Z]{2}\d{2}[a-zA-Z]{2}\d{3}$', val_low):
        return False
    if re.match(r'^[a-zA-Z]{2,4}\d{2}[a-zA-Z]{2}\d{3}$', val_low):
        return False
    if re.match(r'^[uUpP]\d{2}[a-zA-Z]{2,4}\d{2}[a-zA-Z]{1,2}\d{3,6}$', val_low):
        return False

    return True
def analyze_with_spacy(text: str) -> list[dict]:
    """
    Run spaCy NER and return NEW AI findings (names, locations, orgs etc.)
    that regex cannot detect.

    Returns list of:
      { type, value, method, confidence, weight }
    """
    nlp = _get_nlp()
    if nlp is None or not text or not text.strip():
        return []

    text_low = text.lower()
    is_academic = any(kw in text_low for kw in [
        # Academic document signals
        "synopsis", "academic", "semester", "project report", "problem statement",
        "guided by", "submitted by", "literature survey", "future scope",
        "bachelor of engineering", "master of technology", "vtu", "usn", "uucms",
        # ML / Data-Science / Code signals
        "sklearn", "scikit", "import pandas", "import numpy", "import sklearn",
        "from sklearn", "load_breast_cancer", "train_test_split", "cross_val_score",
        "gridsearchcv", "k-nearest", "k-means", "kmeans", "knn",
        "breast cancer", "iris dataset", "mnist", "classification report",
        "confusion matrix", "random forest", "decision tree", "neural network",
        "matplotlib", "seaborn", "jupyter", "notebook", "colab", "ipynb",
        "def ", "import ", "print(", "return ", "class ", "self.",
        # Tool / App documentation — study guides, user manuals, feature docs
        "study guide", "user guide", "user manual", "how to use", "getting started",
        "key features", "key files", "scan results", "scanner", "metadata scanner",
        "upload & scan", "batch scan", "cloud scanner", "screen monitor",
        "privacy exposure", "privacyshield", "privacy tool", "privacy shield",
        "risk level", "sensitivity score", "findings panel", "blur engine",
        "report generator", "background agent", "score history",
        "social scanner", "url scanner", "attack simulation",
        # Generic documentation / readme / guide signals
        "table of contents", "chapter ", "section ", "appendix",
        "installation", "configuration", "setup guide", "readme",
    ])

    # ── OCR Quality Check ─────────────────────────────────────────────────────
    # If text has too many noise characters, it's a bad OCR scan — skip NER
    # to prevent garbled fragments being flagged as person names

    # Strip browser URL/tab-title lines (e.g. 'Sujay Bhat - Facebook')
    _BP = {'facebook','instagram','twitter','whatsapp','telegram','snapchat','youtube','linkedin','reddit','tiktok','pinterest','discord','google','gmail','outlook','yahoo','hotmail'}
    _cln = []
    for _ln in text.splitlines():
        _lnl = _ln.strip().lower()
        _it = any(_lnl.endswith('- ' + _p) or _lnl.endswith('| ' + _p) for _p in _BP)
        _iu = any(_pl in _lnl.replace(' ','') for _pl in ('facebookcom','instagram.com','twitter.com'))
        if not _it and not _iu:
            _cln.append(_ln)
    ner_text = chr(10).join(_cln)

    total_chars = max(len(ner_text), 1)
    noise_chars = sum(1 for c in ner_text if c in r'|\{}[]<>_=+`~^*')
    noise_ratio = noise_chars / total_chars
    is_bad_ocr = noise_ratio > 0.03  # more than 3% noise chars = bad OCR
    if is_bad_ocr:
        logger.info("Bad OCR quality detected (noise ratio=%.2f%%) — skipping PERSON/ORG NER", noise_ratio * 100)

    try:
        doc = nlp(ner_text[:500_000])
    except Exception as e:
        logger.error("spaCy NER failed: %s", e)
        return []

    seen: set[tuple] = set()
    findings: list[dict] = []

    for ent in doc.ents:
        if ent.label_ in _SKIP_LABELS:
            continue
        mapping = _ENTITY_MAP.get(ent.label_)
        if not mapping:
            continue

        # Skip person/org/location NER for bad OCR documents — only garbage comes out
        if is_bad_ocr and ent.label_ in ["PERSON", "ORG", "GPE", "LOC"]:
            continue

        ftype, weight = mapping
        
        # Remove zero-width spaces and non-printing unicode characters
        clean_text = re.sub(r'[\u200b-\u200d\ufeff\u200e\u200f]', '', ent.text)
        # Ensure all types of straight and curly single/double quotes are stripped (including left-single '‘')
        value = clean_text.strip().strip(".,;:()[]'\"”’“‘")
        
        if ent.label_ in ["ORG", "PERSON", "GPE", "LOC"]:
            # Clean trailing numbers or punctuation from entity values (e.g. Theta Dynamics Private Limited.7.)
            value = re.sub(r'[\d\s.,;:()\[\]\'"”’“‘#&–\-]+$', '', value).strip()
        
        value = value.strip()
        if len(value) < 3:
            continue

        conf = _confidence(value, ent.label_)

        if conf < 0.40:  # Raised threshold — reduces borderline garbage further
            continue

        # Reject OCR garbage entity values before any further validation
        if _is_ocr_garbage_entity(value):
            continue

        # Filter out false entities using deep validation
        if not _is_valid_entity(value, ent.label_, is_academic=is_academic):
            continue

        # In academic/code documents, drastically reduce NER confidence and weight
        # to prevent code comments, algorithm names, variable names etc. inflating score
        if is_academic and ftype in ("person_name", "organization", "location", "demographic"):
            conf = round(conf * 0.35, 2)   # e.g. 0.90 → 0.31
            weight = max(weight // 4, 1)   # e.g. 20 → 5
            if conf < 0.25:                # drop very low confidence after dampening
                continue

        key = (ftype, value.lower())
        if key in seen:
            continue
        seen.add(key)

        findings.append({
            "type":       ftype,
            "value":      value,
            "method":     "ai",
            "confidence": conf,
            "weight":     weight,
        })

    return findings


# ─── Confidence scoring for regex findings ───────────────────────────────────

def _char_entropy(s: str) -> float:
    """Shannon entropy — high = more random = more likely a real credential."""
    if not s:
        return 0.0
    freq: dict[str, int] = {}
    for c in s:
        freq[c] = freq.get(c, 0) + 1
    n = len(s)
    return -sum((v / n) * math.log2(v / n) for v in freq.values())


# Rules for scoring regex-detected findings
_TYPE_RULES = {
    "email":       {"base": 0.85, "flag": lambda v: "@" in v and "." in v},
    "phone":       {"base": 0.80, "flag": lambda v: bool(re.match(r"^[6-9]\d{9}$", v))},
    "password":    {"base": 0.55, "entropy_w": 0.15},
    "aadhaar":     {"base": 0.88, "flag": lambda v: bool(re.match(r"^[2-9]\d{11}$", v.replace(" ", "")))},
    "pan_card":    {"base": 0.90, "flag": lambda v: bool(re.match(r"^[A-Z]{5}[0-9]{4}[A-Z]$", v))},
    "credit_card": {"base": 0.78},
    "cvv":         {"base": 0.72},
    "otp":         {"base": 0.65},
    "dob":         {"base": 0.70},
}


def score_regex_finding(value: str, ftype: str) -> float:
    """Return a confidence score 0.0–1.0 for a regex-detected finding."""
    rules = _TYPE_RULES.get(ftype, {"base": 0.50})
    score = rules["base"]

    # Flag check (structural match)
    flag_fn = rules.get("flag")
    if flag_fn is not None:
        try:
            score += 0.1 if flag_fn(value) else -0.15
        except Exception:
            pass

    # Entropy boost for passwords
    ew = rules.get("entropy_w", 0.0)
    if ew:
        entropy = _char_entropy(value)
        score += ew * min(entropy / 4.0, 1.0)

    return round(min(max(score, 0.0), 1.0), 3)


def enrich_regex_findings(findings: list[dict]) -> list[dict]:
    """
    Add 'confidence', 'method', and 'ai_label' to existing regex findings.
    """
    enriched = []
    for f in findings:
        conf = score_regex_finding(f.get("value", ""), f.get("type", ""))
        label = (
            "HIGH_CONFIDENCE"   if conf >= 0.75 else
            "MEDIUM_CONFIDENCE" if conf >= 0.45 else
            "LOW_CONFIDENCE"
        )
        enriched.append({
            **f,
            "method":     f.get("method", "regex"),
            "confidence": conf,
            "ai_label":   label,
        })
    return enriched


# ─── Score contribution from AI findings ─────────────────────────────────────

def score_ai_findings(ai_findings: list[dict], doc_type: str = "generic") -> float:
    """
    Score points from AI-detected findings.
    For code/academic/generic documents, NER-only finding types are capped at 20pts total.
    """
    # Finding types that come purely from NER (not hard regex evidence)
    _NER_SOFT_TYPES = {"person_name", "organization", "location", "demographic", "date"}
    # Document types that should heavily discount NER soft findings
    _LOW_RISK_DOC_TYPES = {"ml_notebook", "project_synopsis", "generic", "academic", "unknown"}

    by_type: dict[str, list] = {}
    for f in ai_findings:
        by_type.setdefault(f["type"], []).append(f)

    raw = 0.0
    ner_soft_total = 0.0

    for ftype, items in by_type.items():
        if not items:
            continue
        w = items[0]["weight"]
        n = len(items)
        pts = w + (w * 0.7 if n >= 2 else 0) + (w * 0.5 * (n - 2) if n >= 3 else 0)
        contribution = pts * 1.4

        if ftype in _NER_SOFT_TYPES:
            ner_soft_total += contribution
        else:
            raw += contribution

    # For low-risk doc types, cap NER soft-type contribution to 15 pts
    if doc_type in _LOW_RISK_DOC_TYPES:
        raw += min(ner_soft_total, 15.0)
    else:
        raw += ner_soft_total

    return round(raw, 1)


# ─── Engine info ─────────────────────────────────────────────────────────────

def get_ai_engine_info() -> dict:
    _get_nlp()  # ensure loaded
    return {
        "engine":    "spaCy NER" if _SPACY_AVAILABLE else "Rule-Based",
        "model":     "en_core_web_sm" if _SPACY_AVAILABLE else None,
        "available": _SPACY_AVAILABLE,
        "new_types": [
            "person_name", "location", "organization",
            "id_number", "date", "financial", "demographic"
        ],
    }
