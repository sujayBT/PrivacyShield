import os
import re
import logging
import pytesseract
import pdfplumber
from PIL import Image

logger = logging.getLogger(__name__)

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


# ─── Text Extraction ──────────────────────────────────────────────────────────

def extract_text_from_file(file_path: str) -> str:
    text = ""
    ext = os.path.splitext(file_path)[1].lower()
    try:
        if ext in [".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tiff"]:
            img = Image.open(file_path).convert("RGB")
            w, h = img.size
            
            # --- Smart OCR (Fast Path) ---
            # Run a single, fast PSM 3 pass on the raw image first
            try:
                text = pytesseract.image_to_string(img, config="--psm 3 --oem 3")
            except Exception:
                text = ""
                
            # --- Fallback to heavy enhanced OCR if fast path extracts nothing useful ---
            if len(text.strip()) < 20:
                logger.info("Fast OCR failed (< 20 chars), falling back to enhanced dual-pass OCR.")
                if w < 1200:
                    scale = max(2, int(1200 / w))
                    img = img.resize((w * scale, h * scale), Image.LANCZOS)
                # Increase contrast & sharpness for dark/dim UIs
                from PIL import ImageEnhance
                img = ImageEnhance.Contrast(img).enhance(1.8)
                img = ImageEnhance.Sharpness(img).enhance(2.0)
                # Run OCR with PSM 6 (uniform block) + PSM 11 (sparse text) and merge
                try:
                    t6  = pytesseract.image_to_string(img, config="--psm 6 --oem 3")
                    t11 = pytesseract.image_to_string(img, config="--psm 11 --oem 3")
                    # Combine unique lines from both passes
                    lines6  = set(t6.splitlines())
                    lines11 = set(t11.splitlines())
                    text = "\n".join(sorted(lines6 | lines11, key=lambda l: t6.find(l) if l in t6 else 99999))
                except Exception:
                    text = pytesseract.image_to_string(img)
        elif ext == ".pdf":
            # ── Fast PDF text extraction: PyMuPDF (handles most PDFs) ─────────
            # Limits: max 15 pages, max 12,000 chars → keeps scan fast
            PDF_MAX_PAGES  = 15
            PDF_MAX_CHARS  = 12_000
            try:
                import fitz  # PyMuPDF
                doc = fitz.open(file_path)
                total_pages = len(doc)
                pages_to_scan = min(total_pages, PDF_MAX_PAGES)
                for page_num in range(pages_to_scan):
                    page_text = doc[page_num].get_text("text")
                    text += page_text
                    if len(text) >= PDF_MAX_CHARS:
                        text = text[:PDF_MAX_CHARS]
                        break
                doc.close()

                # If PDF is image-based (scanned), run OCR on first 3 pages only
                if len(text.strip()) < 100:
                    logger.info("Image-based PDF detected — running OCR on first 3 pages")
                    import fitz
                    doc2 = fitz.open(file_path)
                    ocr_text = ""
                    for page_num in range(min(3, len(doc2))):
                        page = doc2[page_num]
                        pix = page.get_pixmap(dpi=150)  # lower DPI = faster
                        img_data = pix.tobytes("png")
                        import io
                        img = Image.open(io.BytesIO(img_data)).convert("RGB")
                        page_ocr = pytesseract.image_to_string(img, config="--psm 6 --oem 3")
                        ocr_text += page_ocr
                        if len(ocr_text) >= PDF_MAX_CHARS:
                            break
                    doc2.close()
                    text = ocr_text[:PDF_MAX_CHARS]

            except Exception as fitz_err:
                logger.warning("PyMuPDF failed (%s), trying pdfplumber", fitz_err)
                # ── Fallback: pdfplumber (also page-limited) ──────────────────
                try:
                    with pdfplumber.open(file_path) as pdf:
                        for page in pdf.pages[:PDF_MAX_PAGES]:
                            text += page.extract_text() or ""
                            if len(text) >= PDF_MAX_CHARS:
                                text = text[:PDF_MAX_CHARS]
                                break
                except Exception as plumber_err:
                    logger.warning("pdfplumber failed (%s), trying HTML strip", plumber_err)
                    try:
                        from bs4 import BeautifulSoup
                        with open(file_path, "r", encoding="utf-8", errors="ignore") as fh:
                            raw_html = fh.read()
                        soup = BeautifulSoup(raw_html, "html.parser")
                        text = soup.get_text(separator="\n", strip=True)[:PDF_MAX_CHARS]
                    except Exception:
                        pass
        elif ext in [".txt", ".html", ".htm"]:
            if ext in [".html", ".htm"]:
                try:
                    from bs4 import BeautifulSoup
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as fh:
                        raw_html = fh.read()
                    soup = BeautifulSoup(raw_html, "html.parser")
                    # Remove script/style noise
                    for tag in soup(["script", "style", "noscript"]):
                        tag.decompose()
                    text = soup.get_text(separator="\n", strip=True)
                except Exception:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as fh:
                        text = fh.read()
            else:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    text = f.read()

        elif ext in [".docx"]:
            import docx as python_docx
            doc = python_docx.Document(file_path)
            text = "\n".join([para.text for para in doc.paragraphs])
        elif ext == ".doc":
            # Try reading .doc as binary text fallback (limited support)
            try:
                import subprocess
                result = subprocess.run(
                    ["antiword", file_path], capture_output=True, text=True
                )
                text = result.stdout
            except Exception:
                # Fallback: read raw bytes and extract printable chars
                with open(file_path, "rb") as f:
                    raw = f.read()
                text = raw.decode("latin-1", errors="ignore")
    except Exception as e:
        logger.error("Text extraction error for %s: %s", file_path, e)
    return text


# ─── Pattern Detection ────────────────────────────────────────────────────────

