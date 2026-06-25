# backend_bundle.spec  — PyInstaller spec for Privacy Shield backend
# Run: pyinstaller backend_bundle.spec

import os
import sys
from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules

block_cipher = None

# ── Collect all submodules (catches dynamic imports PyInstaller misses) ────────
fastapi_datas,    fastapi_binaries,    fastapi_hidden    = collect_all('fastapi')
starlette_datas,  starlette_binaries,  starlette_hidden  = collect_all('starlette')
spacy_datas,      spacy_binaries,      spacy_hidden      = collect_all('spacy')
thinc_datas,      thinc_binaries,      thinc_hidden      = collect_all('thinc')
srsly_datas,      srsly_binaries,      srsly_hidden      = collect_all('srsly')
pydantic_hidden                                          = collect_submodules('pydantic')
uvicorn_hidden                                           = collect_submodules('uvicorn')
sqlalchemy_hidden                                        = collect_submodules('sqlalchemy')
anyio_hidden                                             = collect_submodules('anyio')
multipart_hidden                                         = collect_submodules('multipart')
watchdog_hidden                                          = collect_submodules('watchdog')
try:
    torch_datas, torch_binaries, torch_hidden = collect_all('torch')
except Exception:
    torch_datas, torch_binaries, torch_hidden = [], [], []
try:
    transformers_datas, transformers_binaries, transformers_hidden = collect_all('transformers')
except Exception:
    transformers_datas, transformers_binaries, transformers_hidden = [], [], []
try:
    spacy_model_datas, spacy_model_binaries, spacy_model_hidden = collect_all('en_core_web_sm')
except Exception:
    spacy_model_datas, spacy_model_binaries, spacy_model_hidden = [], [], []

