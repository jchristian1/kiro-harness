from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator

from kiro_worker.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
)


@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Enable foreign key enforcement and WAL mode on every SQLite connection.
    WAL mode allows concurrent readers and writers — essential for progress
    updates written during a long run to be visible to concurrent GET requests.
    """
    if "sqlite" in settings.DATABASE_URL:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.execute("PRAGMA journal_mode = WAL")
        cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables() -> None:
    """Create all tables if they don't exist (bootstrap for Phase 1)."""
    from kiro_worker.db.models import Base
    Base.metadata.create_all(bind=engine)
    # Ensure meta table has schema_version
    with engine.connect() as conn:
        conn.execute(text("INSERT OR IGNORE INTO meta (key, value) VALUES ('schema_version', '1')"))
        conn.commit()