# Generic noise words to ignore when detecting passwords/tokens
# This is a comprehensive list of common English words, UI labels, and OCR fragments
_IGNORE_WORDS = {
    # Auth/account UI labels
    "account", "security", "change", "english", "create",
    "strong", "facebook", "instagram", "whatsapp", "telegram", "twitter",
    "gmail", "please", "enter", "confirm", "reset", "update", "continue",
    "welcome", "verify", "settings", "profile", "google", "outlook",
    # Navigation / UI buttons
    "right", "left", "home", "menu", "back", "next", "done", "cancel",
    "submit", "send", "save", "edit", "delete", "close", "open", "view",
    "login", "logout", "signup", "register", "forgot", "remember", "sign",
    "notification", "message", "inbox", "search", "filter", "sort",
    "upload", "download", "share", "copy", "paste", "print", "export",
    "import", "help", "support", "about", "terms", "privacy", "policy",
    "android", "iphone", "mobile", "keyboard", "screen", "touch",
    "click", "press", "swipe", "scroll", "select", "choose", "check",
    # Common single English words that look token-like
    "hello", "world", "test", "user", "admin", "root", "guest",
    "public", "private", "default", "system", "service", "network",
    "server", "client", "database", "storage", "memory", "cache",
    "error", "warning", "success", "failure", "loading",
    "your", "their", "these", "those", "this", "that", "there",
    "have", "been", "from", "with", "will", "would", "could",
    "should", "might", "about", "after", "before", "during",
    "above", "below", "under", "over", "between", "through",
    "access", "allow", "block", "enable", "disable", "turn",
    "start", "stop", "pause", "resume", "refresh", "reload",
    "connect", "disconnect", "sync", "backup", "restore",
    "manage", "control", "monitor", "track", "record", "report",
    "status", "state", "mode", "type", "level", "grade",
    "option", "options", "choice", "choices", "result", "results",
    "detail", "details", "info", "information", "content", "data",
    "value", "values", "item", "items", "list", "section", "group",
    # Pronouns and common sentence starters
    "already", "always", "never", "often", "sometimes", "usually",
    "every", "each", "both", "either", "neither", "other",
    "same", "different", "similar", "new", "old", "recent", "latest",
    "first", "second", "third", "last", "next", "final",
    "also", "only", "just", "even", "still", "again", "once",
    # Tech/app noise
    "android", "windows", "linux", "macos", "chrome", "firefox",
    "safari", "edge", "opera", "browser", "internet", "online",
    "offline", "website", "webpage", "portal", "platform", "cloud",
    # Common OCR fragments from screenshots
    "notification", "battery", "signal", "volume", "wifi", "bluetooth",
    "airplane", "rotate", "lock", "unlock", "camera", "gallery",
    "call", "missed", "received", "dialed", "contact", "contacts",
    "recent", "favourite", "favorites", "history", "activity",
    "notification", "alert", "reminder", "alarm", "timer", "clock",
    "calendar", "event", "task", "note", "notes", "memo",
    "photo", "video", "audio", "music", "podcast", "stream",
    "app", "apps", "application", "install", "uninstall", "update",
    "version", "build", "release", "beta", "alpha",
    # Common words that the previous detector flagged
    "paya", "english",
    # ── DATE / TIME LABELS — frequently misdetected as person names ────────────
    "date", "time", "year", "month", "day", "hour", "minute", "second",
    "today", "yesterday", "tomorrow", "now", "then", "when",
    # Month names — OCR sometimes reads them as names
    "january", "february", "march", "april", "june", "july",
    "august", "september", "october", "november", "december",
    "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "oct", "nov", "dec",
    # Document field labels — printed labels misread as names
    "name", "place", "address", "city", "state", "country", "pincode",
    "phone", "mobile", "email", "fax", "gender", "male", "female",
    "age", "roll", "class", "subject", "course", "department",
    "college", "university", "school", "institute", "institution",
    "number", "serial", "code", "reference", "ref", "no", "num",
    "designation", "position", "post", "rank", "grade", "score",
    "signature", "sign", "stamp", "seal", "logo",
    "total", "amount", "balance", "debit", "credit", "paid",
    "issued", "valid", "expiry", "expires", "validity",
    "nationality", "occupation", "relation", "father", "mother",
    "husband", "wife", "guardian", "principal", "officer",
    # Academic / project doc noise
    "abstract", "introduction", "conclusion", "methodology", "references",
    "acknowledgement", "appendix", "synopsis", "chapter", "figure", "table",
    "theory", "algorithm", "approach", "implementation", "result",
    "objective", "scope", "purpose", "summary", "overview",
    # Privacy Tool itself
    "privacy", "tool", "exposure", "scanner", "scan", "analysis",
    "finding", "findings", "sensitive", "detected", "report",
}

# OCR fragments that look like garbage — strictly reject these as passwords
_OCR_GARBAGE_PATTERN = re.compile(
    r"^[xzqjXZQJ]{3,}|"          # starts with many rare letters
    r"^[^a-zA-Z0-9]{3,}|"        # mostly symbols
    r"^[0-9a-f]{20,}$|"          # hex dump
    r".*(\w)\1{3,}.*",            # 4+ repeated chars
    re.I
)

# Common words from UI text that look like alphanumeric tokens but are not sensitive
_UI_NOISE = re.compile(
    r"^(android|iphone|mobile|keyboard|qwerty|space|return|shift|delete|"
    r"backspace|search|browser|address|http|https|www|com|org|net|"
    r"button|screen|touch|swipe|scroll|click|press|hold|drag|"
    r"right|left|home|back|next|done|cancel|submit|send|save|"
    r"menu|nav|tab|icon|logo|badge|chip|card|modal|dialog|"
    r"wifi|signal|battery|bluetooth|notification|lock|unlock|"
    r"view|edit|open|close|expand|collapse|toggle|switch|"
    r"ok|yes|no|okay|sure|fine|good|bad|skip|later|always|never|"
    r"continue|confirm|accept|decline|allow|deny|block|report|"
    r"english|hindi|french|spanish|arabic|chinese|japanese|"
    r"saturday|sunday|monday|tuesday|wednesday|thursday|friday|"
    r"january|february|march|april|june|july|august|september|"
    r"october|november|december)$", re.I
)


# Patterns that strongly indicate real credentials — STRICT: require explicit = or : separator
# This prevents "password account", "password right" etc from being matched
_CREDENTIAL_PATTERN = re.compile(
    r"(?:password|passwd|pwd|pass|secret|token|apikey|api_key|auth)\s*[=:]\s*(\S+)",
    re.I
)

# Contextual credential: "New Password: value" — also requires a separator
_CREDENTIAL_LABEL_PATTERN = re.compile(
    r"(?:new\s+password|current\s+password|confirm\s+password|enter\s+password|type\s+password)"
    r"\s*[=:]\s*([\S]{4,})",
    re.I
)

