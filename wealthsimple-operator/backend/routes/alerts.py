from __future__ import annotations

from typing import List, Literal, Optional, Sequence

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from db import get_db
from models import (
    Alert,
    AlertDetail,
    AlertStatus,
    AlertSummary,
    AuditEvent,
    AuditEventType,
    ClientSummary,
    PortfolioSummary,
)

router = APIRouter(prefix="/alerts", tags=["alerts"])


class AlertsListResponse(BaseModel):
    items: List[AlertSummary]
    total: int


class AlertActionRequest(BaseModel):
    action: Literal["reviewed", "escalate", "false_positive"]


class AlertActionResponse(BaseModel):
    alert: AlertDetail
    message: str


@router.get("", response_model=AlertsListResponse)
def list_alerts(
    db: Session = Depends(get_db),
    priority: Optional[str] = Query(
        None,
        description="Optional priority filter, e.g. 'HIGH' or 'HIGH,MEDIUM'.",
    ),
    status: Optional[str] = Query(
        None,
        description="Optional status filter, e.g. 'OPEN' or 'OPEN,ESCALATED'.",
    ),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> AlertsListResponse:
    query = db.query(Alert).options(
        joinedload(Alert.client),
        joinedload(Alert.portfolio),
    )

    if priority:
        raw_values = {p.strip().upper() for p in priority.split(",") if p.strip()}
        priorities = [AlertStatus(v) for v in []]  # type: ignore[call-arg]
        # map to Priority enum via values on Alert.priority
        from ..models import Priority as PriorityEnum

        priority_enums = [PriorityEnum(v) for v in raw_values if v in PriorityEnum.__members__]
        if priority_enums:
            query = query.filter(Alert.priority.in_(priority_enums))

    if status:
        raw_status = {s.strip().upper() for s in status.split(",") if s.strip()}
        status_enums = [AlertStatus(v) for v in raw_status if v in AlertStatus.__members__]
        if status_enums:
            query = query.filter(Alert.status.in_(status_enums))

    total = query.count()

    alerts: Sequence[Alert] = (
        query.order_by(Alert.created_at.desc()).offset(offset).limit(limit).all()
    )

    items: List[AlertSummary] = []
    for a in alerts:
        client = a.client
        portfolio = a.portfolio
        client_summary = ClientSummary(
            id=client.id,
            name=client.name,
            email=client.email,
            segment=client.segment,
            risk_profile=client.risk_profile,
        )
        portfolio_summary = PortfolioSummary(
            id=portfolio.id,
            name=portfolio.name,
            total_value=float(portfolio.total_value),
            target_equity_pct=float(portfolio.target_equity_pct),
            target_fixed_income_pct=float(portfolio.target_fixed_income_pct),
            target_cash_pct=float(portfolio.target_cash_pct),
        )
        items.append(
            AlertSummary(
                id=a.id,
                created_at=a.created_at,
                priority=a.priority,
                confidence=a.confidence,
                event_title=a.event_title,
                status=a.status,
                client=client_summary,
                portfolio=portfolio_summary,
            )
        )

    return AlertsListResponse(items=items, total=total)


@router.get("/{alert_id}", response_model=AlertDetail)
def get_alert(alert_id: int, db: Session = Depends(get_db)) -> AlertDetail:
    alert: Alert | None = (
        db.query(Alert)
        .options(
            joinedload(Alert.client),
            joinedload(Alert.portfolio),
        )
        .filter(Alert.id == alert_id)
        .first()
    )
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    client = alert.client
    portfolio = alert.portfolio
    client_summary = ClientSummary(
        id=client.id,
        name=client.name,
        email=client.email,
        segment=client.segment,
        risk_profile=client.risk_profile,
    )
    portfolio_summary = PortfolioSummary(
        id=portfolio.id,
        name=portfolio.name,
        total_value=float(portfolio.total_value),
        target_equity_pct=float(portfolio.target_equity_pct),
        target_fixed_income_pct=float(portfolio.target_fixed_income_pct),
        target_cash_pct=float(portfolio.target_cash_pct),
    )

    return AlertDetail(
        id=alert.id,
        created_at=alert.created_at,
        priority=alert.priority,
        confidence=alert.confidence,
        event_title=alert.event_title,
        summary=alert.summary,
        reasoning_bullets=alert.reasoning_bullets,
        human_review_required=alert.human_review_required,
        suggested_next_step=alert.suggested_next_step,
        decision_trace_steps=[{"step": s["step"], "detail": s["detail"]} for s in alert.decision_trace_steps],
        change_detection=[
            {
                "metric": c.get("metric", ""),
                "from": c.get("from", ""),
                "to": c.get("to", ""),
            }
            for c in alert.change_detection
        ],
        status=alert.status,
        concentration_score=alert.concentration_score,
        drift_score=alert.drift_score,
        volatility_proxy=alert.volatility_proxy,
        risk_score=alert.risk_score,
        client=client_summary,
        portfolio=portfolio_summary,
    )


@router.post("/{alert_id}/action", response_model=AlertActionResponse)
def act_on_alert(
    alert_id: int,
    payload: AlertActionRequest,
    db: Session = Depends(get_db),
) -> AlertActionResponse:
    alert: Alert | None = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    if payload.action == "reviewed":
        new_status = AlertStatus.REVIEWED
        event_type = AuditEventType.ALERT_REVIEWED
        message = "Alert marked as reviewed."
    elif payload.action == "escalate":
        new_status = AlertStatus.ESCALATED
        event_type = AuditEventType.ALERT_ESCALATED
        message = "Alert escalated for further attention."
    else:
        new_status = AlertStatus.FALSE_POSITIVE
        event_type = AuditEventType.ALERT_FALSE_POSITIVE
        message = "Alert marked as false positive."

    alert.status = new_status
    db.add(
        AuditEvent(
            alert_id=alert.id,
            run_id=alert.run_id,
            event_type=event_type,
            actor="operator_demo",
            details={"new_status": new_status.value},
        )
    )
    db.commit()
    db.refresh(alert)

    # Reuse get_alert logic to build the detailed view
    detail = get_alert(alert_id=alert.id, db=db)
    return AlertActionResponse(alert=detail, message=message)

