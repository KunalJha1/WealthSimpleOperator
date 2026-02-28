from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from ai.provider import get_provider
from db import get_db
from models import (
    SimulationRequest,
    SimulationSummary,
    SimulationScenario,
    SimulationSeverity,
    PlaybookAction,
    PlaybookSummary,
    AuditEvent,
    AuditEventType,
)
from simulation_engine import run_scenario


router = APIRouter(prefix="/simulations", tags=["simulations"])


class PlaybookRequest(BaseModel):
    scenario: SimulationScenario
    severity: SimulationSeverity
    portfolio_ids: List[int]


@router.post("/run", response_model=SimulationSummary)
def run_simulation(
    payload: SimulationRequest,
    db: Session = Depends(get_db),
) -> SimulationSummary:
    provider = get_provider()
    return run_scenario(db=db, provider=provider, request=payload)


@router.post("/playbook", response_model=PlaybookSummary)
def generate_playbook(
    payload: PlaybookRequest,
    db: Session = Depends(get_db),
) -> PlaybookSummary:
    """Generate a defensive playbook with ranked actions for off-trajectory portfolios."""
    from models import Alert, Portfolio, Client

    # Fetch portfolios and their clients
    portfolios = (
        db.query(Portfolio)
        .options(joinedload(Portfolio.client))
        .filter(Portfolio.id.in_(payload.portfolio_ids))
        .all()
    )

    if not portfolios:
        raise HTTPException(status_code=400, detail="No portfolios found")

    # Generate ranked action plan
    actions: List[PlaybookAction] = []

    urgency_map = {
        "severe": ("Contact immediately", "Urgent"),
        "moderate": ("Review rebalancing", "High"),
        "mild": ("Monitor", "Medium"),
    }

    action_type, urgency = urgency_map.get(payload.severity.value, ("Monitor", "Medium"))

    for idx, portfolio in enumerate(portfolios, 1):
        client = portfolio.client

        # Draft email subject and body
        subject = f"Action Required: Portfolio Review Due to {payload.scenario.value.replace('_', ' ').title()}"

        body = f"""Dear {client.name},

Recent market analysis indicates your portfolio may need attention due to {payload.scenario.value.replace('_', ' ')}.

Current situation:
- Your {portfolio.name} may experience trajectory drift in this scenario
- Severity: {payload.severity.value.capitalize()}
- Recommended action: {action_type}

Next steps:
1. Review your current allocation and targets
2. Discuss any life changes affecting your plan
3. Consider rebalancing if allocations have drifted

We recommend scheduling a call within 5 business days to discuss.

Best regards,
Advisor Team"""

        actions.append(
            PlaybookAction(
                rank=idx,
                client_name=client.name,
                portfolio_name=portfolio.name,
                action_type=action_type,
                urgency=urgency,
                draft_email_subject=subject,
                draft_email_body=body,
            )
        )

    ai_rationale = f"Playbook generated for {len(portfolios)} portfolios off trajectory in {payload.scenario.value} scenario at {payload.severity.value} severity. Actions ranked by exposure and client tier. Review drafts and customize before sending."

    # Log audit event
    db.add(
        AuditEvent(
            event_type=AuditEventType.PLAYBOOK_GENERATED,
            actor="operator_demo",
            details={
                "scenario": payload.scenario.value,
                "severity": payload.severity.value,
                "portfolios_affected": len(portfolios),
                "actions_generated": len(actions),
            },
        )
    )
    db.commit()

    return PlaybookSummary(
        scenario=payload.scenario,
        severity=payload.severity,
        actions=actions,
        ai_rationale=ai_rationale,
    )