# Aadhaar: 12-digit number (space-separated groups too)
_AADHAAR_PATTERN = re.compile(r"\b[2-9]\d{3}\s?\d{4}\s?\d{4}\b")

# PAN card: 5 letters + 4 digits + 1 letter
_PAN_PATTERN = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b")

# Credit/Debit card: 16 digits (groups allowed)
_CARD_PATTERN = re.compile(r"\b(?:\d[ -]?){15,16}\b")

# CVV: 3-4 digits near CVV keyword
_CVV_PATTERN = re.compile(r"\bCVV\b.*?(\d{3,4})", re.I)

# Date of birth patterns
_DOB_PATTERN = re.compile(
    r"\b(?:dob|date\s+of\s+birth|born\s+on)[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b", re.I
)

# Email
_EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")

# Indian mobile numbers
_PHONE_PATTERN = re.compile(r"\b[6-9][0-9]{9}\b")

# OTP — only matched with explicit context keyword nearby
# (blind 4-6 digit regex caused keyboard numbers, timestamps, counters to be flagged)
_OTP_CONTEXT_PATTERN = re.compile(
    r"(?:otp|one[-\s]time\s+(?:password|passcode|pin|code)|"
    r"verification\s+(?:code|pin)|auth(?:entication)?\s+(?:code|pin|token)|"
    r"login\s+(?:code|pin)|security\s+code|confirm(?:ation)?\s+(?:code|pin)|"
    r"passcode|access\s+code)"
    r"\D{0,60}(\d{4,6})",
    re.I,
)
_YEAR_PATTERN = re.compile(r"\b(19|20)\d{2}\b")          # plain 4-digit year
_FISCAL_YEAR_PATTERN = re.compile(r"\b(19|20)\d{2}-\d{2,4}\b")  # e.g. 2026-27, 2024-2025
# Keep _OTP_PATTERN as alias so any existing imports don't break
_OTP_PATTERN = _OTP_CONTEXT_PATTERN

# Month names to detect date strings like "18-Apr-2026", "05-May-2026"
_MONTH_ABBR = re.compile(
    r"\b\d{1,2}[-/](Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[-/]\d{2,4}\b", re.I
)
_MONTH_FULL = re.compile(
    r"\b\d{1,2}[-/](January|February|March|April|May|June|July|August|September|October|November|December)[-/]\d{2,4}\b", re.I
)

# Passwords: alphanumeric+special, 6-30 chars, must have digit or special char
_PASSWORD_PATTERN = re.compile(r"\b[A-Za-z0-9@#$!%^&*_\-]{6,30}\b")



def _is_date_string(token: str) -> bool:
    """Returns True if the token looks like a date, not a password."""
    if _MONTH_ABBR.match(token) or _MONTH_FULL.match(token):
        return True
    if _FISCAL_YEAR_PATTERN.match(token):
        return True
    # Pattern like "Inter-Department", nav labels — contains only alpha+hyphen
    if re.match(r'^[A-Za-z]+-[A-Za-z]+$', token):
        return True
    return False


def _shannon_entropy(s: str) -> float:
    """Calculate Shannon entropy of a string."""
    if not s:
        return 0.0
    import math
    freq = {}
    for c in s:
        freq[c] = freq.get(c, 0) + 1
    n = len(s)
    return -sum((v / n) * math.log2(v / n) for v in freq.values())

def _is_ocr_garbage(token: str) -> bool:
    """
    Returns True if a token looks like OCR noise / garbage.
    Used to reject bad detections before they become findings.
    """
    if not token:
        return True
    t = token.strip()
    if len(t) < 3:
        return True
    # Mostly non-alphanumeric characters
    alpha_ratio = sum(1 for c in t if c.isalnum()) / max(len(t), 1)
    if alpha_ratio < 0.5:
        return True
    # Contains 4+ repeated characters in a row (OCR artifact)
    if re.search(r'(.)\1{3,}', t):
        return True
    # Starts with 3+ consecutive rare letters (xzqj etc.)
    if re.match(r'^[xzqjXZQJ]{3,}', t):
        return True
    # Random symbol soup
    if re.match(r'^[^a-zA-Z0-9]{3,}', t):
        return True
    # Contains mixed-in unicode corruption
    if re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', t):
        return True
    return False


def _clean_ocr_text(text: str) -> str:
    """
    Clean OCR-extracted text before running pattern detection.
    Removes garbage lines, duplicate lines, and noise fragments.
    """
    if not text:
        return ""
    cleaned = []
    seen_lines = set()
    for line in text.splitlines():
        stripped = line.strip()
        # Skip empty or very short lines
        if len(stripped) < 3:
            continue
        # Skip lines that are mostly non-alphanumeric (OCR garbage)
        alpha_ratio = sum(1 for c in stripped if c.isalnum()) / max(len(stripped), 1)
        if alpha_ratio < 0.35:
            continue
        # Skip duplicate lines (OCR often repeats header/footer)
        low = stripped.lower()
        if low in seen_lines:
            continue
        seen_lines.add(low)
        cleaned.append(stripped)
    return "\n".join(cleaned)


