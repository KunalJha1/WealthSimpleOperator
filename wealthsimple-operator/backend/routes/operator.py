from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ai.provider import get_provider
from db import get_db
from models import RunSummary
from operator_engine import run_operator

router = APIRouter(prefix="/operator", tags=["operator"])
logger = logging.getLogger(__name__)


@router.post("/run", response_model=RunSummary)
def run_operator_endpoint(db: Session = Depends(get_db)) -> RunSummary:
    provider = get_provider()
    try:
        summary = run_operator(db=db, provider=provider)
        return summary
    except Exception as exc:
        logger.exception("Operator run failed")
        # Return structured API error so frontend surfaces real backend failures.
        raise HTTPException(status_code=500, detail=f"Operator run failed: {exc}") from exc

