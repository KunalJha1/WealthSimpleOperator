from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from db import get_db
from models import MonitoringUniverseDetail, MonitoringUniverseSummary
from operator_engine import (
    compute_monitoring_universe_detail,
    compute_monitoring_universe_summary,
)

router = APIRouter(prefix="/portfolios", tags=["portfolios"])


@router.get("/summary", response_model=MonitoringUniverseSummary)
def get_portfolios_summary(db: Session = Depends(get_db)) -> MonitoringUniverseSummary:
    return compute_monitoring_universe_summary(db)


@router.get("/monitoring-detail", response_model=MonitoringUniverseDetail)
def get_monitoring_detail(db: Session = Depends(get_db)) -> MonitoringUniverseDetail:
    return compute_monitoring_universe_detail(db)

