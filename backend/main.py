from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from backend.database import engine, Base
from backend.routers import auth_router, scan_router
from backend.routers import url_scan_router
from backend.routers import cloud_router
from backend.routers import monitor_router
from backend.routers import social_router
from backend.routers import metadata_router
from backend.routers import attack_router
from backend.routers import history_router
from backend.routers import batch_scan_router
from backend.routers import agent_router
import logging
import os
import sys

logger = logging.getLogger(__name__)

# Create all tables (new tables only — doesn't drop existing ones)
Base.metadata.create_all(bind=engine)

# ── Safe column migrations for SQLite ──────────────────────────────────────
# SQLite doesn't support ALTER TABLE ... ADD COLUMN IF NOT EXISTS,
# so we attempt each ALTER and silently ignore "duplicate column" errors.
_MIGRATIONS = [
    "ALTER TABLE findings ADD COLUMN ai_confidence REAL",
    "ALTER TABLE findings ADD COLUMN ai_label TEXT",
    "ALTER TABLE scans ADD COLUMN source TEXT DEFAULT 'file'",
    "ALTER TABLE scans ADD COLUMN source_url TEXT",
    "ALTER TABLE scans ADD COLUMN extracted_text TEXT",
    # Phase 6 — Vision
    "ALTER TABLE scans ADD COLUMN vision_doc_type TEXT",
    "ALTER TABLE scans ADD COLUMN vision_face_count INTEGER DEFAULT 0",
    "ALTER TABLE scans ADD COLUMN vision_is_id_doc INTEGER DEFAULT 0",
    # AI classifier
    "ALTER TABLE scans ADD COLUMN ai_doc_type_label TEXT",
    "ALTER TABLE scans ADD COLUMN ai_doc_confidence REAL",
]

for sql in _MIGRATIONS:
    try:
        with engine.begin() as conn:
            conn.execute(__import__("sqlalchemy").text(sql))
            logger.info("Migration applied: %s", sql)
    except Exception:
        pass  # Column already exists — skip silently

app = FastAPI(title="Privacy Exposure Tool API v2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router)
app.include_router(scan_router.router)
app.include_router(url_scan_router.router)
app.include_router(cloud_router.router)
app.include_router(monitor_router.router)
app.include_router(social_router.router)
app.include_router(metadata_router.router)
app.include_router(attack_router.router)
app.include_router(history_router.router)
app.include_router(batch_scan_router.router)
app.include_router(agent_router.router)

# ── Production: serve the built React frontend ──────────────────────────────
# When packaged with PyInstaller, RESOURCES_PATH env var points to the
# Electron resources folder containing the pre-built frontend.
_frontend_dir = os.environ.get("ELECTRON_RESOURCES", "")
if _frontend_dir:
    _static_dir = os.path.join(_frontend_dir, "frontend")
else:
    # PyInstaller bundle: frontend is next to the backend exe
    _static_dir = os.path.join(
        getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__))),
        "frontend"
    )

if os.path.isdir(_static_dir):
    logger.info("Serving frontend from: %s", _static_dir)

    # Mount /assets static directory
    _assets = os.path.join(_static_dir, "assets")
    if os.path.isdir(_assets):
        app.mount("/assets", StaticFiles(directory=_assets), name="assets")

    @app.get("/", include_in_schema=False)
    async def serve_index():
        return FileResponse(os.path.join(_static_dir, "index.html"))

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str = ""):
        # Don't intercept API / docs routes
        if full_path.startswith(("api/", "docs", "openapi.json", "redoc")):
            from fastapi import HTTPException
            raise HTTPException(status_code=404)
        # Serve real file if it exists (JS, CSS, images)
        file_path = os.path.join(_static_dir, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        # SPA fallback — all unknown routes return index.html
        return FileResponse(os.path.join(_static_dir, "index.html"))
else:
    logger.warning("Frontend directory NOT found at: %s", _static_dir)


@app.get("/api/health")
def health():
    return {"status": "ok"}


# ── Pre-warm AI document classifier on startup (background thread) ────────────
# Loads the model configured in MODEL_NAME (env / .env) before the first scan,
# eliminating the cold-start delay on the very first request.
def _prewarm_classifier():
    try:
        import time
        time.sleep(2)   # Let FastAPI finish startup first
        from backend.config import CLASSIFIER_MODEL
        from backend.ai.document_classifier import classify_document
        # One dummy call — loads the model and JIT-warms the pipeline
        classify_document("warmup text for pre-warm", filename="prewarm")
        logger.info("[DocClassifier] Pre-warm complete — model ready: %s", CLASSIFIER_MODEL)
    except Exception as exc:
        logger.warning("[DocClassifier] Pre-warm error (non-fatal): %s", exc)

import threading as _threading
_threading.Thread(target=_prewarm_classifier, daemon=True, name="clf-prewarm").start()