def _detect_passwords(text: str, email_set: set | None = None, is_academic: bool = False) -> list:
    """
    Detect passwords/credentials from text.
    Priority 1: explicit credential=value patterns (require = or : separator).
    Priority 2: heuristic alphanumeric tokens with strict 3-class complexity.
    email_set: set of already-detected emails to exclude substrings of.
    """
    found = set()
    email_set = email_set or set()

    # 1. Explicit credential key=value  (e.g. password: Secret@123 or password is X123)
    explicit_vals = set()
    for pattern in (_CREDENTIAL_PATTERN, _CREDENTIAL_LABEL_PATTERN):
        for m in pattern.finditer(text):
            val = m.group(1).strip("\"'`\n\r")
            # Strip trailing punctuation that OCR often adds
            val = val.rstrip(".,:;!?")
            if len(val) >= 4:
                # Never emit a value that is part of an email address
                if not any(val in e or e in val for e in email_set):
                    found.add(val)
                    explicit_vals.add(val.lower())

    # 2. Heuristic tokens
    for m in _PASSWORD_PATTERN.finditer(text):
        token = m.group()
        low   = token.lower()

        # If already captured by explicit rule, skip heuristic checks
        if token in found or low in explicit_vals:
            continue

        # ── CONTEXT AWARENESS FOR PASSWORD FIELDS ───────────────────────────
        # Check if this token is near a password context keyword in the text
        start_pos = m.start()
        # Look back up to 120 characters in the text (covers several lines/labels)
        context_window = text[max(0, start_pos - 120):start_pos].lower()
        
        # Check for explicit password labels/fields nearby in OCR text
        is_password_context = any(kw in context_window for kw in [
            "password", "passwd", "pwd", "passcode", "secret", "credential"
        ])

        # KEY FIX: if this is an academic/project synopsis document, disable heuristic passwords entirely
        # to prevent street addresses, PIN codes, or technical versions from being flagged as secrets.
        if is_academic:
            continue

        # Must contain digit OR special char (reject plain words like "right", "account")
        if not re.search(r'[0-9@#$!%^&*_\-]', token):
            continue
        # Skip pure numbers
        if token.isdigit():
            continue
        # Skip noise words (huge list)
        if low in _IGNORE_WORDS:
            continue
        if _UI_NOISE.match(token):
            continue
        # Skip OCR garbage tokens
        if _is_ocr_garbage(token):
            continue
        # Skip short all-alpha tokens
        if re.match(r'^[a-zA-Z]{1,5}$', token):
            continue
        # Skip date-like strings
        if _is_date_string(token):
            continue
        # Skip plain years
        if _YEAR_PATTERN.fullmatch(token):
            continue
        # KEY FIX: skip tokens that are substrings of any detected email
        if any(token in email or token in email.split('@')[0] or
               token in email.split('@')[-1].split('.')[0]
               for email in email_set):
            continue
        # Skip tokens that look like email local-parts (contain @ but are incomplete)
        if not is_password_context:
            if '@' in token and '.' not in token.split('@')[-1]:
                continue

        # Skip USN / Register Numbers (VTU USN: e.g. 4SU22CS099 or lowercase)
        if re.match(r'^\d[a-zA-Z]{2}\d{2}[a-zA-Z]{2}\d{3}$', token):
            continue

        # 2. Skip other potential USN/academic formats
        # e.g., USN style roll numbers, sometimes starts with 1-4 letters followed by digits, e.g. SDM22CS099
        if re.match(r'^[a-zA-Z]{2,4}\d{2}[a-zA-Z]{2}\d{3}$', token):
            continue

        # 3. Skip UUCMS register numbers (e.g. U18CM23C0045, U25UV25T029139, P25UV24T069008, or lowercase)
        if re.match(r'^[uUpP]\d{2}[a-zA-Z]{2,4}\d{2}[a-zA-Z]{1,2}\d{3,6}$', token):
            continue

        # 3. Skip variable names, file paths, coding conventions
        if '_' in token:
            continue
        if '/' in token or '\\' in token or ('.' in token and not re.search(r'[@#$!%^&*\-]', token)):
            continue
        if re.search(r'[a-z][A-Z]', token):
            continue

        # ── STRICT 3-CLASS COMPLEXITY REQUIREMENT ───────────────────────────
        # A real heuristic password must have BOTH upper AND lower case letters
        # AND at least one digit OR special character.
        # However, if we are in a labeled password context (like "New password"),
        # we relax this since users often use lowercase-only passwords (e.g. sujay@1234).
        has_upper   = bool(re.search(r'[A-Z]', token))
        has_lower   = bool(re.search(r'[a-z]', token))
        has_digit   = bool(re.search(r'[0-9]', token))
        has_special = bool(re.search(r'[@#$!%^&*_\-]', token))

        if not is_password_context:
            # Standard heuristic (high barrier to prevent generic UI noise)
            if not (has_upper and has_lower and (has_digit or has_special)):
                continue
            
            # Minimum Length: 8 chars — always, no exceptions
            if len(token) < 8:
                continue

            # Shannon Entropy Threshold: must look sufficiently random
            if _shannon_entropy(token) < 3.2:
                continue
        else:
            # Labeled password context (relaxed complexity)
            # Require at least one letter and (digit or special character)
            has_letter = bool(re.search(r'[a-zA-Z]', token))
            if not (has_letter and (has_digit or has_special)):
                continue
            
            # Minimum Length: 6 chars in password context
            if len(token) < 6:
                continue

            # Shannon Entropy Threshold: relaxed to 2.2
            if _shannon_entropy(token) < 2.2:
                continue

        found.add(token)

    return list(found)



# ─── Exposure Score & Risk Level ──────────────────────────────────────────────
#
# Weight table (per finding type, per item):
#   password / credential : 35 pts  — extremely sensitive
#   aadhaar               : 40 pts  — unique national ID
#   pan_card              : 30 pts  — financial identity
#   credit_card           : 35 pts  — financial data
#   cvv                   : 35 pts  — cardholder verification
#   dob                   : 20 pts  — personal identity
#   email                 : 15 pts  — personally identifiable
#   phone                 : 12 pts  — personally identifiable
#   otp                   : 25 pts  — authentication secret
#
# Risk thresholds (out of 100, clamped):
#   CRITICAL : score >= 75
#   HIGH     : score >= 45
#   MEDIUM   : score >= 20
#   LOW      : score < 20

_WEIGHTS = {
    "aadhaar":     50,
    "password":    40,
    "credit_card": 40,
    "cvv":         38,
    "pan_card":    45,
    "otp":         30,
    "dob":         25,
    "email":       18,
    "phone":       15,
    "person_name": 20,
    "id_number":   30,
}

