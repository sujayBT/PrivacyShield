import os
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, declarative_base

# In packaged mode (Electron), Electron sets PRIVACY_DATA_DIR to AppData.
# In dev mode, use the repo root.
_data_dir = os.environ.get("PRIVACY_DATA_DIR", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_db_path   = os.path.join(_data_dir, "privacyshield_secure.db")

SQLALCHEMY_DATABASE_URL = f"sqlite:///{_db_path}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={
        "check_same_thread": False,
        "timeout": 30,          # Wait up to 30 s before raising OperationalError
    },
    pool_pre_ping=True,
)

# ── Enable WAL mode for concurrent access ─────────────────────────────────────
# WAL allows DB Browser for SQLite to read the file while the backend is writing.
@event.listens_for(engine, "connect")
def _set_sqlite_pragmas(dbapi_conn, _record):
    try:
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")    # allow concurrent readers
        cursor.execute("PRAGMA synchronous=NORMAL")  # faster writes, still safe
        cursor.execute("PRAGMA busy_timeout=30000")  # 30 s retry on lock (ms)
        cursor.execute("PRAGMA cache_size=-32000")   # 32 MB page cache
        cursor.close()
    except Exception:
        pass  # DB locked by external tool (e.g. DB Browser) — skip, retry later


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

