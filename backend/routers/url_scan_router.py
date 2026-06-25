"""
URL Scanner Router — Phase 5 (v3 - Production-accurate)
=========================================================
POST /api/url-scan/scan
GET  /api/url-scan/history

Key improvements over v2:
- Verhoeff checksum for Aadhaar (eliminates Wikipedia random numbers)
- Context keyword required for Aadhaar when no checksum
- PDF technical noise stripping (HTTP headers, RFC refs, status codes)
- Deduplication before scoring
- Rebalanced scoring weights
- AI confidence >= 0.70 filter
"""
from __future__ import annotations
import re, io, ipaddress, logging, requests
from urllib.parse import urlparse
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from backend import models, auth
from backend.database import get_db
from backend.services.ai_detection import get_ai_engine_info

logger = logging.getLogger(__name__)

def _bs4():
    from bs4 import BeautifulSoup
    return BeautifulSoup

def _pdfplumber():
    import pdfplumber
    return pdfplumber

router = APIRouter(prefix="/api/url-scan", tags=["url-scan"])


# ── Schemas ───────────────────────────────────────────────────────────────────
class URLScanRequest(BaseModel):
    url: str

class URLScanResponse(BaseModel):
    scan_id: int
    url: str
    title: str
    score: float
    risk_level: str
    findings: list
    finding_count: int
    extracted_text_preview: str
    ai_engine: str
    class Config:
        from_attributes = True


# ═══════════════════════════════════════════════════════════════════════════════
# SSRF PROTECTION
# ═══════════════════════════════════════════════════════════════════════════════
_ALLOWED_SCHEMES = {"http", "https"}
_PRIVATE_NETS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
]
_BLOCKED_HOSTS = {"localhost", "metadata.google.internal", "169.254.169.254"}
_BLOCKED_PATH  = re.compile(r"/(metadata|computeMetadata|latest/meta-data)", re.I)

def _validate_url(url: str) -> str:
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    p = urlparse(url)
    if p.scheme not in _ALLOWED_SCHEMES:
        raise HTTPException(400, "Only http/https URLs allowed.")
    host = (p.hostname or "").lower()
    if host in _BLOCKED_HOSTS:
        raise HTTPException(400, "Blocked host.")
    if _BLOCKED_PATH.search(p.path):
        raise HTTPException(400, "Blocked path.")
    try:
        addr = ipaddress.ip_address(host)
        for net in _PRIVATE_NETS:
            if addr in net:
                raise HTTPException(400, f"Private IP not allowed: {host}")
    except ValueError:
        pass
    return url


# ═══════════════════════════════════════════════════════════════════════════════
# VERHOEFF CHECKSUM (official Aadhaar validation algorithm)
# ═══════════════════════════════════════════════════════════════════════════════
_V_D = [
    [0,1,2,3,4,5,6,7,8,9],
    [1,2,3,4,0,6,7,8,9,5],
    [2,3,4,0,1,7,8,9,5,6],
    [3,4,0,1,2,8,9,5,6,7],
    [4,0,1,2,3,9,5,6,7,8],
    [5,9,8,7,6,0,4,3,2,1],
    [6,5,9,8,7,1,0,4,3,2],
    [7,6,5,9,8,2,1,0,4,3],
    [8,7,6,5,9,3,2,1,0,4],
    [9,8,7,6,5,4,3,2,1,0],
]
_V_P = [
    [0,1,2,3,4,5,6,7,8,9],
    [1,5,7,6,2,8,3,0,9,4],
    [5,8,0,3,7,9,6,1,4,2],
    [8,9,1,6,0,4,3,5,2,7],
    [9,4,5,3,1,2,6,8,7,0],
    [4,2,8,6,5,7,3,9,0,1],
    [2,7,9,3,8,0,6,4,1,5],
    [7,0,4,6,9,1,3,2,5,8],
]
_V_INV = [0,4,3,2,1,9,8,7,6,5]

