from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from sqlalchemy.orm import sessionmaker, Session, declarative_base

from db_utils import create_sqlite_engine


DEFAULT_DB_PATH = Path(__file__).resolve().parent / "operator.db"
SQLALCHEMY_DATABASE_URL = os.getenv(
    "SQLALCHEMY_DATABASE_URL",
    f"sqlite:///{DEFAULT_DB_PATH.as_posix()}",
)

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

