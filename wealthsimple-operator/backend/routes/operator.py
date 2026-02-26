from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from ai.provider import get_provider
from db import SessionLocal
from db_utils import run_with_retry
from models import RunSummary
from operator_engine import get_cached_run_summary, run_operator

router = APIRouter(prefix="/operator", tags=["operator"])
logger = logging.getLogger(__name__)


@router.post("/run", response_model=RunSummary)
def run_operator_endpoint(force: bool = False, max_age_seconds: int = 120) -> RunSummary:
    provider = get_provider()
    try:
        if not force:
            with SessionLocal() as db:
                cached = get_cached_run_summary(
                    db,
                    provider_name=provider.name,
                    max_age_seconds=max_age_seconds,
                )
                if cached is not None:
                    return cached

        def _run_once() -> RunSummary:
            with SessionLocal() as db:
                try:
                    return run_operator(db=db, provider=provider)
                except Exception:
                    db.rollback()
                    raise

        summary = run_with_retry(_run_once)
        return summary
    except Exception as exc:
        logger.exception("Operator run failed")
        # Return structured API error so frontend surfaces real backend failures.
        raise HTTPException(status_code=500, detail=f"Operator run failed: {exc}") from exc

