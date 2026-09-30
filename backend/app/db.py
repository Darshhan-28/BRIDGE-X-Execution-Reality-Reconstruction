"""SQLite engine + session helpers (P1 foundation).

Full table models arrive in Phase 2. This module only proves the
DB file can be created and connected on a CPU-only laptop.
"""
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import settings

connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(settings.DATABASE_URL, connect_args=connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_columns() -> None:
    """Lightweight additive migration for existing bridge_x.db files.

    create_all() never alters existing tables, so new nullable columns
    added in later phases are applied here with ALTER TABLE.
    """
    from sqlalchemy import text as _text

    with engine.begin() as conn:
        cols = {r[1] for r in conn.execute(_text("PRAGMA table_info(field_reports)")).all()}
        if "meta" not in cols:
            conn.execute(_text("ALTER TABLE field_reports ADD COLUMN meta TEXT DEFAULT '{}'"))
        # P14: learned-vocabulary lifecycle + persisted boost audit trail.
        vcols = {r[1] for r in conn.execute(_text("PRAGMA table_info(project_vocabulary)")).all()}
        if "is_active" not in vcols:
            conn.execute(_text("ALTER TABLE project_vocabulary ADD COLUMN is_active INTEGER DEFAULT 1"))
            conn.execute(_text("UPDATE project_vocabulary SET is_active = 1 WHERE is_active IS NULL"))
        mcols = {r[1] for r in conn.execute(_text("PRAGMA table_info(match_candidates)")).all()}
        if "base_score" not in mcols:
            conn.execute(_text("ALTER TABLE match_candidates ADD COLUMN base_score FLOAT DEFAULT 0.0"))
        if "vocab_bonus" not in mcols:
            conn.execute(_text("ALTER TABLE match_candidates ADD COLUMN vocab_bonus FLOAT DEFAULT 0.0"))
        if "vocab_hits_json" not in mcols:
            conn.execute(_text("ALTER TABLE match_candidates ADD COLUMN vocab_hits_json TEXT DEFAULT '[]'"))
        # REAL-DATA phase: source-type labeling for honest provenance.
        fcols = {r[1] for r in conn.execute(_text("PRAGMA table_info(field_reports)")).all()}
        if "source_type" not in fcols:
            conn.execute(_text("ALTER TABLE field_reports ADD COLUMN source_type TEXT DEFAULT 'SYNTHETIC'"))


def check_db() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