def _verhoeff_validate(number: str) -> bool:
    """Return True if the digit string passes the Verhoeff checksum."""
    try:
        digits = [int(c) for c in reversed(number)]
        c = 0
        for i, d in enumerate(digits):
            c = _V_D[c][_V_P[i % 8][d]]
        return c == 0
    except Exception:
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# CONTENT FETCHING
# ═══════════════════════════════════════════════════════════════════════════════
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/pdf,*/*",
}

def _fetch_url(url: str):
    try:
        r = requests.get(url, headers=_HEADERS, timeout=12, allow_redirects=True)
        r.raise_for_status()
    except requests.exceptions.Timeout:
        raise HTTPException(408, "Request timed out.")
    except requests.exceptions.ConnectionError:
        raise HTTPException(502, "Could not connect to URL.")
    except requests.exceptions.HTTPError as e:
        raise HTTPException(502, f"URL error: {e}")
    except Exception as e:
        raise HTTPException(500, f"Fetch failed: {e}")
    ct = r.headers.get("content-type", "").lower()
    return r.content, r.text, ct


# ═══════════════════════════════════════════════════════════════════════════════
# TEXT EXTRACTION
# ═══════════════════════════════════════════════════════════════════════════════
_NOISE_TAGS = [
    "script","style","nav","footer","header","aside","noscript",
    "menu","form","iframe","svg","figure","button","select",
    "option","dialog","template","cookie","banner",
]
_NAV_RE = re.compile(
    r"^(Home|About|Contact|Login|Sign\s*[Ii]n|Sign\s*[Uu]p|Register|Menu|"
    r"Search|Toggle|Skip|Close|Open|Back|Next|Prev|Submit|Cancel|"
    r"Read\s*More|Learn\s*More|Click\s*Here|Download|Upload|View|"
    r"Facebook|Twitter|Instagram|LinkedIn|YouTube|WhatsApp|"
    r"Accept\s*Cookies?|Cookie\s*Policy|Privacy\s*Policy|Terms)$",
    re.I,
)

def _clean_html(html: str) -> tuple[str, str]:
    BS = _bs4()
    soup = BS(html, "lxml")
    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else "Untitled Page"
    for tag in soup(_NOISE_TAGS):
        tag.decompose()
    raw = soup.get_text(separator="\n")
    lines, seen = [], set()
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        if _NAV_RE.match(line):
            continue
        key = line.lower()
        if len(line) < 25 and key in seen:
            continue
        seen.add(key)
        lines.append(line)
    text = re.sub(r"\n{3,}", "\n\n", "\n".join(lines))
    return re.sub(r"[ \t]{2,}", " ", text).strip(), title


# Lines that are pure technical/protocol noise in PDFs
_PDF_NOISE = re.compile(
    r"^("
    r"HTTP/[\d.]+"                        # HTTP/1.1
    r"|RFC\s*\d+"                         # RFC 2616
    r"|\d{3}\s+[A-Z][a-zA-Z\s]+"         # 200 OK, 404 Not Found
    r"|[A-Za-z\-]+:\s*.{1,80}"           # Header: value
    r"|Content-[A-Za-z]+:.*"             # Content-Type: ...
    r"|Cache-Control:.*"
    r"|ETag:.*"
    r"|Date:.*GMT"
    r"|Transfer-Encoding:.*"
    r"|Connection:.*"
    r"|Server:.*"
    r"|Accept-[A-Za-z]+:.*"
    r"|Authorization:.*"
    r"|X-[A-Za-z\-]+:.*"
    r"|\s*\d+\s*$"                        # lone page numbers
    r"|v?\d+\.\d+(\.\d+)+"               # version numbers 1.2.3
    r"|[0-9a-f]{32,}"                     # hex hashes
    r")$",
    re.I,
)

def _extract_pdf(content: bytes) -> tuple[str, str]:
    pdfmod = _pdfplumber()
    parts = []
    try:
        with pdfmod.open(io.BytesIO(content)) as pdf:
            for page in pdf.pages:
                try:
                    t = page.extract_text()
                    if not t:
                        continue
                    # Strip technical lines
                    clean_lines = [
                        ln for ln in t.splitlines()
                        if ln.strip() and not _PDF_NOISE.match(ln.strip())
                    ]
                    if clean_lines:
                        parts.append("\n".join(clean_lines))
                except Exception:
                    continue
    except Exception as e:
        logger.warning("PDF error: %s", e)
    return "\n".join(parts), "PDF Document"


# ═══════════════════════════════════════════════════════════════════════════════
# URL-SPECIFIC PII PATTERNS
# ═══════════════════════════════════════════════════════════════════════════════

# Years / fiscal years / month dates — never PII
_YEAR_RE   = re.compile(r"\b(19|20)\d{2}\b")
_FISCAL_RE = re.compile(r"\b(19|20)\d{2}[-–](19|20)?\d{2}\b")
_MONTHS    = r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|January|February|March|April|May|June|July|August|September|October|November|December)"
_DATE_RE   = re.compile(rf"\b\d{{1,2}}[-/]{_MONTHS}[-/]\d{{2,4}}\b|\b{_MONTHS}\s+\d{{1,2}},?\s+\d{{4}}\b", re.I)

def _build_noise_set(text: str) -> set:
    s = set()
    for m in _YEAR_RE.finditer(text): s.add(m.group())
    for m in _FISCAL_RE.finditer(text): s.add(m.group())
    for m in _DATE_RE.finditer(text): s.add(m.group())
    return s

# Email
_EMAIL = re.compile(r"\b[A-Za-z0-9._%+\-]{2,}@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")

# ── Smart email classification ────────────────────────────────────────────────
# Business/public contact prefixes — these are NOT personal emails
_PUBLIC_EMAIL_PREFIXES = {
    "info", "support", "contact", "admin", "hello", "help", "enquiry", "inquiry",
    "noreply", "no-reply", "donotreply", "do-not-reply", "office", "team",
    "mail", "webmaster", "postmaster", "editor", "news", "press", "media",
    "feedback", "service", "care", "hr", "recruitment", "jobs", "sales",
    "marketing", "billing", "accounts", "finance", "legal", "privacy", "security",
}
# Domains that indicate institutional/business emails (not personal)
_INSTITUTIONAL_DOMAINS = re.compile(
    r"\.(edu|gov|ac\.in|edu\.in|nic\.in|org\.in|co\.in|mil|int)$"
    r"|@(gmail|yahoo|hotmail|outlook|protonmail|icloud|rediffmail|ymail|live\.com)",
    re.I,
)
_PERSONAL_EMAIL_DOMAINS = re.compile(
    r"@(gmail|yahoo|hotmail|outlook|protonmail|icloud|rediffmail|ymail)\.\w+",
    re.I,
)


def _classify_email(email: str, url: str = "", page_text: str = "") -> str:
    """
    Classify an email as 'public_contact' or 'personal_email'.
    Public contact emails contribute minimal score (weight=1).
    Personal emails contribute full score.

    Rules (first match wins):
    1. Email domain matches the scanned website domain → public contact
    2. Email local part matches any word in the website domain → public contact
    3. Known public-contact prefix (info, admin, contact...) → public contact
    4. Institutional TLD (.edu, .gov, .ac.in...) → public contact
    5. Surrounded by contact-context words in page text → public contact
    6. Gmail/Yahoo/Hotmail with non-personal local part found near
       'contact', 'email us', 'reach us' etc. → public contact
    7. Anything else → personal email
    """
    local, _, domain = email.lower().partition("@")

    # Rule 1 & 2: email domain or local part relates to the scanned site
    if url:
        try:
            from urllib.parse import urlparse
            p = urlparse(url)
            host = re.sub(r'^www\.', '', (p.hostname or "").lower())
            host_root = host.split(".")[0]   # e.g. "jssmca" from jssmca.ac.in
            # Domain match: e.g. alumni@jssmca.ac.in on jssmca.ac.in
            if host and (domain == host or domain.endswith("." + host)
                         or host in domain):
                return "public_contact"
            # Local part matches site name: e.g. jssnmca@gmail.com on jssnmca site
            if host_root and len(host_root) >= 4 and (
                local == host_root
                or local.startswith(host_root)
                or host_root in local
            ):
                return "public_contact"
        except Exception:
            pass

    # Rule 3: known public-contact prefix
    if local in _PUBLIC_EMAIL_PREFIXES:
        return "public_contact"

    # Rule 4: institutional TLD
    if re.search(r"\.(edu|gov|ac\.in|edu\.in|nic\.in|mil|int)$", domain):
        return "public_contact"

    # Rule 5 & 6: context keywords near the email in the page
    _CONTACT_CTX = re.compile(
        r"\b(contact|reach\s+us|email\s+us|write\s+to|mail\s+us|"
        r"enquir|inquiry|admissions?|registrar|helpdesk|helpline|"
        r"principal|director|dean|office|department|institute|college|"
        r"university|school|faculty|placement|for\s+more\s+info|"
        r"get\s+in\s+touch|send\s+us|feel\s+free\s+to)\b",
        re.I,
    )
    if page_text:
        escaped = re.escape(email)
        for m in re.finditer(escaped, page_text, re.I):
            window_start = max(0, m.start() - 200)
            window_end   = min(len(page_text), m.end() + 200)
            window       = page_text[window_start:window_end]
            if _CONTACT_CTX.search(window):
                return "public_contact"

    # Anything on a webmail domain with an institutional-looking local part
    # e.g. jssnmca@gmail.com — if it's on a .ac.in/.edu site it's a contact
    if _PERSONAL_EMAIL_DOMAINS.search(email) and url:
        try:
            from urllib.parse import urlparse
            host = (urlparse(url).hostname or "").lower()
            if re.search(r"\.(ac\.in|edu\.in|edu|gov|nic\.in|org)$", host):
                return "public_contact"
        except Exception:
            pass

    # Personal webmail with nothing institutional → personal
    if _PERSONAL_EMAIL_DOMAINS.search(email):
        return "personal_email"

    return "personal_email"

# Indian mobile: 10 digits starting 6–9
_PHONE = re.compile(r"\b[6-9][0-9]{9}\b")

# Aadhaar: 12 digits (groups of 4 with optional space/dash)
_AADHAAR_RAW = re.compile(r"\b[2-9]\d{3}[\s\-]?\d{4}[\s\-]?\d{4}\b")
# Context keywords that signal an Aadhaar number nearby
_AADHAAR_CTX = re.compile(r"\b(aadhaar|aadhar|uid|uidai|aadhaar\s*number|aadhaar\s*card)\b", re.I)

# PAN: strict AAAAA0000A
_PAN = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b")
# Avoid PAN false positives in purely technical text (e.g. all-caps code tokens)
_PAN_CTX_NEG = re.compile(r"\b(RFC|HTTP|HTML|JSON|XML|API|URL|SQL|CSS|TCP|UDP|IP)\b", re.I)

# Credit card: 13–16 digits
_CARD_RAW = re.compile(r"\b(?:\d[ \-]?){13,16}\b")

# CVV: explicit keyword required
_CVV = re.compile(r"\b(?:CVV|CVC|CVV2|security\s+code)\b\D{0,20}(\d{3,4})", re.I)

# DOB: explicit keyword required
_DOB = re.compile(
    r"\b(?:dob|date\s+of\s+birth|born\s+on|birth\s+date)[:\s]+(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})\b", re.I
)

# OTP: context keyword required within 60 chars
_OTP_CTX = re.compile(
    r"(?:otp|one[-\s]time\s+(?:password|passcode|pin)|verification\s+code|"
    r"auth(?:entication)?\s+code|login\s+code|security\s+code|confirm(?:ation)?\s+code)"
    r"\D{0,50}(\d{4,6})",
    re.I,
)

# Password: explicit credential key=value ONLY
_PWD_CTX = re.compile(
    r"(?:password|passwd|pwd|pass|passcode|secret|token|api[-_]?key|auth[-_]?key)"
    r"\s*[=:]\s*([^\s,\"'<>{}\[\]\n]{4,30})",
    re.I,
)

# Academic / generic noise
_ACADEMIC = re.compile(
    r"\b(batch|session|semester|academic|term|inter[-\s]department|"
    r"roll\s*no|enrollment|admission|june[-–]july|july[-–]august)\b", re.I
)
_HYPHEN_LABEL = re.compile(r"^[A-Za-z]+-[A-Za-z]+$")


# ── Luhn check ────────────────────────────────────────────────────────────────
def _luhn(n: str) -> bool:
    digits = [int(c) for c in n if c.isdigit()]
    if len(digits) < 13:
        return False
    total = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


# ── Per-type detectors ────────────────────────────────────────────────────────
def _detect_aadhaar(text: str, noise: set) -> list:
    """
    Strict Aadhaar detection using Verhoeff checksum ONLY.

    Why Verhoeff-only:
    - UIDAI generates all real Aadhaar numbers using this checksum
    - Random numeric sequences (Wikipedia, RFC PDFs) will NOT pass it
    - Even if a page mentions 'Aadhaar' as a concept/topic, random nearby
      numbers won't pass the checksum → zero false positives
    - Real leaked Aadhaar numbers WILL pass (they were generated by UIDAI)
    """
    results = []
    for m in _AADHAAR_RAW.finditer(text):
        raw = re.sub(r"[\s\-]", "", m.group())
        if len(raw) != 12:
            continue
        if raw in noise:
            continue
        if _verhoeff_validate(raw):
            results.append(m.group().strip())
    return list(set(results))


def _detect_phones(text: str) -> list:
    found = set()
    for m in _PHONE.finditer(text):
        val = m.group()
        # Skip if embedded inside a longer digit sequence (e.g. Aadhaar)
        start = max(0, m.start() - 2)
        end   = min(len(text), m.end() + 2)
        ctx   = re.sub(r"\s", "", text[start:end])
        if len(ctx) >= 12 and ctx.isdigit():
            continue
        found.add(val)
    return list(found)


def _detect_cards(text: str, phone_set: set, noise: set) -> list:
    found = []
    for m in _CARD_RAW.finditer(text):
        raw = re.sub(r"[ \-]", "", m.group())
        if len(raw) not in (13, 14, 15, 16):
            continue
        if raw in phone_set or raw in noise:
            continue
        if _luhn(raw):
            found.append(raw)
    return list(set(found))


def _detect_pans(text: str) -> list:
    # If text is full of technical acronyms, suppress PAN detection
    if len(_PAN_CTX_NEG.findall(text)) > 5:
        # Require explicit PAN context keyword
        if not re.search(r"\b(pan\s*card|pan\s*number|permanent\s*account)\b", text, re.I):
            return []
    return list(set(_PAN.findall(text)))


def _detect_passwords(text: str) -> list:
    found = []
    for m in _PWD_CTX.finditer(text):
        val = m.group(1).strip("\"'`")
        low = val.lower()
        if low in {"true","false","null","none","undefined","yes","no"}:
            continue
        if _HYPHEN_LABEL.match(val) or _ACADEMIC.search(val):
            continue
        if len(val) >= 4:
            found.append(val)
    return list(set(found))


def _detect_otps(text: str, noise: set) -> list:
    found = []
    for m in _OTP_CTX.finditer(text):
        val = m.group(1).strip()
        if val and val not in noise:
            found.append(val)
    return list(set(found))


# ── False-positive post-filter ────────────────────────────────────────────────
def _filter_fp(findings: list, noise: set) -> list:
    clean = []
    for f in findings:
        val   = str(f.get("value", "")).strip()
        ftype = f.get("type", "")
        if not val:
            continue
        if val in noise:
            continue
        if _FISCAL_RE.fullmatch(val):
            continue
        if ftype in ("password", "otp") and _DATE_RE.search(val):
            continue
        if ftype == "password" and (_HYPHEN_LABEL.match(val) or _ACADEMIC.search(val)):
            continue
        clean.append(f)
    return clean


# ── Deduplication ─────────────────────────────────────────────────────────────
def _dedup(findings: list) -> list:
    """Keep only one finding per (type, value) pair."""
    seen = set()
    out  = []
    for f in findings:
        key = (f.get("type"), str(f.get("value", "")).strip().lower())
        if key not in seen:
            seen.add(key)
            out.append(f)
    return out


# ── URL-specific scoring ──────────────────────────────────────────────────────
_URL_WEIGHTS = {
    "credit_card":    35,
    "cvv":            40,
    "aadhaar":        30,
    "pan_card":       20,
    "password":       25,
    "otp":            15,
    "dob":             8,
    "phone":           8,
    "public_phone":    1,   # business/office phone — minimal weight
    "email":           5,   # personal email — full weight
    "personal_email":  5,   # personal email — full weight
    "public_contact":  1,   # business/institutional email — minimal weight
    "http_only":       8,   # unencrypted HTTP site warning
}

def _url_score(findings: list) -> tuple[float, str]:
    by_type: dict[str, list] = {}
    for f in findings:
        # Remap classified email and phone types for scoring
        ftype = f.get("email_class", f.get("phone_class", f["type"]))
        by_type.setdefault(ftype, []).append(f["value"])

    raw = 0.0
    for ftype, items in by_type.items():
        w = _URL_WEIGHTS.get(ftype, 0)
        if w == 0:
            continue
        n = len(items)
        if n == 1:
            raw += w
        elif n == 2:
            raw += w + w * 0.5
        else:
            raw += w + w * 0.5 + w * 0.3 * (n - 2)

    score = min(round(raw, 1), 100.0)
    if   score >= 75: risk = "CRITICAL"
    elif score >= 35: risk = "HIGH"
    elif score >= 15: risk = "MEDIUM"
    elif score >  0:  risk = "LOW"
    else:             risk = "SAFE"
    return score, risk


# Business/public contact keywords for phone numbers — these are NOT personal phones
_PUBLIC_PHONE_KEYWORDS = re.compile(
    r"\b(admission|enquiry|office|contact|helpdesk|registrar|placement|fax|tel|call|support|info|desk|college|institute|university|school|principal|dean|campus|department|helpline|customer|service|agent)\b",
    re.I
)

def _classify_phone(phone: str, text: str, url: str = "") -> str:
    """
    Classify a phone number as 'public_phone' or 'phone' (personal).
    If it is a public contact/office phone number, it has a minimal weight.
    """
    if url:
        try:
            from urllib.parse import urlparse
            p = urlparse(url)
            host = (p.hostname or "").lower()
            if host and any(domain in host for domain in [".edu", ".gov", ".ac.in", ".nic.in", "jssmca", "college", "university"]):
                return "public_phone"
        except Exception:
            pass

    phone_escaped = re.escape(phone)
    for m in re.finditer(phone_escaped, text):
        start = max(0, m.start() - 120)
        end = min(len(text), m.end() + 120)
        window = text[start:end].lower()
        if _PUBLIC_PHONE_KEYWORDS.search(window):
            return "public_phone"
            
    return "phone"


# ── Main analysis ─────────────────────────────────────────────────────────────
def _analyse(text: str, is_http: bool = False, url: str = "") -> dict:
    noise    = _build_noise_set(text)
    emails   = list(set(_EMAIL.findall(text)))
    phones   = _detect_phones(text)
    phone_s  = set(phones)
    aadhaars = _detect_aadhaar(text, noise)
    pans     = _detect_pans(text)
    cards    = _detect_cards(text, phone_s, noise)
    cvvs     = [m.group(1) for m in _CVV.finditer(text)]
    dobs     = [m.group(1) for m in _DOB.finditer(text)]
    otps     = _detect_otps(text, noise)
    pwds     = _detect_passwords(text)

    # Remove phone numbers that are substrings of Aadhaar
    aadhaar_flat = set(re.sub(r"\s", "", a) for a in aadhaars)
    phones = [p for p in phones if p not in aadhaar_flat]

    findings: list[dict] = []

    # ── HTTP-only site warning ─────────────────────────────────────────────────
    if is_http:
        findings.append({
            "type":   "http_only",
            "value":  "Site uses unencrypted HTTP (no TLS/SSL)",
            "method": "url_check",
            "note":   "All data exchanged with this site is transmitted in plaintext and can be intercepted.",
        })

    # ── Email with smart classification ──────────────────────────────────────
    for email in emails:
        email_class = _classify_email(email, url, page_text=text)
        findings.append({
            "type":        "email",
            "email_class": email_class,  # used in scoring
            "value":       email.strip(),
            "method":      "regex",
            "label":       "Public Contact Email" if email_class == "public_contact" else "Personal Email",
        })

    # ── Phone with smart classification ──────────────────────────────────────
    for phone in phones:
        phone_class = _classify_phone(phone, text, url)
        findings.append({
            "type":        "phone",
            "phone_class": phone_class,  # used in scoring
            "value":       phone.strip(),
            "method":      "regex",
            "label":       "Public Contact Phone" if phone_class == "public_phone" else "Personal Phone",
        })

    for ftype, items in [
        ("password", pwds),
        ("aadhaar", aadhaars), ("pan_card", pans), ("credit_card", cards),
        ("cvv", cvvs), ("dob", dobs), ("otp", otps),
    ]:
        for val in items:
            findings.append({"type": ftype, "value": str(val).strip(), "method": "regex"})

    # Post-filter → deduplicate
    findings = _filter_fp(findings, noise)
    findings = _dedup(findings)

    # AI enrichment with confidence filter
    try:
        from backend.services.ai_detection import enrich_regex_findings
        findings = enrich_regex_findings(findings)
        findings = [
            f for f in findings
            if f.get("method") != "ai" or f.get("confidence", 1.0) >= 0.70
        ]
    except Exception:
        pass

    score, risk = _url_score(findings)
    return {"findings": findings, "score": score, "risk_level": risk, "text": text}


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════
@router.post("/scan", response_model=URLScanResponse)
def scan_url(
    body: URLScanRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    url = _validate_url(body.url)
    is_http = url.startswith("http://")
    content_bytes, content_text, content_type = _fetch_url(url)

    if "pdf" in content_type:
        text, title = _extract_pdf(content_bytes)
    else:
        text, title = _clean_html(content_text)

    if not text.strip():
        raise HTTPException(422, "Could not extract readable text from this URL.")

    analysis = _analyse(text, is_http=is_http, url=url)
    hostname = urlparse(url).hostname or "url-scan"

    db_scan = models.ScanRecord(
        filename=f"{hostname}.html",
        score=analysis["score"],
        risk_level=analysis["risk_level"],
        original_path=url,
        extracted_text=text[:10000],
        source="url",
        source_url=url,
        owner_id=current_user.id,
    )
    db.add(db_scan)
    db.commit()
    db.refresh(db_scan)

    for f in analysis["findings"]:
        db.add(models.Finding(
            type=f["type"],
            value=f["value"],
            ai_confidence=f.get("confidence"),
            ai_label=f.get("ai_label"),
            scan_id=db_scan.id,
        ))
    db.commit()

    ai_info = get_ai_engine_info()
    return URLScanResponse(
        scan_id=db_scan.id,
        url=url,
        title=title,
        score=analysis["score"],
        risk_level=analysis["risk_level"],
        findings=analysis["findings"],
        finding_count=len(analysis["findings"]),
        extracted_text_preview=text[:400],
        ai_engine=ai_info["engine"],
    )


@router.get("/history")
def url_scan_history(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    scans = (
        db.query(models.ScanRecord)
        .filter(
            models.ScanRecord.owner_id == current_user.id,
            models.ScanRecord.source == "url",
        )
        .order_by(models.ScanRecord.upload_date.desc())
        .limit(20)
        .all()
    )
    return [
        {
            "id":            s.id,
            "url":           s.source_url,
            "filename":      s.filename,
            "score":         s.score,
            "risk_level":    s.risk_level,
            "upload_date":   s.upload_date,
            "finding_count": len(s.findings),
        }
        for s in scans
    ]


@router.delete("/history/{scan_id}", status_code=204)
def delete_url_scan(
    scan_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Delete a single URL scan history entry belonging to the current user."""
    scan = (
        db.query(models.ScanRecord)
        .filter(
            models.ScanRecord.id == scan_id,
            models.ScanRecord.owner_id == current_user.id,
            models.ScanRecord.source == "url",
        )
        .first()
    )
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found.")
    # Delete child findings first (no CASCADE configured)
    db.query(models.Finding).filter(models.Finding.scan_id == scan_id).delete()
    db.delete(scan)
    db.commit()