def calculate_privacy_score(findings_by_type: dict, doc_type: str = "generic") -> tuple:
    """
    findings_by_type: dict mapping finding type -> list of values
    doc_type: the classified document type (used to cap NER-soft contributions)
    Returns (score: float, risk_level: str)
    """
    raw = 0.0
    has_critical_pii = False
    CRITICAL_TYPES = {"aadhaar", "pan_card", "credit_card", "password", "cvv"}
    # NER-derived soft types that should be capped for low-risk documents
    NER_SOFT_TYPES  = {"person_name", "location", "organization", "demographic", "date", "id_number"}
    LOW_RISK_DOCS   = {"ml_notebook", "project_synopsis", "generic", "academic", "unknown"}

    ner_soft_raw = 0.0

    for ftype, items in findings_by_type.items():
        weight = _WEIGHTS.get(ftype, 10)
        count = len(items)
        if count == 0:
            continue
        if ftype in CRITICAL_TYPES:
            has_critical_pii = True
        # Diminishing returns: each additional item adds less
        # first item = full weight, second = 70%, third+ = 50%
        if count == 1:
            pts = weight
        elif count == 2:
            pts = weight + weight * 0.7
        else:
            pts = weight + weight * 0.7 + weight * 0.5 * (count - 2)

        if ftype in NER_SOFT_TYPES:
            ner_soft_raw += pts
        else:
            raw += pts

    # For low-risk doc types, cap NER soft contributions to 15 pts
    if doc_type in LOW_RISK_DOCS:
        raw += min(ner_soft_raw, 15.0)
    else:
        raw += ner_soft_raw

    # Clamp to 0–100
    score = min(round(raw, 1), 100.0)

    # Minimum floor: if critical PII types are found, score cannot be below 40
    if has_critical_pii and score < 40:
        score = max(score, 40.0)

    # CRITICAL requires both a high score AND at least one hard PII type
    if score >= 80 and has_critical_pii:
        risk = "CRITICAL"
    elif score >= 75:
        # High score even without hard PII — still HIGH not CRITICAL
        risk = "HIGH"
    elif score >= 35:
        risk = "HIGH"
    elif score >= 15:
        risk = "MEDIUM"
    else:
        risk = "LOW"

    return score, risk


# ─── Full Document Analysis ───────────────────────────────────────────────────

def _mask(text: str, pattern, replacement: str = "XXXX") -> str:
    """Replace all matches of pattern in text with replacement."""
    return pattern.sub(replacement, text)


def _detect_labeled_names(text: str) -> list[str]:
    names = set()
    keywords = ["name", "full name", "given names", "surname", "holder name", "holder's name", "cardholder name"]
    for kw in keywords:
        for m in re.finditer(r'\b' + re.escape(kw) + r'\b', text, re.I):
            window = text[m.end() : m.end() + 60].strip()
            match = re.search(r'^[:\s\n\-\|/=\[\]\(\)]+([A-Z][a-zA-Z\s]{2,30})\b', window)
            if match:
                val = match.group(1).strip()
                words = val.split()
                if 1 <= len(words) <= 4:
                    val_low = val.lower()
                    if val_low not in _IGNORE_WORDS:
                        names.add(val)
    return list(names)


def _detect_id_numbers(text: str) -> list[str]:
    id_numbers = set()
    keywords = [
        "id number", "identity number", "card number", "document number",
        "passport no", "passport number", "dl no", "licence no", "license no",
        "id no", "id num", "identity doc no", "doc number", "id doc"
    ]
    for kw in keywords:
        for m in re.finditer(r'\b' + re.escape(kw) + r'\b', text, re.I):
            window = text[m.end() : m.end() + 60].strip()
            match = re.search(r'^[:\s\n\-\|/=\[\]\(\)]+([A-Z0-9\-]{4,20})\b', window, re.I)
            if match:
                val = match.group(1).strip()
                val_low = val.lower()
                if val_low not in _IGNORE_WORDS and not val.isdigit() and len(val) >= 4:
                    id_numbers.add(val)
    return list(id_numbers)


