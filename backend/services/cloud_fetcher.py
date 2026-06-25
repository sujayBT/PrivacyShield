"""
Phase 7 — Cloud Fetcher Service
=================================
Downloads files from public cloud share links without requiring OAuth.
Supports:
  - Google Drive  : https://drive.google.com/file/d/{ID}/view
  - Dropbox       : https://www.dropbox.com/s/xxx/file?dl=0
  - OneDrive      : https://1drv.ms/... or onedrive.live.com share links
  - Direct URL    : any direct-download URL (http/https)

Returns: { path: str, filename: str, source: str, size_bytes: int }
Raises ValueError for unsupported / inaccessible links.
"""

from __future__ import annotations
import os
import re
import tempfile
import requests
from pathlib import Path
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

from backend.config import UPLOAD_DIR
TIMEOUT    = 30   # seconds
MAX_BYTES  = 20 * 1024 * 1024   # 20 MB cap


# ── URL transformers ─────────────────────────────────────────────────────────

def _gdrive_direct(url: str) -> tuple[str, str]:
    """Convert a Google Drive share URL to a direct download URL."""
    # Pattern 1: /file/d/{ID}/view
    m = re.search(r"/file/d/([A-Za-z0-9_-]+)", url)
    if m:
        file_id = m.group(1)
        return (
            f"https://drive.google.com/uc?export=download&id={file_id}",
            "gdrive"
        )
    # Pattern 2: ?id={ID}
    m2 = re.search(r"[?&]id=([A-Za-z0-9_-]+)", url)
    if m2:
        file_id = m2.group(1)
        return (
            f"https://drive.google.com/uc?export=download&id={file_id}",
            "gdrive"
        )
    raise ValueError("Could not extract Google Drive file ID from URL")


def _dropbox_direct(url: str) -> tuple[str, str]:
    """Convert Dropbox share link to direct download."""
    # Replace dl=0 with dl=1 or add dl=1
    if "dl=0" in url:
        return url.replace("dl=0", "dl=1"), "dropbox"
    if "dl=1" in url:
        return url, "dropbox"
    sep = "&" if "?" in url else "?"
    return url + sep + "dl=1", "dropbox"


def _onedrive_direct(url: str) -> tuple[str, str]:
    """Convert OneDrive share link to direct download."""
    # Short links: 1drv.ms → follow redirect and add download param
    # Full links: onedrive.live.com
    if "1drv.ms" in url or "onedrive.live.com" in url or "sharepoint.com" in url:
        # Append download=1 if not present
        sep = "&" if "?" in url else "?"
        download_url = url + sep + "download=1"
        return download_url, "onedrive"
    raise ValueError("Unrecognised OneDrive URL format")


def resolve_cloud_url(url: str) -> tuple[str, str]:
    """
    Detect cloud provider and return (direct_download_url, source_label).
    Falls back to treating the URL as a direct download link.
    """
    url = url.strip()
    lower = url.lower()

    if "drive.google.com" in lower or "docs.google.com" in lower:
        return _gdrive_direct(url)
    if "dropbox.com" in lower:
        return _dropbox_direct(url)
    if "1drv.ms" in lower or "onedrive.live.com" in lower or "sharepoint.com" in lower:
        return _onedrive_direct(url)

    # Direct download URL
    parsed = urlparse(url)
    if parsed.scheme in ("http", "https") and parsed.netloc:
        return url, "direct_url"

    raise ValueError(f"Unsupported URL format: {url}")


# ── Download helper ───────────────────────────────────────────────────────────

def _guess_ext(content_type: str, url: str) -> str:
    ct = content_type.split(";")[0].strip().lower()
    ext_map = {
        "application/pdf":  ".pdf",
        "image/jpeg":       ".jpg",
        "image/jpg":        ".jpg",
        "image/png":        ".png",
        "image/bmp":        ".bmp",
        "image/webp":       ".webp",
    }
    if ct in ext_map:
        return ext_map[ct]
    # Fall back to URL suffix
    suffix = Path(urlparse(url).path).suffix.lower()
    if suffix in {".pdf", ".png", ".jpg", ".jpeg", ".bmp", ".webp"}:
        return suffix
    return ".pdf"   # default


