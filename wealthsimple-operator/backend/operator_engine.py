from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from ai.provider import AIProvider
from db import session_scope
from models import (
    Alert,
    AlertStatus,
    AuditEvent,
    AuditEventType,
    Client,
    MonitoringUniverseSummary,
    Portfolio,
    Priority,
    Run,
    RunSummary,
)


PRIORITY_ORDER = {
    Priority.HIGH: 0,
    Priority.MEDIUM: 1,
    Priority.LOW: 2,
}


def _compute_metrics(portfolio: Portfolio) -> Dict[str, float]:
    """Compute deterministic risk metrics for a portfolio."""
    positions = portfolio.positions
    if not positions:
        return {
            "concentration_score": 0.0,
            "drift_score": 0.0,
            "volatility_proxy": 0.0,
            "risk_score": 0.0,
        }

    # Concentration: max weight on any single position, scaled 0-10
    max_weight = max(float(p.weight) for p in positions)
    concentration_score = round(min(10.0, max_weight * 10.0), 1)

    # Realized allocation by simple asset class buckets
    equity_weight = sum(float(p.weight) for p in positions if p.asset_class in ("Equity", "ETF"))
    fixed_income_weight = sum(float(p.weight) for p in positions if p.asset_class == "Fixed Income")
    cash_weight = sum(float(p.weight) for p in positions if p.asset_class == "Cash")

    # Targets are stored as percentages (0-100)
    target_equity = float(portfolio.target_equity_pct)
    target_fixed_income = float(portfolio.target_fixed_income_pct)
    target_cash = float(portfolio.target_cash_pct)

    realized_equity_pct = equity_weight * 100.0
    realized_fixed_income_pct = fixed_income_weight * 100.0
    realized_cash_pct = cash_weight * 100.0

    diff_equity = abs(realized_equity_pct - target_equity)
    diff_fixed_income = abs(realized_fixed_income_pct - target_fixed_income)
    diff_cash = abs(realized_cash_pct - target_cash)

    # Average deviation scaled into 0-10 band (10 ~ 50pp avg deviation)
    avg_deviation = (diff_equity + diff_fixed_income + diff_cash) / 3.0
    drift_score = round(min(10.0, avg_deviation / 5.0), 1)

    # Volatility proxy: deterministic pseudo-random function of portfolio id
    # to keep things stable across runs without persisting a history series.
    volatility_raw = (portfolio.id * 37 % 97) / 96.0  # in [0, 1)
    volatility_proxy = round(volatility_raw * 10.0, 1)

    risk_score = round(
        (concentration_score + drift_score + volatility_proxy) / 3.0,
        1,
    )

    return {
        "concentration_score": concentration_score,
        "drift_score": drift_score,
        "volatility_proxy": volatility_proxy,
        "risk_score": risk_score,
    }


def _latest_metrics_for_portfolio(db: Session, portfolio_id: int) -> Dict[str, float] | None:
    last_alert: Alert | None = (
        db.query(Alert)
        .filter(Alert.portfolio_id == portfolio_id)
        .order_by(Alert.created_at.desc())
        .first()
    )
    if not last_alert:
        return None
    return {
        "concentration_score": last_alert.concentration_score,
        "drift_score": last_alert.drift_score,
        "volatility_proxy": last_alert.volatility_proxy,
        "risk_score": last_alert.risk_score,
    }


