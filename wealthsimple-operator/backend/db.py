from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Generator
from urllib.parse import unquote

from sqlalchemy.orm import sessionmaker, Session, declarative_base

from db_utils import create_sqlite_engine


DEFAULT_DB_PATH = Path(__file__).resolve().parent / "operator.db"


def _resolve_database_url() -> str:
    configured_url = os.getenv("SQLALCHEMY_DATABASE_URL")
    if not configured_url:
        return f"sqlite:///{DEFAULT_DB_PATH.as_posix()}"

    if not configured_url.startswith("sqlite:///"):
        return configured_url

    sqlite_path = unquote(configured_url.replace("sqlite:///", "", 1))
    db_path = Path(sqlite_path)

    if db_path.is_absolute():
        return configured_url

    canonical_path = (Path(__file__).resolve().parent / db_path).resolve()
    return f"sqlite:///{canonical_path.as_posix()}"


SQLALCHEMY_DATABASE_URL = _resolve_database_url()

engine = create_sqlite_engine(
    SQLALCHEMY_DATABASE_URL,
    busy_timeout_seconds=30,
    check_same_thread=False,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """Provide a transactional scope around a series of operations."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

