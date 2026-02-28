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
    RebalancingSuggestion,
    RebalancingLineItem,
    ReallocationAlternative,
    ReallocationPlan,
    ReallocationPlanStatus,
    ReallocationPlanView,
    ReallocationTrade,
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


class ReallocationPlanRequest(BaseModel):
    target_cash_amount: float = 266000.0


def _estimate_unit_price(ticker: str, asset_class: str) -> float:
    seed = (sum(ord(c) for c in ticker) % 35) + 40
    if asset_class == "Equity":
        return float(seed + 60)
    if asset_class == "Fixed Income":
        return float(seed // 2 + 85)
    return 1.0


def _estimate_gain_rate(ticker: str, asset_class: str) -> float:
    seed = (sum(ord(c) for c in ticker) % 9) / 100.0
    if asset_class == "Equity":
        return 0.14 + seed
    if asset_class == "Fixed Income":
        return 0.04 + seed / 2
    return 0.0


def _volatility_weight(asset_class: str) -> float:
    if asset_class == "Equity":
        return 0.16
    if asset_class == "Fixed Income":
        return 0.07
    return 0.01


def _plan_to_view(plan: ReallocationPlan) -> ReallocationPlanView:
    return ReallocationPlanView(
        plan_id=plan.id,
        alert_id=plan.alert_id,
        status=plan.status,
        generated_at=plan.created_at,
        target_cash_amount=float(plan.target_cash_amount),
        current_cash_amount=float(plan.current_cash_amount),
        additional_cash_needed=float(plan.additional_cash_needed),
        estimated_realized_gains=float(plan.estimated_realized_gains),
        estimated_tax_impact=float(plan.estimated_tax_impact),
        volatility_before=float(plan.volatility_before),
        volatility_after=float(plan.volatility_after),
        volatility_reduction_pct=float(plan.volatility_reduction_pct),
        liquidity_days=int(plan.liquidity_days),
        ai_rationale=plan.ai_rationale,
        assumptions=plan.assumptions or {},
        trades=[ReallocationTrade(**trade) for trade in (plan.trades or [])],
        alternatives_considered=[
            ReallocationAlternative(**item)
            for item in (plan.alternatives_considered or [])
        ],
        requires_human_approval=True,
        simulated_execution=True,
        queued_at=plan.queued_at,
        approved_at=plan.approved_at,
        approved_by=plan.approved_by,
        executed_at=plan.executed_at,
        execution_reference=plan.execution_reference,
    )


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
        raise HTTPException(
            status_code=404,
            detail=f"Alert {alert_id} not found. It may have been archived or removed; select an active alert and retry.",
        )

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


@router.post("/{alert_id}/rebalance-suggestion", response_model=RebalancingSuggestion)
def generate_rebalance_suggestion(
    alert_id: int,
    db: Session = Depends(get_db),
) -> RebalancingSuggestion:
    alert: Alert | None = (
        db.query(Alert)
        .options(
            joinedload(Alert.portfolio).joinedload(Portfolio.positions),
            joinedload(Alert.client),
        )
        .filter(Alert.id == alert_id)
        .first()
    )
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    portfolio = alert.portfolio
    positions = portfolio.positions

    # Calculate current allocation by asset class
    total_value = float(portfolio.total_value)
    current_equity = sum(p.value for p in positions if p.asset_class == "Equity")
    current_fixed_income = sum(p.value for p in positions if p.asset_class == "Fixed Income")
    current_cash = sum(p.value for p in positions if p.asset_class == "Cash")

    current_equity_pct = (current_equity / total_value * 100) if total_value else 0
    current_fixed_income_pct = (current_fixed_income / total_value * 100) if total_value else 0
    current_cash_pct = (current_cash / total_value * 100) if total_value else 0

    # Target allocation from portfolio
    target_equity_pct = float(portfolio.target_equity_pct)
    target_fixed_income_pct = float(portfolio.target_fixed_income_pct)
    target_cash_pct = float(portfolio.target_cash_pct)

    # Generate line items for each position
    line_items: List[RebalancingLineItem] = []
    for pos in positions:
        current_weight = (float(pos.value) / total_value * 100) if total_value else 0

        # Suggested weight: simple approach - rebalance toward target by asset class
        if pos.asset_class == "Equity":
            suggested_weight = (target_equity_pct / max(1, len([p for p in positions if p.asset_class == "Equity"])))
        elif pos.asset_class == "Fixed Income":
            suggested_weight = (target_fixed_income_pct / max(1, len([p for p in positions if p.asset_class == "Fixed Income"])))
        else:  # Cash
            suggested_weight = (target_cash_pct / max(1, len([p for p in positions if p.asset_class == "Cash"])))

        delta = suggested_weight - current_weight
        if delta > 0.5:
            action = "Increase"
        elif delta < -0.5:
            action = "Reduce"
        else:
            action = "Hold"

        line_items.append(
            RebalancingLineItem(
                ticker=pos.ticker,
                asset_class=pos.asset_class,
                current_weight=round(current_weight, 2),
                suggested_weight=round(suggested_weight, 2),
                delta_weight=round(delta, 2),
                action=action,
            )
        )

    # AI rationale
    ai_rationale = f"Portfolio drift detected: equity at {current_equity_pct:.1f}% vs target {target_equity_pct:.1f}%. "
    if current_equity_pct > target_equity_pct + 2:
        ai_rationale += "Recommend reducing equity exposure. "
    elif current_equity_pct < target_equity_pct - 2:
        ai_rationale += "Recommend increasing equity exposure. "

    ai_rationale += "Review each position carefully and adjust for tax efficiency and client circumstances."

    # Log audit event
    db.add(
        AuditEvent(
            alert_id=alert.id,
            run_id=alert.run_id,
            event_type=AuditEventType.REBALANCE_SUGGESTION_CREATED,
            actor="operator_demo",
            details={
                "alert_id": alert.id,
                "portfolio_id": portfolio.id,
                "suggested_equity_pct": target_equity_pct,
            },
        )
    )
    db.commit()

    return RebalancingSuggestion(
        alert_id=alert.id,
        generated_at=datetime.utcnow(),
        current_equity_pct=round(current_equity_pct, 2),
        target_equity_pct=round(target_equity_pct, 2),
        current_fixed_income_pct=round(current_fixed_income_pct, 2),
        target_fixed_income_pct=round(target_fixed_income_pct, 2),
        current_cash_pct=round(current_cash_pct, 2),
        target_cash_pct=round(target_cash_pct, 2),
        line_items=line_items,
        ai_rationale=ai_rationale,
        requires_human_approval=True,
    )


@router.post("/{alert_id}/reallocation-plan", response_model=ReallocationPlanView)
def generate_reallocation_plan(
    alert_id: int,
    payload: ReallocationPlanRequest,
    db: Session = Depends(get_db),
) -> ReallocationPlanView:
    alert: Alert | None = (
        db.query(Alert)
        .options(
            joinedload(Alert.portfolio).joinedload(Portfolio.positions),
            joinedload(Alert.client),
        )
        .filter(Alert.id == alert_id)
        .first()
    )
    if not alert:
        raise HTTPException(
            status_code=404,
            detail=f"Alert {alert_id} not found. It may have been archived or removed; select an active alert and retry.",
        )

    portfolio = alert.portfolio
    positions = list(portfolio.positions)
    total_value = float(portfolio.total_value)

    current_cash_amount = sum(float(p.value) for p in positions if p.asset_class == "Cash")
    target_cash_amount = max(0.0, float(payload.target_cash_amount))
    additional_cash_needed = max(0.0, target_cash_amount - current_cash_amount)

    tax_inclusion_rate = 0.50
    marginal_tax_rate = 0.38

    sell_candidates = [
        p for p in positions if p.asset_class in {"Equity", "Fixed Income"} and float(p.value) > 0
    ]
    sell_candidates.sort(
        key=lambda p: (
            _estimate_gain_rate(p.ticker, p.asset_class),
            0 if p.asset_class == "Fixed Income" else 1,
            -float(p.value),
        )
    )

    trades: List[Dict[str, Any]] = []
    remaining = additional_cash_needed
    total_realized_gains = 0.0
    total_tax_impact = 0.0
    settlement_days = 0
    updated_values = {p.id: float(p.value) for p in positions}

    for pos in sell_candidates:
        if remaining <= 0:
            break
        available = float(pos.value)
        sell_amount = min(available, remaining)
        if sell_amount <= 0:
            continue
        gain_rate = _estimate_gain_rate(pos.ticker, pos.asset_class)
        estimated_gain = round(sell_amount * gain_rate, 2)
        estimated_tax = round(estimated_gain * tax_inclusion_rate * marginal_tax_rate, 2)
        unit_price = _estimate_unit_price(pos.ticker, pos.asset_class)
        units = round(sell_amount / unit_price, 4) if unit_price > 0 else 0.0
        settle = 2 if pos.asset_class == "Equity" else 1
        settlement_days = max(settlement_days, settle)

        trades.append(
            {
                "ticker": pos.ticker,
                "asset_class": pos.asset_class,
                "action": "SELL",
                "amount": round(sell_amount, 2),
                "estimated_units": units,
                "settlement_days": settle,
                "estimated_gain_realized": estimated_gain,
                "estimated_tax_cost": estimated_tax,
            }
        )
        updated_values[pos.id] = round(max(0.0, updated_values[pos.id] - sell_amount), 2)
        total_realized_gains += estimated_gain
        total_tax_impact += estimated_tax
        remaining -= sell_amount

    # The proposed sells are modeled as moving proceeds into cash.
    updated_cash_amount = current_cash_amount + sum(t["amount"] for t in trades)

    def _portfolio_volatility(values: Dict[int, float], cash_value: float) -> float:
        if total_value <= 0:
            return 0.0
        weighted = 0.0
        for pos in positions:
            if pos.asset_class == "Cash":
                continue
            value = values.get(pos.id, 0.0)
            weighted += (value / total_value) * _volatility_weight(pos.asset_class)
        weighted += (cash_value / total_value) * _volatility_weight("Cash")
        return round(weighted * 100, 2)

    current_values = {p.id: float(p.value) for p in positions}
    volatility_before = _portfolio_volatility(current_values, current_cash_amount)
    volatility_after = _portfolio_volatility(updated_values, updated_cash_amount)
    volatility_reduction_pct = round(max(0.0, volatility_before - volatility_after), 2)

    alternatives = [
        {
            "name": "Sell highest gain positions first",
            "estimated_tax_impact": round(total_tax_impact * 1.34, 2),
            "estimated_liquidity_days": max(2, settlement_days),
            "volatility_after": round(max(0.0, volatility_after - 0.2), 2),
            "rejected_reason": "Higher projected tax cost despite marginally better volatility.",
        },
        {
            "name": "Pro-rata liquidation across all risk assets",
            "estimated_tax_impact": round(total_tax_impact * 1.17, 2),
            "estimated_liquidity_days": settlement_days or 1,
            "volatility_after": round(volatility_after + 0.15, 2),
            "rejected_reason": "Faster, but less tax efficient and leaves more concentration.",
        },
        {
            "name": "Delay liquidation and fund externally",
            "estimated_tax_impact": 0.0,
            "estimated_liquidity_days": 10,
            "volatility_after": round(volatility_before, 2),
            "rejected_reason": "Misses down payment liquidity deadline and keeps current risk profile.",
        },
    ]

    if additional_cash_needed > 0 and not trades:
        raise HTTPException(status_code=400, detail="Unable to produce a sell plan for this portfolio")

    coverage = round(
        (sum(t["amount"] for t in trades) / additional_cash_needed * 100) if additional_cash_needed > 0 else 100.0,
        1,
    )
    ai_rationale = (
        f"AI selected low-gain lots first to raise ${additional_cash_needed:,.0f} for a down payment target of "
        f"${target_cash_amount:,.0f}, while reducing volatility from {volatility_before:.2f}% to {volatility_after:.2f}%. "
        f"Projected taxable gains are ${total_realized_gains:,.0f} with estimated tax impact of ${total_tax_impact:,.0f}."
    )

    assumptions = {
        "target_use_case": "Down payment reserve",
        "target_amount": round(target_cash_amount, 2),
        "cash_coverage_pct": coverage,
        "tax_inclusion_rate": tax_inclusion_rate,
        "marginal_tax_rate": marginal_tax_rate,
        "execution_mode": "SIMULATED_NOT_SENT",
        "pricing_model": "deterministic-demo-pricing-v1",
        "generated_for_client": alert.client.name,
    }

    plan = ReallocationPlan(
        alert_id=alert.id,
        status=ReallocationPlanStatus.PLANNED,
        target_cash_amount=round(target_cash_amount, 2),
        current_cash_amount=round(current_cash_amount, 2),
        additional_cash_needed=round(additional_cash_needed, 2),
        estimated_realized_gains=round(total_realized_gains, 2),
        estimated_tax_impact=round(total_tax_impact, 2),
        volatility_before=volatility_before,
        volatility_after=volatility_after,
        volatility_reduction_pct=volatility_reduction_pct,
        liquidity_days=max(1, settlement_days),
        trades=trades,
        alternatives_considered=alternatives,
        assumptions=assumptions,
        ai_rationale=ai_rationale,
    )
    db.add(plan)
    db.flush()

    db.add(
        AuditEvent(
            alert_id=alert.id,
            run_id=alert.run_id,
            event_type=AuditEventType.REALLOCATION_PLAN_CREATED,
            actor="operator_demo",
            details={
                "plan_id": plan.id,
                "status": plan.status.value,
                "target_cash_amount": round(target_cash_amount, 2),
                "additional_cash_needed": round(additional_cash_needed, 2),
                "estimated_tax_impact": round(total_tax_impact, 2),
                "trades_count": len(trades),
            },
        )
    )
    db.commit()
    db.refresh(plan)
    return _plan_to_view(plan)


@router.post("/reallocation-plans/{plan_id}/queue", response_model=ReallocationPlanView)
def queue_reallocation_plan(
    plan_id: int,
    db: Session = Depends(get_db),
) -> ReallocationPlanView:
    plan: ReallocationPlan | None = (
        db.query(ReallocationPlan)
        .options(joinedload(ReallocationPlan.alert))
        .filter(ReallocationPlan.id == plan_id)
        .first()
    )
    if not plan:
        raise HTTPException(status_code=404, detail="Reallocation plan not found")
    if plan.status not in {ReallocationPlanStatus.PLANNED, ReallocationPlanStatus.QUEUED}:
        raise HTTPException(status_code=409, detail="Only planned plans can be queued")

    if plan.status == ReallocationPlanStatus.PLANNED:
        plan.status = ReallocationPlanStatus.QUEUED
        plan.queued_at = datetime.utcnow()
        db.add(
            AuditEvent(
                alert_id=plan.alert_id,
                run_id=plan.alert.run_id if plan.alert else None,
                event_type=AuditEventType.REALLOCATION_PLAN_QUEUED,
                actor="operator_demo",
                details={"plan_id": plan.id, "status": plan.status.value},
            )
        )
        db.commit()
        db.refresh(plan)

    return _plan_to_view(plan)


@router.post("/reallocation-plans/{plan_id}/approve", response_model=ReallocationPlanView)
def approve_reallocation_plan(
    plan_id: int,
    db: Session = Depends(get_db),
) -> ReallocationPlanView:
    plan: ReallocationPlan | None = (
        db.query(ReallocationPlan)
        .options(joinedload(ReallocationPlan.alert))
        .filter(ReallocationPlan.id == plan_id)
        .first()
    )
    if not plan:
        raise HTTPException(status_code=404, detail="Reallocation plan not found")
    if plan.status not in {ReallocationPlanStatus.QUEUED, ReallocationPlanStatus.APPROVED}:
        raise HTTPException(status_code=409, detail="Plan must be queued before approval")

    if plan.status == ReallocationPlanStatus.QUEUED:
        plan.status = ReallocationPlanStatus.APPROVED
        plan.approved_by = "operator_demo"
        plan.approved_at = datetime.utcnow()
        db.add(
            AuditEvent(
                alert_id=plan.alert_id,
                run_id=plan.alert.run_id if plan.alert else None,
                event_type=AuditEventType.REALLOCATION_PLAN_APPROVED,
                actor="operator_demo",
                details={"plan_id": plan.id, "status": plan.status.value, "approved_by": plan.approved_by},
            )
        )
        db.commit()
        db.refresh(plan)

    return _plan_to_view(plan)


@router.post("/reallocation-plans/{plan_id}/execute", response_model=ReallocationPlanView)
def execute_reallocation_plan(
    plan_id: int,
    db: Session = Depends(get_db),
) -> ReallocationPlanView:
    plan: ReallocationPlan | None = (
        db.query(ReallocationPlan)
        .options(joinedload(ReallocationPlan.alert))
        .filter(ReallocationPlan.id == plan_id)
        .first()
    )
    if not plan:
        raise HTTPException(status_code=404, detail="Reallocation plan not found")
    if plan.status not in {ReallocationPlanStatus.APPROVED, ReallocationPlanStatus.EXECUTED}:
        raise HTTPException(status_code=409, detail="Plan must be approved before execution")

    if plan.status == ReallocationPlanStatus.APPROVED:
        now = datetime.utcnow()
        plan.status = ReallocationPlanStatus.EXECUTED
        plan.executed_at = now
        plan.execution_reference = f"SIM-{plan.id}-{now.strftime('%Y%m%d%H%M%S')}"
        db.add(
            AuditEvent(
                alert_id=plan.alert_id,
                run_id=plan.alert.run_id if plan.alert else None,
                event_type=AuditEventType.REALLOCATION_PLAN_EXECUTED,
                actor="operator_demo",
                details={
                    "plan_id": plan.id,
                    "status": plan.status.value,
                    "execution_reference": plan.execution_reference,
                    "simulated": True,
                },
            )
        )
        db.commit()
        db.refresh(plan)

    return _plan_to_view(plan)
