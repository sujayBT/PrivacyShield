"""
backend_entry.py — PyInstaller entry-point for PrivacyShield backend
Runs uvicorn serving the FastAPI app.
Data (DB, uploads, reports) is stored in PRIVACY_DATA_DIR (set by Electron).
"""
import os
import sys
import argparse

# ── Data directory ────────────────────────────────────────────────────────────
# Electron main.js sets PRIVACY_DATA_DIR = %APPDATA%\PrivacyShield
# On first launch, the SQLAlchemy engine will auto-create the DB there.
_data_dir = os.environ.get(
    "PRIVACY_DATA_DIR",
    os.path.dirname(os.path.abspath(__file__))
)

# Ensure subdirectories exist (new installation)
for _sub in ("uploads", "reports", "screenshots"):
    os.makedirs(os.path.join(_data_dir, _sub), exist_ok=True)

os.environ["PRIVACY_DATA_DIR"] = _data_dir

# ── sys.path fix for frozen bundle ────────────────────────────────────────────
if getattr(sys, "frozen", False):
    sys.path.insert(0, sys._MEIPASS)

# ── Parse args ────────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser(description="PrivacyShield Backend")
parser.add_argument("--host", default="127.0.0.1")
parser.add_argument("--port", type=int, default=int(os.environ.get("BACKEND_PORT", 8000)))
args, _ = parser.parse_known_args()

# ── Start server (always — frozen or not) ─────────────────────────────────────
import uvicorn

uvicorn.run(
    "backend.main:app",
    host=args.host,
    port=args.port,
    log_level="info",
)
