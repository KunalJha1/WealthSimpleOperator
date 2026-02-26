from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ai.provider import get_provider
from db import get_db
from models import SimulationRequest, SimulationSummary
from simulation_engine import run_scenario


router = APIRouter(prefix="/simulations", tags=["simulations"])


@router.post("/run", response_model=SimulationSummary)
def run_simulation(
    payload: SimulationRequest,
    db: Session = Depends(get_db),
) -> SimulationSummary:
    provider = get_provider()
    return run_scenario(db=db, provider=provider, request=payload)