def run_operator(db: Session, provider: AIProvider, actor: str = "operator_demo") -> RunSummary:
    """Run a full operator scan across all portfolios.

    Creates a Run record, computes metrics, calls the AI provider, stores alerts,
    and logs audit events. Returns a summary suitable for the Operator UI.
    """
    now = datetime.utcnow()
    run = Run(started_at=now, provider_used=provider.name)
    db.add(run)
    db.flush()  # assign run.id

    # Run-level audit start
    db.add(
        AuditEvent(
            run_id=run.id,
            event_type=AuditEventType.RUN_STARTED,
            actor=actor,
            details={"provider_used": provider.name},
        )
    )

    portfolios: List[Portfolio] = (
        db.query(Portfolio)
        .options(
            joinedload(Portfolio.client),
            joinedload(Portfolio.positions),
        )
        .all()
    )

    alerts_created = 0
    priority_counts: Dict[Priority, int] = defaultdict(int)

    for portfolio in portfolios:
        client: Client = portfolio.client
        metrics = _compute_metrics(portfolio)
        last_metrics = _latest_metrics_for_portfolio(db, portfolio.id)

        context = {
            "client": {
                "id": client.id,
                "name": client.name,
                "email": client.email,
                "segment": client.segment,
                "risk_profile": client.risk_profile,
            },
            "portfolio": {
                "id": portfolio.id,
                "name": portfolio.name,
                "total_value": float(portfolio.total_value),
                "target_equity_pct": float(portfolio.target_equity_pct),
                "target_fixed_income_pct": float(portfolio.target_fixed_income_pct),
                "target_cash_pct": float(portfolio.target_cash_pct),
            },
            "last_metrics": last_metrics or {},
        }

        ai_output = provider.score_portfolio(metrics=metrics, context=context)

        alert = Alert(
            run_id=run.id,
            portfolio_id=portfolio.id,
            client_id=client.id,
            priority=ai_output.priority,
            confidence=int(ai_output.confidence),
            event_title=ai_output.event_title,
            summary=ai_output.summary,
            reasoning_bullets=[str(b) for b in ai_output.reasoning_bullets],
            human_review_required=bool(ai_output.human_review_required),
            suggested_next_step=ai_output.suggested_next_step,
            decision_trace_steps=[
                {"step": s.step, "detail": s.detail} for s in ai_output.decision_trace_steps
            ],
            change_detection=[
                {"metric": c.metric, "from": c.from_value, "to": c.to_value}
                for c in ai_output.change_detection
            ],
            status=AlertStatus.OPEN,
            concentration_score=metrics["concentration_score"],
            drift_score=metrics["drift_score"],
            volatility_proxy=metrics["volatility_proxy"],
            risk_score=metrics["risk_score"],
        )
        db.add(alert)
        db.flush()

        alerts_created += 1
        priority_counts[ai_output.priority] += 1

        db.add(
            AuditEvent(
                alert_id=alert.id,
                run_id=run.id,
                event_type=AuditEventType.ALERT_CREATED,
                actor=actor,
                details={
                    "priority": ai_output.priority.value,
                    "confidence": int(ai_output.confidence),
                    "human_review_required": bool(ai_output.human_review_required),
                },
            )
        )

    run.alerts_created = alerts_created
    run.completed_at = datetime.utcnow()

    db.add(
        AuditEvent(
            run_id=run.id,
            event_type=AuditEventType.RUN_COMPLETED,
            actor=actor,
            details={
                "alerts_created": alerts_created,
                "priority_counts": {p.value: c for p, c in priority_counts.items()},
            },
        )
    )

    db.commit()

    # Build summary for this run
    top_alerts = _top_alerts_for_run(db, run.id, limit=20)

    # Ensure all priorities appear in counts
    full_priority_counts: Dict[Priority, int] = {p: 0 for p in Priority}
    for p, c in priority_counts.items():
        full_priority_counts[p] = c

    return RunSummary(
        run_id=run.id,
        provider_used=run.provider_used,
        created_alerts_count=alerts_created,
        priority_counts=full_priority_counts,
        top_alerts=top_alerts,
    )


def _top_alerts_for_run(db: Session, run_id: int, limit: int = 20):
    from models import AlertSummary, ClientSummary, PortfolioSummary

    alerts: List[Alert] = (
        db.query(Alert)
        .options(
            joinedload(Alert.client),
            joinedload(Alert.portfolio),
        )
        .filter(Alert.run_id == run_id)
        .all()
    )

    def sort_key(a: Alert) -> Tuple[int, datetime]:
        return PRIORITY_ORDER.get(a.priority, 99), a.created_at

    alerts_sorted = sorted(alerts, key=sort_key)[:limit]

    summaries: List[AlertSummary] = []
    for a in alerts_sorted:
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
        summaries.append(
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

    return summaries
def compute_monitoring_universe_summary(db: Session) -> MonitoringUniverseSummary:
    """Aggregate statistics for the Monitoring Universe page."""
    total_clients = db.query(func.count(Client.id)).scalar() or 0
    total_portfolios = db.query(func.count(Portfolio.id)).scalar() or 0
    total_runs = db.query(func.count(Run.id)).scalar() or 0

    alerts_by_priority: Dict[Priority, int] = {p: 0 for p in Priority}
    rows = db.query(Alert.priority, func.count(Alert.id)).group_by(Alert.priority).all()
    for priority, count in rows:
        alerts_by_priority[priority] = int(count or 0)

    alerts_by_status: Dict[AlertStatus, int] = {s: 0 for s in AlertStatus}
    rows_status = db.query(Alert.status, func.count(Alert.id)).group_by(Alert.status).all()
    for status, count in rows_status:
        alerts_by_status[status] = int(count or 0)

    total_alerts = sum(alerts_by_priority.values())
    average_alerts_per_run = float(total_alerts) / float(total_runs) if total_runs else 0.0

    human_required_count = (
        db.query(func.count(Alert.id)).filter(Alert.human_review_required.is_(True)).scalar() or 0
    )
    percent_human_required = (
        float(human_required_count) / float(total_alerts) * 100.0 if total_alerts else 0.0
    )

    return MonitoringUniverseSummary(
        total_clients=total_clients,
        total_portfolios=total_portfolios,
        alerts_by_priority=alerts_by_priority,
        alerts_by_status=alerts_by_status,
        total_runs=total_runs,
        average_alerts_per_run=round(average_alerts_per_run, 2),
        percent_alerts_human_review_required=round(percent_human_required, 2),
    )

