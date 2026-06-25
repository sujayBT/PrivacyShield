"""
Phase 14 — Background Agent Service
Folder watcher using watchdog + Windows notifications via plyer.
Runs in a background thread, auto-scans new files, fires OS popups on risk.
"""
import os
import threading
import json
import time
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# ── State ────────────────────────────────────────────────────────────────────
_agent_state = {
    "running":       False,
    "paused":        False,
    "started_at":    None,
    "watched_folders": [],
    "events":        [],        # list of dicts (recent scan events)
    "total_scanned": 0,
    "total_alerts":  0,
}
_observer = None   # watchdog observer instance
_lock = threading.Lock()

# Maximum events to keep in memory
MAX_EVENTS = 100

from backend.services.notify import send_risk_alert, send_agent_started, send_agent_stopped


# ── Event logging ─────────────────────────────────────────────────────────────
def _log_event(filename: str, score: float, risk: str, findings_count: int, file_path: str):
    event = {
        "id":             len(_agent_state["events"]) + 1,
        "timestamp":      datetime.utcnow().isoformat(),
        "filename":       filename,
        "file_path":      file_path,
        "score":          score,
        "risk_level":     risk,
        "findings_count": findings_count,
        "alerted":        risk not in ("SAFE", "LOW"),
    }
    with _lock:
        _agent_state["events"].insert(0, event)
        if len(_agent_state["events"]) > MAX_EVENTS:
            _agent_state["events"].pop()
        _agent_state["total_scanned"] += 1
        if event["alerted"]:
            _agent_state["total_alerts"] += 1
    return event


# ── File scanner (calls detection service directly) ───────────────────────────
def _scan_file(file_path: str):
    """Scan a file and fire notification if risk >= MEDIUM."""
    if _agent_state["paused"]:
        return
    try:
        from backend.services.detection import analyze_document
        result = analyze_document(file_path)
        
        doc_type = result.get("document_type", "generic")
        doc_label = result.get("document_type_label", "Generic Document")
        doc_boost = result.get("document_type_boost", 0)
        
        score = min(result.get("score", 0) + doc_boost, 100.0)
        risk  = result.get("risk_level", "SAFE")
        if doc_boost > 0:
            if score >= 75:   risk = "CRITICAL"
            elif score >= 35: risk = "HIGH"
            elif score >= 15: risk = "MEDIUM"
            else:             risk = "LOW"
            
        findings = result.get("findings", [])

            
        filename  = os.path.basename(file_path)

        _log_event(filename, score, risk, len(findings), file_path)

        # Only notify if MEDIUM or above — like antivirus software
        if risk not in ("SAFE", "LOW"):
            types_found = list({f["type"] for f in findings})
            send_risk_alert(
                source="file",
                name=filename,
                score=score,
                risk=risk,
                finding_types=types_found,
            )
            logger.info("Agent alert: %s → score=%.1f risk=%s", filename, score, risk)
        else:
            logger.info("Agent scan: %s → SAFE (score=%.1f)", filename, score)

    except Exception as e:
        logger.error("Agent scan error for %s: %s", file_path, e)


# ── Watchdog event handler ─────────────────────────────────────────────────────
WATCHED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt", ".png", ".jpg", ".jpeg", ".bmp", ".webp"}

def _make_handler():
    """Return a watchdog FileSystemEventHandler."""
    try:
        from watchdog.events import FileSystemEventHandler
    except ImportError:
        return None

    class _Handler(FileSystemEventHandler):
        def on_created(self, event):
            if event.is_directory:
                return
            ext = os.path.splitext(event.src_path)[1].lower()
            if ext in WATCHED_EXTENSIONS:
                # Small delay so the file is fully written
                time.sleep(1.5)
                threading.Thread(target=_scan_file, args=(event.src_path,), daemon=True).start()

    return _Handler()


# ── Public API ────────────────────────────────────────────────────────────────
def get_status() -> dict:
    with _lock:
        return {
            "running":         _agent_state["running"],
            "paused":          _agent_state["paused"],
            "started_at":      _agent_state["started_at"],
            "watched_folders": _agent_state["watched_folders"],
            "total_scanned":   _agent_state["total_scanned"],
            "total_alerts":    _agent_state["total_alerts"],
            "recent_events":   _agent_state["events"][:20],
        }


def _get_default_folders() -> list:
    """Return all common Windows user folders that exist."""
    home = os.path.expanduser("~")
    candidates = [
        os.path.join(home, "Downloads"),
        os.path.join(home, "Desktop"),
        os.path.join(home, "Documents"),
        os.path.join(home, "Pictures"),
        os.path.join(home, "Videos"),
        os.path.join(home, "Music"),
        os.path.join(home, "OneDrive"),
        os.path.join(home, "OneDrive", "Documents"),
        os.path.join(home, "OneDrive", "Desktop"),
        os.path.join(home, "OneDrive", "Pictures"),
    ]
    return [f for f in candidates if os.path.isdir(f)]


