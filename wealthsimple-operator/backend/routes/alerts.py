from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Sequence

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import case
from sqlalchemy.orm import Session, joinedload

from ai.provider import get_provider
from db import get_db
from generate_client_insights import _allocation_breakdown, _build_profile_view
from models import (
    Alert,
    AlertDetail,
    AlertStatus,
    AlertSummary,
    AuditEvent,
    AuditEventType,
    ClientSummary,
    FollowUpDraft,
    FollowUpDraftStatus,
    FollowUpDraftView,
    Portfolio,
    PortfolioSummary,
    Priority,
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


class FollowUpDraftCreateRequest(BaseModel):
    force_regenerate: bool = False


class FollowUpDraftResponse(BaseModel):
    draft: FollowUpDraftView
    message: str


class FollowUpDraftRejectRequest(BaseModel):
    reason: Optional[str] = None


def _draft_to_view(draft: FollowUpDraft) -> FollowUpDraftView:
    return FollowUpDraftView(
        id=draft.id,
        alert_id=draft.alert_id,
        client_id=draft.client_id,
        status=draft.status,
        recipient_email=draft.recipient_email,
        subject=draft.subject,
        body=draft.body,
        generation_provider=draft.generation_provider,
        generated_from=draft.generated_from or {},
        approved_by=draft.approved_by,
        approved_at=draft.approved_at,
        created_at=draft.created_at,
        updated_at=draft.updated_at,
    )


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
        priority_enums = [Priority(v) for v in raw_values if v in Priority.__members__]
        if priority_enums:
            query = query.filter(Alert.priority.in_(priority_enums))

    if status:
        raw_status = {s.strip().upper() for s in status.split(",") if s.strip()}
        status_enums = [AlertStatus(v) for v in raw_status if v in AlertStatus.__members__]
        if status_enums:
            query = query.filter(Alert.status.in_(status_enums))

    total = query.count()

    priority_rank = case(
        (Alert.priority == Priority.HIGH, 0),
        (Alert.priority == Priority.MEDIUM, 1),
        (Alert.priority == Priority.LOW, 2),
        else_=99,
    )

    alerts: Sequence[Alert] = (
        query.order_by(priority_rank.asc(), Alert.created_at.desc(), Alert.confidence.desc())
        .offset(offset)
        .limit(limit)
        .all()
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
                summary=a.summary,
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
            joinedload(Alert.portfolio).joinedload(Portfolio.positions),
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
    allocation = _allocation_breakdown(portfolio)
    metrics = {
        "concentration_score": float(alert.concentration_score),
        "drift_score": float(alert.drift_score),
        "volatility_proxy": float(alert.volatility_proxy),
        "risk_score": float(alert.risk_score),
    }
    client_profile_view = _build_profile_view(
        client=client,
        portfolio=portfolio,
        metrics=metrics,
        allocation=allocation,
        generated_at=alert.created_at,
        db=db,
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
        client_profile_view=client_profile_view,
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


@router.post("/{alert_id}/follow-up-draft", response_model=FollowUpDraftResponse)
def create_follow_up_draft(
    alert_id: int,
    payload: FollowUpDraftCreateRequest,
    db: Session = Depends(get_db),
) -> FollowUpDraftResponse:
    alert: Alert | None = (
        db.query(Alert)
        .options(joinedload(Alert.client), joinedload(Alert.portfolio))
        .filter(Alert.id == alert_id)
        .first()
    )
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    existing_pending: FollowUpDraft | None = (
        db.query(FollowUpDraft)
        .filter(
            FollowUpDraft.alert_id == alert.id,
            FollowUpDraft.status == FollowUpDraftStatus.PENDING_APPROVAL,
        )
        .order_by(FollowUpDraft.created_at.desc())
        .first()
    )
    if existing_pending and not payload.force_regenerate:
        return FollowUpDraftResponse(
            draft=_draft_to_view(existing_pending),
            message="Existing pending follow-up draft returned.",
        )

    provider = get_provider()
    advisor_name = "Advisor Team"
    alert_context: Dict[str, Any] = {
        "client_name": alert.client.name,
        "client_email": alert.client.email,
        "event_title": alert.event_title,
        "summary": alert.summary,
        "priority": alert.priority.value,
        "suggested_next_step": alert.suggested_next_step,
        "advisor_name": advisor_name,
        "risk_profile": alert.client.risk_profile,
    }

    content = provider.generate_follow_up_draft(alert_context=alert_context)

    draft = FollowUpDraft(
        alert_id=alert.id,
        client_id=alert.client_id,
        status=FollowUpDraftStatus.PENDING_APPROVAL,
        recipient_email=alert.client.email,
        subject=content.subject,
        body=content.body,
        generation_provider=provider.name,
        generated_from={
            "alert_id": alert.id,
            "priority": alert.priority.value,
            "risk_score": float(alert.risk_score),
            "generated_at": datetime.utcnow().isoformat(),
        },
    )
    db.add(draft)
    db.flush()

    db.add(
        AuditEvent(
            alert_id=alert.id,
            run_id=alert.run_id,
            event_type=AuditEventType.FOLLOW_UP_DRAFT_CREATED,
            actor="operator_demo",
            details={
                "draft_id": draft.id,
                "status": draft.status.value,
                "recipient_email": draft.recipient_email,
                "provider": draft.generation_provider,
            },
        )
    )
    db.commit()
    db.refresh(draft)

    return FollowUpDraftResponse(
        draft=_draft_to_view(draft),
        message="Follow-up draft generated and queued for approval.",
    )


@router.get("/{alert_id}/follow-up-draft", response_model=FollowUpDraftResponse)
def get_follow_up_draft(
    alert_id: int,
    db: Session = Depends(get_db),
) -> FollowUpDraftResponse:
    alert: Alert | None = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    draft: FollowUpDraft | None = (
        db.query(FollowUpDraft)
        .filter(FollowUpDraft.alert_id == alert_id)
        .order_by(
            case(
                (FollowUpDraft.status == FollowUpDraftStatus.PENDING_APPROVAL, 0),
                (FollowUpDraft.status == FollowUpDraftStatus.APPROVED_READY, 1),
                else_=2,
            ),
            FollowUpDraft.created_at.desc(),
        )
        .first()
    )
    if not draft:
        raise HTTPException(status_code=404, detail="No follow-up draft found for this alert")

    return FollowUpDraftResponse(
        draft=_draft_to_view(draft),
        message="Follow-up draft retrieved.",
    )


@router.post("/follow-up-drafts/{draft_id}/approve", response_model=FollowUpDraftResponse)
def approve_follow_up_draft(
    draft_id: int,
    db: Session = Depends(get_db),
) -> FollowUpDraftResponse:
    draft: FollowUpDraft | None = (
        db.query(FollowUpDraft)
        .options(joinedload(FollowUpDraft.alert))
        .filter(FollowUpDraft.id == draft_id)
        .first()
    )
    if not draft:
        raise HTTPException(status_code=404, detail="Follow-up draft not found")
    if draft.status != FollowUpDraftStatus.PENDING_APPROVAL:
        raise HTTPException(status_code=409, detail="Only pending drafts can be approved")

    draft.status = FollowUpDraftStatus.APPROVED_READY
    draft.approved_by = "operator_demo"
    draft.approved_at = datetime.utcnow()

    db.add(
        AuditEvent(
            alert_id=draft.alert_id,
            run_id=draft.alert.run_id if draft.alert else None,
            event_type=AuditEventType.FOLLOW_UP_DRAFT_APPROVED,
            actor="operator_demo",
            details={"draft_id": draft.id, "status": draft.status.value},
        )
    )
    db.commit()
    db.refresh(draft)

    return FollowUpDraftResponse(
        draft=_draft_to_view(draft),
        message="Follow-up draft approved and marked ready.",
    )


@router.post("/follow-up-drafts/{draft_id}/reject", response_model=FollowUpDraftResponse)
def reject_follow_up_draft(
    draft_id: int,
    payload: FollowUpDraftRejectRequest,
    db: Session = Depends(get_db),
) -> FollowUpDraftResponse:
    draft: FollowUpDraft | None = (
        db.query(FollowUpDraft)
        .options(joinedload(FollowUpDraft.alert))
        .filter(FollowUpDraft.id == draft_id)
        .first()
    )
    if not draft:
        raise HTTPException(status_code=404, detail="Follow-up draft not found")
    if draft.status != FollowUpDraftStatus.PENDING_APPROVAL:
        raise HTTPException(status_code=409, detail="Only pending drafts can be rejected")

    draft.status = FollowUpDraftStatus.REJECTED

    db.add(
        AuditEvent(
            alert_id=draft.alert_id,
            run_id=draft.alert.run_id if draft.alert else None,
            event_type=AuditEventType.FOLLOW_UP_DRAFT_REJECTED,
            actor="operator_demo",
            details={
                "draft_id": draft.id,
                "status": draft.status.value,
                "reason": (payload.reason or "").strip(),
            },
        )
    )
    db.commit()
    db.refresh(draft)

    return FollowUpDraftResponse(
        draft=_draft_to_view(draft),
        message="Follow-up draft rejected.",
    )

