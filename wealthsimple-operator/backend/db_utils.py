"""Database utilities manager for SQLite concurrency and locking resilience.

Handles multi-process / multi-thread SQLite access (e.g., FastAPI + background_backfill)
by enabling WAL mode, increasing busy timeout, and retrying transient lock errors.
"""
from __future__ import annotations

import functools
import logging
import time
from typing import Callable, ParamSpec, TypeVar

P = ParamSpec("P")
T = TypeVar("T")

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)

# SQLite-specific error strings for transient lock failures
SQLITE_LOCK_ERRORS = (
    "database is locked",
    "database is busy",
    "cannot acquire lock",
    "timeout",
    "SQLITE_BUSY",
    "SQLITE_LOCKED",
)

# Default busy timeout in seconds (how long to wait for a lock before raising)
DEFAULT_BUSY_TIMEOUT_SECONDS = 30

# Retry configuration
DEFAULT_MAX_RETRIES = 5
DEFAULT_RETRY_DELAY_SECONDS = 0.5
DEFAULT_RETRY_BACKOFF = 1.5


def _is_sqlite_lock_error(exc: BaseException) -> bool:
    """Return True if the exception is a transient SQLite lock/busy error."""
    msg = str(exc).lower()
    return any(phrase in msg for phrase in SQLITE_LOCK_ERRORS)


def create_sqlite_engine(
    database_url: str,
    *,
    busy_timeout_seconds: float = DEFAULT_BUSY_TIMEOUT_SECONDS,
    check_same_thread: bool = False,
    pool_pre_ping: bool = True,
) -> Engine:
    """Create a SQLite engine configured for concurrent access.

    - Enables WAL (Write-Ahead Logging) for better read concurrency
    - Sets busy_timeout so connections wait for locks instead of failing immediately
    - Uses pool_pre_ping for connection health
    """
    engine = create_engine(
        database_url,
        connect_args={
            "check_same_thread": check_same_thread,
            "timeout": int(busy_timeout_seconds),
        },
        pool_pre_ping=pool_pre_ping,
        pool_size=5,
        max_overflow=10,
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=%d" % (int(busy_timeout_seconds * 1000),))
            cursor.execute("PRAGMA synchronous=NORMAL")
        finally:
            cursor.close()

    return engine


def with_retry(
    max_retries: int = DEFAULT_MAX_RETRIES,
    delay: float = DEFAULT_RETRY_DELAY_SECONDS,
    backoff: float = DEFAULT_RETRY_BACKOFF,
) -> Callable:
    """Decorator that retries on SQLite lock/busy errors."""

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            last_exc: BaseException | None = None
            current_delay = delay
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except OperationalError as e:
                    last_exc = e
                    if not _is_sqlite_lock_error(e) or attempt >= max_retries:
                        raise
                    logger.warning(
                        "SQLite lock error (attempt %d/%d), retrying in %.2fs: %s",
                        attempt + 1,
                        max_retries + 1,
                        current_delay,
                        e,
                    )
                    time.sleep(current_delay)
                    current_delay *= backoff
            raise last_exc  # type: ignore[misc]

        return wrapper

    return decorator


def run_with_retry(
    fn: Callable[[], T],
    max_retries: int = DEFAULT_MAX_RETRIES,
    delay: float = DEFAULT_RETRY_DELAY_SECONDS,
    backoff: float = DEFAULT_RETRY_BACKOFF,
) -> T:
    """Run a callable and retry on SQLite lock/busy errors.

    Use for blocks that use the database, e.g.:

        def do_cycle():
            with SessionLocal() as db:
                return run_operator(db=db, ...)
        run_with_retry(do_cycle)
    """
    last_exc: BaseException | None = None
    current_delay = delay
    for attempt in range(max_retries + 1):
        try:
            return fn()
        except OperationalError as e:
            last_exc = e
            if not _is_sqlite_lock_error(e) or attempt >= max_retries:
                raise
            logger.warning(
                "SQLite lock error (attempt %d/%d), retrying in %.2fs: %s",
                attempt + 1,
                max_retries + 1,
                current_delay,
                e,
            )
            time.sleep(current_delay)
            current_delay *= backoff
    raise last_exc  # type: ignore[misc]