def _detect_dobs(text: str) -> list[str]:
    """
    Detect Date of Birth values only.

    Rules:
    - Only fire on TRUE DOB keywords: "date of birth", "dob", "d.o.b", "born on", "birth date"
    - Do NOT fire on: "date of issue", "date of expiry", "valid till" — those are NOT DOBs
    - Year must be in range 1900–2025 (rejects card numbers, Aadhaar chunks, etc.)
    - Max 1 DOB per document (a person has exactly one date of birth)
    - Deduplication by normalised digits only
    """
    dobs = set()
    month_pattern = (
        r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?"
        r"|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
    )

    dob_month   = re.compile(r"\b\d{1,2}(?:\s+|[/-])" + month_pattern + r"(?:\s+|[/-])\d{2,4}\b", re.I)
    dob_numeric = re.compile(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\b")

    # ── STRICT DOB-ONLY keywords (do NOT include issue/expiry/valid) ──────────
    TRUE_DOB_KEYWORDS = [
        "date of birth", "dob", "d.o.b", "born on", "birth date", "birthdate",
        "date of birth:", "dob:", "d.o.b:"
    ]

    def _valid_year(date_str: str) -> bool:
        """Return True if date string contains a plausible birth year."""
        years = re.findall(r"\b(19\d{2}|20[01]\d|202[0-5])\b", date_str)
        # Also handle 2-digit years: 90 → 1990, 05 → 2005
        two_digit = re.findall(r"\b(\d{2})\b", date_str)
        for y in two_digit:
            yr = int(y)
            full = 1900 + yr if yr >= 30 else 2000 + yr
            if 1900 <= full <= 2025:
                years.append(str(full))
        return len(years) > 0

    def _normalise(date_str: str) -> str:
        """Strip non-digit chars for dedup comparison."""
        return re.sub(r"\D", "", date_str)

    seen_normalised = set()

    def _add(val: str):
        norm = _normalise(val)
        if norm and len(norm) >= 6 and norm not in seen_normalised:
            if _valid_year(val):
                seen_normalised.add(norm)
                dobs.add(val.strip())

    # ── Match: true DOB keyword followed by a date within 80 chars ───────────
    for kw in TRUE_DOB_KEYWORDS:
        for m in re.finditer(re.escape(kw), text, re.I):
            window = text[m.end(): m.end() + 80]
            # Try month-name format first (more specific)
            m_date = dob_month.search(window)
            if m_date:
                _add(m_date.group(0))
                continue
            # Try numeric format
            m_num = dob_numeric.search(window)
            if m_num:
                _add(m_num.group(0))

    # ── Inline format: "DOB: 15/03/1992" captured as group ───────────────────
    inline = re.compile(
        r"\b(?:dob|date\s+of\s+birth|born\s+on|birthdate)"
        r"[:\s\n\-\|/=\[\]\(\)]+(\d{1,2}(?:\s+|[/-])" + month_pattern + r"(?:\s+|[/-])\d{2,4})\b",
        re.I,
    )
    for m in inline.finditer(text):
        _add(m.group(1))

    inline_num = re.compile(
        r"\b(?:dob|date\s+of\s+birth|born\s+on|birthdate)"
        r"[:\s\n\-\|/=\[\]\(\)]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b",
        re.I,
    )
    for m in inline_num.finditer(text):
        _add(m.group(1))

    # ── Limit to 1 result (a person has exactly one DOB) ─────────────────────
    result = list(dobs)
    return result[:1]   # return only the first / most likely DOB



def analyze_document(file_path: str) -> dict:
    import os as _os
    text = extract_text_from_file(file_path)
    # ── Clean OCR output before analysis ────────────────────────────────────
    text = _clean_ocr_text(text)

    # ── AI Document Classification ─────────────────────────────────────────────
    # Runs after text extraction — provides document context before regex/NER.
    # Model is fully abstracted: change MODEL_NAME in .env to swap models.
    filename = _os.path.basename(file_path)
    
    # ── Smart Processing (Early Exit for short/clear files) ─────────────────────
    # Strategy:
    #   1. HIGH-CONFIDENCE bypass: if keyword classifier is very sure (>= 0.75), skip
    #      DeBERTa regardless of text length — DeBERTa won't do better on clear patterns.
    #   2. SHORT-TEXT bypass: if text < 800 chars AND keyword confidence >= 0.60, skip
    #      DeBERTa — short text lacks enough context for transformer NLI anyway.
    from backend.ai.document_classifier import _keyword_classify
    fast_clf = _keyword_classify(text, filename=filename)
    
    ai_doc = None
    ai_doc_type = "generic"
    ai_confidence = 0.0
    _ai_available = False

    _use_fast = (
        # Always bypass if keyword is very highly confident (screenshot passwords, Aadhaar, etc.)
        (fast_clf["confidence"] >= 0.65 and fast_clf["document_type"] != "generic")
        or
        # Also bypass for short docs where DeBERTa is overkill
        (len(text) < 800 and fast_clf["confidence"] >= 0.60 and fast_clf["document_type"] != "generic")
    )
    
    if _use_fast:
        import logging as _logging
        _logging.getLogger(__name__).info(
            "[Smart Processing] Bypassing AI model for '%s' (length %d). Keyword: %s (%.0f%%)", 
            filename, len(text), fast_clf["document_type"], fast_clf["confidence"] * 100
        )
        ai_doc = fast_clf
        ai_doc_type = ai_doc["document_type"]
        ai_confidence = ai_doc["confidence"]
        _ai_available = True
    else:
        # Run full heavy DeBERTa pipeline for medium/large or truly ambiguous files
        try:
            from backend.ai.document_classifier import classify_document
            ai_doc = classify_document(text, filename=filename)
            ai_doc_type   = ai_doc["document_type"]
            ai_confidence = ai_doc["confidence"]
            _ai_available = True
        except Exception as _exc:
            import logging as _logging
            _logging.getLogger(__name__).warning("AI doc classifier error: %s", _exc)
            ai_doc = fast_clf
            ai_doc_type = ai_doc["document_type"]
            ai_confidence = ai_doc["confidence"]
            _ai_available = False

    text_lower = text.lower()
    # is_academic: also triggered by AI classification result
    is_academic = (
        ai_doc_type in {"project_synopsis", "ml_notebook"}
    ) or any(kw in text_lower for kw in [
        "synopsis", "academic", "semester", "project report", "problem statement",
        "guided by", "submitted by", "literature survey", "future scope", "vtu", "usn", "uucms",
        "syllabus", "curriculum", "marks card", "grade card", "examination",
        "sklearn", "scikit", "import pandas", "import numpy", "import sklearn",
        "from sklearn", "load_breast_cancer", "train_test_split", "cross_val_score",
        "k-nearest", "k-means", "kmeans", "knn", "breast cancer", "iris dataset",
        "confusion matrix", "random forest", "decision tree", "neural network",
        "matplotlib", "seaborn", "jupyter", "notebook", "colab", "ipynb",
        "def ", "import ", "print(", "return ", "class ", "self.",
    ])

    # ── PRIORITY PIPELINE ─────────────────────────────────────────────────────

    # 1. Emails
    emails    = list(set(_EMAIL_PATTERN.findall(text)))
    email_set = set(emails)

    # 2. Aadhaar
    aadhaars = list(set(_AADHAAR_PATTERN.findall(text)))

    # 3. PAN
    pans     = list(set(_PAN_PATTERN.findall(text)))

    # 4. Credit cards
    cards    = list(set(_CARD_PATTERN.findall(text)))

    # 5. Phones
    phones   = list(set(_PHONE_PATTERN.findall(text)))

    # 6. DOB
    dobs     = _detect_dobs(text)

    # 7. CVV
    cvvs     = [m.group(1) for m in _CVV_PATTERN.finditer(text)]

    # 8. OTP (masked text to avoid Aadhaar/phone cross-detection)
    masked_for_otp = text
    masked_for_otp = _mask(masked_for_otp, _AADHAAR_PATTERN)
    masked_for_otp = _mask(masked_for_otp, _PHONE_PATTERN)
    phone_set = set(phones)
    year_set  = set(_YEAR_PATTERN.findall(text))
    otps = [
        m.group(1).strip()
        for m in _OTP_CONTEXT_PATTERN.finditer(masked_for_otp)
        if m.group(1).strip() not in phone_set
        and m.group(1).strip() not in year_set
        and not _FISCAL_YEAR_PATTERN.search(m.group(1).strip())
    ]
    otps = list(set(otps))

    # 9. Passwords
    masked_for_pwd = text
    for e in emails:
        masked_for_pwd = masked_for_pwd.replace(e, "EMAIL_MASKED")
    passwords = _detect_passwords(masked_for_pwd, email_set=email_set, is_academic=is_academic)

    # 10. Labeled Names
    names = _detect_labeled_names(text)

    # 11. Labeled ID Numbers
    id_numbers = _detect_id_numbers(text)

    # ── DUPLICATE SUPPRESSION ─────────────────────────────────────────────────
    aadhaar_flat = set(re.sub(r"\s", "", a) for a in aadhaars)
    phones = [p for p in phones if p not in aadhaar_flat]

    findings_by_type = {
        "email":       emails,
        "phone":       phones,
        "password":    passwords,
        "aadhaar":     aadhaars,
        "pan_card":    pans,
        "credit_card": cards,
        "cvv":         cvvs,
        "dob":         dobs,
        "otp":         otps,
        "person_name": names,
        "id_number":   id_numbers,
    }

    scored = {k: v for k, v in findings_by_type.items() if v}
    score, risk = calculate_privacy_score(scored)

    # Flatten findings
    all_findings = []
    for ftype, items in findings_by_type.items():
        for val in items:
            all_findings.append({"type": ftype, "value": val.strip(), "method": "regex"})

    # ── Document Type Resolution ──────────────────────────────────────────────
    # Keyword classifier (baseline — always runs)
    doc_type_result = infer_document_type(text, findings_by_type)

    # AI classifier overrides when confidence >= 0.60
    if _ai_available and ai_doc and ai_confidence >= 0.60:
        final_type = ai_doc_type
        
        # ── CROSS-VALIDATION LAYER ──────────────────────────────────────────────
        # Ensure the AI's prediction is backed up by rule-based/regex evidence.
        # This prevents a project report mentioning "Aadhaar" from being classified as an Aadhaar Card.
        validation_rules = {
            "aadhaar_card":          ["aadhaar"],
            "pan_card_doc":          ["pan_card"],
            "screenshot_credential": ["password", "otp"],
            "driving_license":       ["id_number", "dob", "person_name"],
            "passport":              ["id_number", "dob", "person_name"],
            "student_id":            ["id_number", "person_name"],
            "marks_card":            ["id_number", "person_name", "dob"],
        }
        
        valid = True
        if final_type in validation_rules:
            required_any = validation_rules[final_type]
            if not any(findings_by_type.get(req) for req in required_any):
                valid = False
                logger.info("AI override rejected: Predicted '%s' but no matching regex findings found.", final_type)

        if valid:
            doc_type_result = {
                "document_type": final_type,
                "label":         ai_doc.get("label", "General Document"),
                "score_boost":   ai_doc.get("score_boost", 0),
                "confidence":    round(float(ai_confidence), 4),
                "ai_method":     ai_doc.get("method", "ai"),
            }

    doc_type = doc_type_result["document_type"]

    # Re-score with document type context
    score, risk = calculate_privacy_score(scored, doc_type=doc_type)

    return {
        "text":                     text,
        "emails":                   emails,
        "phones":                   phones,
        "passwords":                passwords,
        "findings":                 all_findings,
        "score":                    score,
        "risk_level":               risk,
        "document_type":            doc_type_result["document_type"],
        "document_type_label":      doc_type_result["label"],
        "document_type_boost":      doc_type_result["score_boost"],
        "document_type_confidence": doc_type_result["confidence"],
        "ai_doc_type":              ai_doc_type,
        "ai_doc_confidence":        ai_confidence,
        "ai_doc_method":            ai_doc.get("method", "fallback") if ai_doc else "fallback",
    }


# ─── Document Type Classifier ───────────────────────────────────────────────


def _has_word(text: str, kw: str) -> bool:
    """Check if kw exists as a whole word or boundary-aware pattern in text."""
    if len(kw) <= 4 or not kw.isalnum():
        return bool(re.search(r'\b' + re.escape(kw) + r'\b', text))
    return kw in text


# Each entry: (document_type, label, score_boost, [required_keywords], [optional_keywords], min_match)
# min_match: minimum number of keywords that must appear to confirm this document type
_DOC_TYPE_RULES = [
    (
        "passport",
        "Passport / Travel Document",
        15,
        ["passport"],  # required
        ["republic of india", "nationality", "place of birth", "date of issue",
         "date of expiry", "passport no", "given names", "surname"],
        2,  # at least 2 total keywords
    ),
    (
        "aadhaar_card",
        "Aadhaar Card",
        5,  # Aadhaar numbers already score high, small extra boost
        ["aadhaar", "uid"],  # required (at least one)
        ["uidai", "enrolment no", "enrollment no", "unique identification",
         "government of india", "your aadhaar"],
        1,
    ),
    (
        "pan_card_doc",
        "PAN Card",
        5,
        ["permanent account number"],   # 'pan' alone is too vague — must say the full phrase
        ["income tax department", "govt of india", "income tax", "assessee"],
        1,
    ),
    (
        "bank_statement",
        "Bank Statement",
        12,
        ["account no", "account number"],
        ["ifsc", "statement period", "opening balance", "closing balance",
         "cr", "dr", "transaction date", "debit", "credit", "bank statement",
         "passbook", "mini statement"],
        2,
    ),
    (
        "payslip",
        "Salary Slip / Payslip",
        15,
        [],
        ["gross salary", "net pay", "net salary", "basic salary", "deductions",
         "employee id", "employee code", "pf no", "pf number", "provident fund",
         "epf", "esi", "tds", "salary slip", "pay slip", "payslip",
         "ctc", "cost to company", "take home"],
        3,
    ),
    (
        "medical",
        "Medical / Health Record",
        15,
        [],
        ["patient name", "patient id", "diagnosis", "prescription", "dosage",
         "medicine", "mg", "doctor", "dr.", "hospital", "clinic", "opd",
         "blood group", "lab report", "test result", "symptoms",
         "medical report", "discharge summary", "blood pressure", "pulse rate"],
        3,
    ),
    (
        "resume",
        "Resume / CV",
        10,
        [],
        ["curriculum vitae", "resume", "work experience", "professional experience",
         "objective", "career objective", "references", "internship",
         "skills", "education", "projects", "achievements", "hobbies",
         "declaration", "date of birth", "marital status", "nationality"],
        4,
    ),
    (
        "marks_card",
        "Marks Card / Academic Certificate",
        5,
        [],
        ["marks obtained", "maximum marks", "grade", "cgpa", "gpa",
         "semester", "examination", "university", "roll no", "hall ticket",
         "result", "pass", "fail", "distinction", "subject code",
         "marks card", "grade card", "transcript"],
        3,
    ),
    (
        "invoice",
        "Invoice / Bill",
        5,
        [],
        ["invoice no", "invoice number", "bill to", "ship to", "total amount",
         "gst no", "gstin", "taxable amount", "cgst", "sgst", "igst",
         "subtotal", "grand total", "due date", "payment terms"],
        3,
    ),
    (
        "project_synopsis",
        "Project Synopsis / Academic Document",
        0,
        [],
        ["problem statement", "project planning", "future scope", "literature survey",
         "technical specifications", "synopsis", "under the guidance of", "department of",
         "bachelor of engineering", "master of technology", "college of engineering",
         "vtu", "usn", "uucms", "uucms no", "project report", "academic year", "visvesvaraya technological university",
         "proposed system", "methodology", "system design", "implementation details",
         "theta dynamics", "motivation", "deliverables", "background", "streamlit", "objectives",
         "milestones", "abstract", "introduction", "conclusions", "appendix", "project scope"],
        2,
    ),
    (
        "ml_notebook",
        "ML / Data Science Code",
        0,   # zero score boost — code files are not inherently sensitive
        [],
        ["sklearn", "scikit", "pandas", "numpy", "matplotlib", "seaborn",
         "train_test_split", "cross_val_score", "gridsearchcv",
         "k-nearest", "k-means", "kmeans", "knn",
         "breast cancer", "iris dataset", "mnist", "classification report",
         "confusion matrix", "random forest", "decision tree", "neural network",
         "tensorflow", "pytorch", "keras", "jupyter", "notebook", "colab",
         "import pandas", "import numpy", "import sklearn", "from sklearn"],
        2,
    ),
    (
        "screenshot_credential",
        "Screenshot — Credential / Password Visible",
        25,  # High sensitivity boost: credentials visible in screenshot = serious risk
        [],
        ["change your password", "reset password", "new password", "current password",
         "confirm password", "enter password", "forgot password", "password expired",
         "your account", "sign in", "log in", "login", "two-factor", "2fa",
         "verification code", "one time password", "otp", "security code",
         "unlock", "unlock pattern", "unlock pin",
         "password is at risk", "password was found", "compromised"],
        2,  # just 2 of the above is enough to flag this as risky
    ),
]


def infer_document_type(text: str, findings_by_type: dict | None = None) -> dict:
    """
    Lightweight keyword-based document type classifier.
    Returns the most likely document type and an associated score boost.

    Returns:
      {
        document_type: str,   # e.g. 'resume', 'bank_statement', 'generic'
        label: str,           # human-readable label
        score_boost: float,   # points to add to privacy score
        confidence: str,      # 'HIGH' | 'MEDIUM' | 'LOW'
      }
    """
    if not text:
        return {"document_type": "generic", "label": "Generic Document",
                "score_boost": 0, "confidence": "LOW"}

    text_lower = text.lower()

    best_type    = "generic"
    best_label   = "Generic Document"
    best_boost   = 0
    best_matches = 0
    best_confidence = "LOW"

    for doc_type, label, boost, required_kws, optional_kws, min_match in _DOC_TYPE_RULES:
        # All required keywords must appear
        if required_kws:
            if not any(_has_word(text_lower, kw) for kw in required_kws):
                continue

        # Count optional keyword hits
        total_kws    = required_kws + optional_kws
        match_count  = sum(1 for kw in total_kws if _has_word(text_lower, kw))

        if match_count >= min_match:
            # Prefer types with more keyword matches (more specific)
            if match_count > best_matches:
                best_matches   = match_count
                best_type      = doc_type
                best_label     = label
                best_boost     = boost
                # Confidence: HIGH if many matches, MEDIUM if borderline
                if match_count >= min_match * 2:
                    best_confidence = "HIGH"
                else:
                    best_confidence = "MEDIUM"

    # -- Intelligent Overrides and Downgrades --
    # If the document is classified as Aadhaar or PAN card but has NO validated findings of that type,
    # and it contains academic keywords, downgrade it to a Project Synopsis/Academic Document.
    # Otherwise, downgrade it to a Generic Document.
    if findings_by_type is not None:
        if best_type == "aadhaar_card" and not findings_by_type.get("aadhaar"):
            academic_kws = ["problem statement", "project planning", "future scope", 
                            "literature survey", "synopsis", "under the guidance of", 
                            "department of", "bachelor of engineering", "college of engineering",
                            "vtu", "usn", "uucms", "uucms no", "project report", "academic year",
                            "theta dynamics", "motivation", "deliverables", "background", "streamlit", "objectives",
                            "milestones", "abstract", "introduction", "conclusions", "appendix", "project scope"]
            academic_match_count = sum(1 for kw in academic_kws if _has_word(text_lower, kw))
            if academic_match_count >= 2:
                best_type = "project_synopsis"
                best_label = "Project Synopsis / Academic Document"
                best_boost = 0
                best_confidence = "HIGH"
            else:
                best_type = "generic"
                best_label = "Generic Document"
                best_boost = 0
                best_confidence = "LOW"
        elif best_type == "pan_card_doc" and not findings_by_type.get("pan_card"):
            academic_kws = ["problem statement", "project planning", "future scope", 
                            "literature survey", "synopsis", "under the guidance of", 
                            "department of", "bachelor of engineering", "college of engineering",
                            "vtu", "usn", "uucms", "uucms no", "project report", "academic year",
                            "theta dynamics", "motivation", "deliverables", "background", "streamlit", "objectives",
                            "milestones", "abstract", "introduction", "conclusions", "appendix", "project scope"]
            academic_match_count = sum(1 for kw in academic_kws if _has_word(text_lower, kw))
            if academic_match_count >= 2:
                best_type = "project_synopsis"
                best_label = "Project Synopsis / Academic Document"
                best_boost = 0
                best_confidence = "HIGH"
            else:
                best_type = "generic"
                best_label = "Generic Document"
                best_boost = 0
                best_confidence = "LOW"
        elif best_type == "screenshot_credential":
            # If no passwords, emails, OTPs, CVVs, credit cards, or national IDs are present, downgrade
            has_credentials = any(findings_by_type.get(k) for k in ["password", "email", "otp", "credit_card", "cvv", "aadhaar", "pan_card"])
            if not has_credentials:
                best_type = "screenshot_auth"
                best_label = "Screenshot — Authentication Screen (No Credentials Visible)"
                best_boost = 0
                best_confidence = "HIGH"

    return {
        "document_type": best_type,
        "label":         best_label,
        "score_boost":   best_boost,
        "confidence":    best_confidence,
    }