# ── Analysis ──────────────────────────────────────────────────────────────────
a = Analysis(
    ['backend_entry.py'],
    pathex=['.'],
    binaries=(
        spacy_binaries + thinc_binaries + srsly_binaries +
        fastapi_binaries + starlette_binaries +
        torch_binaries + transformers_binaries +
        spacy_model_binaries
    ),
    datas=[
        ('backend',       'backend'),    # whole backend package
        ('version.json',  '.'),          # version info
        # cv2 haarcascade XML data files (face detection)
        (r'tf_env\Lib\site-packages\cv2\data', r'cv2\data'),
    ] + spacy_datas + thinc_datas + srsly_datas + fastapi_datas + starlette_datas
      + torch_datas + transformers_datas + spacy_model_datas,
    hiddenimports=[
        # ── FastAPI + Starlette (ALL submodules) ──────────────────────────────
        'fastapi',
        'fastapi.staticfiles',
        'fastapi.responses',
        'fastapi.middleware',
        'fastapi.middleware.cors',
        'fastapi.middleware.gzip',
        'fastapi.security',
        'fastapi.security.oauth2',
        'fastapi.encoders',
        'fastapi.exceptions',
        'fastapi.routing',
        'fastapi.openapi',
        'fastapi.openapi.utils',
        'fastapi.openapi.docs',
        'fastapi.background',
        'fastapi.concurrency',
        'fastapi.dependencies',
        'fastapi.dependencies.utils',
        'fastapi.params',
        'fastapi.datastructures',
        'fastapi.templating',
        'starlette',
        'starlette.staticfiles',
        'starlette.responses',
        'starlette.requests',
        'starlette.routing',
        'starlette.middleware',
        'starlette.middleware.cors',
        'starlette.middleware.gzip',
        'starlette.middleware.base',
        'starlette.background',
        'starlette.concurrency',
        'starlette.datastructures',
        'starlette.exceptions',
        'starlette.formparsers',
        'starlette.types',
        'starlette.websockets',
        'starlette.testclient',
        'starlette.templating',
        'starlette.convertors',
        # ── Backend modules ───────────────────────────────────────────────────
        'backend',
        'backend.database',
        'backend.models',
        'backend.schemas',
        'backend.auth',
        'backend.main',
        'backend.routers',
        'backend.routers.auth_router',
        'backend.routers.scan_router',
        'backend.routers.url_scan_router',
        'backend.routers.cloud_router',
        'backend.routers.monitor_router',
        'backend.routers.social_router',
        'backend.routers.metadata_router',
        'backend.routers.attack_router',
        'backend.routers.history_router',
        'backend.routers.batch_scan_router',
        'backend.routers.agent_router',
        'backend.services',
        'backend.services.ai_detection',
        'backend.services.attack_simulation',
        'backend.services.background_agent',
        'backend.services.blurring',
        'backend.services.cloud_fetcher',
        'backend.services.detection',
        'backend.services.metadata_extractor',
        'backend.services.recommendations',
        'backend.services.remediation',
        'backend.services.report',
        'backend.services.screenshot_monitor',
        'backend.services.social_scraper',
        'backend.services.vision_detection',
        'backend.services.notify',
        'backend.services.bart_classifier',
        'backend.ai',
        'backend.ai.document_classifier',
        # ── uvicorn ───────────────────────────────────────────────────────────
        'uvicorn',
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.loops.asyncio',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.http.h11_impl',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        'uvicorn.middleware',
        'uvicorn.middleware.proxy_headers',
        'uvicorn._compat',
        'uvicorn.config',
        'uvicorn.importer',
        'uvicorn.main',
        'uvicorn.server',
        # ── SQLAlchemy ────────────────────────────────────────────────────────
        'sqlalchemy',
        'sqlalchemy.dialects.sqlite',
        'sqlalchemy.dialects.sqlite.pysqlite',
        'sqlalchemy.pool',
        'sqlalchemy.event',
        'sqlalchemy.orm',
        'sqlalchemy.orm.session',
        'sqlalchemy.ext.declarative',
        # ── Auth / Security ───────────────────────────────────────────────────
        'passlib',
        'passlib.handlers',
        'passlib.handlers.bcrypt',
        'bcrypt',
        'jose',
        'jose.jwt',
        'jose.exceptions',
        'jose.constants',
        'jose.backends',
        'cryptography',
        'cryptography.hazmat',
        'cryptography.hazmat.primitives',
        'cryptography.hazmat.primitives.hashes',
        # ── anyio ─────────────────────────────────────────────────────────────
        'anyio',
        'anyio.abc',
        'anyio._backends._asyncio',
        'anyio._core._fileio',
        'sniffio',
        # ── Image / OCR ───────────────────────────────────────────────────────
        'PIL',
        'PIL.Image',
        'PIL.ExifTags',
        'PIL.TiffImagePlugin',
        'PIL.PngImagePlugin',
        'PIL.JpegImagePlugin',
        'piexif',
        'piexif.helper',
        'pytesseract',
        # ── PDF ───────────────────────────────────────────────────────────────
        'fitz',
        'pdfplumber',
        'reportlab',
        'reportlab.pdfgen',
        'reportlab.pdfgen.canvas',
        'reportlab.platypus',
        'reportlab.lib',
        'reportlab.lib.pagesizes',
        'reportlab.lib.styles',
        'reportlab.lib.units',
        # ── Office documents ──────────────────────────────────────────────────
        'docx',
        'docx.oxml',
        'openpyxl',
        'openpyxl.styles',
        # ── Web / scraping ────────────────────────────────────────────────────
        'bs4',
        'bs4.builder',
        'bs4.builder._lxml',
        'bs4.builder._html5lib',
        'requests',
        'requests.adapters',
        'requests.auth',
        'aiohttp',
        'aiofiles',
        'httpx',
        # ── multipart ─────────────────────────────────────────────────────────
        'multipart',
        'python_multipart',
        'email_validator',
        'email_validator.syntax_validator',
        'email_validator.deliverability',
        # ── misc ──────────────────────────────────────────────────────────────
        'pydantic',
        'pydantic.v1',
        'pydantic_settings',
        'pydantic_core',
        'h11',
        'h11._readers',
        'h11._writers',
        'h11._connection',
        'exifread',
        'cv2',
        'zipfile',
        'logging',
        'logging.handlers',
        'json',
        'io',
        'struct',
        'pathlib',
        'typing_extensions',
        'annotated_types',
        # ── Notifications ────────────────────────────────────────────────────
        'plyer',
        'plyer.platforms',
        'plyer.platforms.win',
        'plyer.platforms.win.notification',
        'plyer.utils',
        'win10toast',
        # ── File watcher ─────────────────────────────────────────────────────
        'watchdog',
        'watchdog.observers',
        'watchdog.observers.polling',
        'watchdog.events',
        # ── System / utils ────────────────────────────────────────────────────
        'cffi',
        'click',
        'psutil',
        # ── ML / transformers (BART classifier) ───────────────────────────────
        'torch',
        'torch.nn',
        'transformers',
        'transformers.pipelines',
        'transformers.models',
        'transformers.models.bart',
        'transformers.tokenization_utils',
        'transformers.tokenization_utils_fast',
        'tokenizers',
        'safetensors',
    ] + (fastapi_hidden + starlette_hidden + spacy_hidden +
         thinc_hidden + srsly_hidden + pydantic_hidden +
         uvicorn_hidden + sqlalchemy_hidden + anyio_hidden +
         multipart_hidden + watchdog_hidden + torch_hidden + transformers_hidden +
         spacy_model_hidden),

    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'notebook',
        'jupyter',
        'PyQt5',
        'PyQt6',
        'wx',
        'tkinter',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,           # keep True so error output is visible
    icon='electron\\assets\\icon.ico',  # logo_v7_final.png generated icon
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='backend',
)