def _detect_real_ext(save_path: str, ct_ext: str) -> str:
    """
    Read the first 16 bytes of the saved file to detect its real type.
    Returns the correct extension regardless of what Content-Type said.
    """
    try:
        with open(save_path, "rb") as f:
            magic = f.read(16)
        if magic.startswith(b"%PDF"):
            return ".pdf"
        if magic.startswith(b"\x89PNG"):
            return ".png"
        if magic[:3] in (b"\xff\xd8\xff",):          # JPEG
            return ".jpg"
        if magic[:4] in (b"GIF8",):
            return ".gif"
        if magic[:4] in (b"PK\x03\x04",):            # ZIP-based (docx, xlsx, pptx)
            return ct_ext if ct_ext in (".docx", ".xlsx", ".pptx") else ".docx"
        # Check for HTML
        sample = magic.lower()
        if sample.startswith(b"<") or b"<html" in magic.lower():
            return ".html"
        # Check further in the file for HTML
        with open(save_path, "rb") as f:
            head = f.read(512).lower()
        if b"<html" in head or b"<!doctype" in head:
            return ".html"
    except Exception:
        pass
    return ct_ext  # trust Content-Type as fallback


def download_cloud_file(url: str, user_id: int) -> dict:
    """
    Download a file from a cloud share link.
    Returns: { path, filename, source, size_bytes }
    Raises ValueError / requests.RequestException on failure.
    """
    import time
    direct_url, source = resolve_cloud_url(url)

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    })

    # First request — follow redirects (needed for GDrive large-file warning)
    resp = session.get(direct_url, stream=True, timeout=TIMEOUT, allow_redirects=True)

    # ── Google Drive large-file confirmation ──────────────────────────────────
    if source == "gdrive":
        ct = resp.headers.get("Content-Type", "")
        if "text/html" in ct:
            confirm = None
            for k, v in resp.cookies.items():
                if "download_warning" in k:
                    confirm = v
            if confirm:
                resp = session.get(
                    direct_url + f"&confirm={confirm}",
                    stream=True, timeout=TIMEOUT
                )
            else:
                raise ValueError(
                    "Google Drive requires confirmation. Make sure the file is shared "
                    "publicly (Anyone with the link → Viewer) and is smaller than 100 MB."
                )

    resp.raise_for_status()

    ct      = resp.headers.get("Content-Type", "application/octet-stream")
    ct_ext  = _guess_ext(ct, direct_url)

    # Use a timestamp so repeated scans don't overwrite the same file
    ts = int(time.time())
    tmp_name  = f"cloud_{source}_{user_id}_{ts}{ct_ext}"
    save_path = os.path.join(UPLOAD_DIR, tmp_name)
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    total = 0
    with open(save_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            if chunk:
                total += len(chunk)
                if total > MAX_BYTES:
                    os.remove(save_path)
                    raise ValueError(f"File exceeds 20 MB limit ({total // 1024 // 1024} MB)")
                f.write(chunk)

    if total == 0:
        raise ValueError("Downloaded file is empty — check the share link permissions.")

    # ── Validate the real file type via magic bytes ───────────────────────────
    real_ext = _detect_real_ext(save_path, ct_ext)

    if real_ext != ct_ext:
        # Rename the file to its actual extension
        new_name = tmp_name.replace(ct_ext, real_ext)
        new_path = os.path.join(UPLOAD_DIR, new_name)
        os.rename(save_path, new_path)
        save_path = new_path
        tmp_name  = new_name

    # ── Reject non-scannable types ─────────────────────────────────────────────
    SUPPORTED = {".pdf", ".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tiff",
                 ".docx", ".xlsx", ".txt", ".html"}
    if real_ext not in SUPPORTED:
        os.remove(save_path)
        raise ValueError(
            f"Downloaded file type '{real_ext}' is not supported for scanning. "
            f"Supported: PDF, PNG, JPG, DOCX, XLSX, TXT."
        )

    return {
        "path":       save_path,
        "filename":   tmp_name,
        "source":     source,
        "size_bytes": total,
    }