def start_agent(folders: list) -> dict:
    global _observer

    if _agent_state["running"]:
        return {"ok": False, "message": "Agent is already running."}

    try:
        from watchdog.observers import Observer
    except ImportError:
        return {"ok": False, "message": "watchdog library not installed. Run: pip install watchdog"}

    # Use passed folders if valid, else all defaults
    if folders:
        valid_folders = [f for f in folders if os.path.isdir(f)]
    else:
        valid_folders = _get_default_folders()

    if not valid_folders:
        return {"ok": False, "message": "No valid folders found to watch."}

    handler  = _make_handler()
    observer = Observer()
    for folder in valid_folders:
        observer.schedule(handler, folder, recursive=False)

    observer.start()
    _observer = observer

    with _lock:
        _agent_state["running"]         = True
        _agent_state["paused"]          = False
        _agent_state["started_at"]      = datetime.utcnow().isoformat()
        _agent_state["watched_folders"] = valid_folders

    send_agent_started(len(valid_folders))
    logger.info("Background agent started. Watching: %s", valid_folders)
    return {"ok": True, "message": "Agent started.", "folders": valid_folders}


def add_folder(folder_path: str) -> dict:
    """Add a new folder to the watcher while agent is running."""
    global _observer

    if not os.path.isdir(folder_path):
        return {"ok": False, "message": f"Path does not exist or is not a folder: {folder_path}"}

    with _lock:
        if folder_path in _agent_state["watched_folders"]:
            return {"ok": False, "message": "Folder is already being watched."}

    if _agent_state["running"] and _observer:
        try:
            from watchdog.observers import Observer
            handler = _make_handler()
            _observer.schedule(handler, folder_path, recursive=False)
        except Exception as e:
            return {"ok": False, "message": f"Could not add folder to watcher: {e}"}

    with _lock:
        _agent_state["watched_folders"].append(folder_path)

    logger.info("Folder added to watch: %s", folder_path)
    return {"ok": True, "message": f"Now watching: {folder_path}", "folders": _agent_state["watched_folders"]}


def remove_folder(folder_path: str) -> dict:
    """Remove a folder from the watched list (takes effect on next restart)."""
    with _lock:
        if folder_path not in _agent_state["watched_folders"]:
            return {"ok": False, "message": "Folder is not in the watch list."}
        _agent_state["watched_folders"].remove(folder_path)

    logger.info("Folder removed from watch list: %s", folder_path)
    return {"ok": True, "message": f"Removed: {folder_path}", "folders": _agent_state["watched_folders"]}


def get_all_candidate_folders() -> dict:
    """Return all common system folders + their watched status."""
    home = os.path.expanduser("~")
    candidates = [
        os.path.join(home, "Downloads"),
        os.path.join(home, "Desktop"),
        os.path.join(home, "Documents"),
        os.path.join(home, "Pictures"),
        os.path.join(home, "Videos"),
        os.path.join(home, "Music"),
        os.path.join(home, "OneDrive"),
        os.path.join(home, "OneDrive", "Documents"),
        os.path.join(home, "OneDrive", "Desktop"),
        os.path.join(home, "OneDrive", "Pictures"),
    ]
    watched = _agent_state["watched_folders"]
    result = []
    for f in candidates:
        result.append({
            "path":    f,
            "exists":  os.path.isdir(f),
            "watched": f in watched,
            "label":   os.path.basename(f),
        })
    return {"system_folders": result, "watched": watched}


def stop_agent() -> dict:
    global _observer
    if not _agent_state["running"]:
        return {"ok": False, "message": "Agent is not running."}

    if _observer:
        _observer.stop()
        _observer.join(timeout=3)
        _observer = None

    with _lock:
        _agent_state["running"]         = False
        _agent_state["paused"]          = False
        _agent_state["started_at"]      = None
        _agent_state["watched_folders"] = []

    send_agent_stopped()
    logger.info("Background agent stopped.")
    return {"ok": True, "message": "Agent stopped."}


def pause_agent() -> dict:
    if not _agent_state["running"]:
        return {"ok": False, "message": "Agent is not running."}
    with _lock:
        _agent_state["paused"] = not _agent_state["paused"]
    state = "paused" if _agent_state["paused"] else "resumed"
    return {"ok": True, "message": f"Agent {state}."}


def clear_events() -> dict:
    with _lock:
        _agent_state["events"] = []
    return {"ok": True, "message": "Events cleared."}
