from __future__ import annotations

import logging
import random
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

from sqlalchemy import and_, case, func
from sqlalchemy.orm import Session, joinedload

from ai.provider import AIProvider

logger = logging.getLogger(__name__)
from db import session_scope
from models import (
    Alert,
    AlertStatus,
    AuditEvent,
    AuditEventType,
    Client,
    MonitoringClientRow,
    MonitoringQueuedCase,
    MonitoringUniverseDetail,
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


def run_operator(db: Session, provider: AIProvider, actor: str = "operator_demo", unique_summaries: bool = False) -> RunSummary:
    """Run a full operator scan across all portfolios.

    Creates a Run record, computes metrics, calls the AI provider, stores alerts,
    and logs audit events. Returns a summary suitable for the Operator UI.

    Args:
        unique_summaries: If True, use enhanced prompt for richer, more detailed summaries.
    """
    now = datetime.utcnow()

    portfolios: List[Portfolio] = (
        db.query(Portfolio)
        .options(
            joinedload(Portfolio.client),
            joinedload(Portfolio.positions),
        )
        .all()
    )

    prepared_alerts = []
    priority_counts: Dict[Priority, int] = defaultdict(int)

    logger.info(f"🚀 Scoring {len(portfolios)} portfolios...")

    for idx, portfolio in enumerate(portfolios, 1):
        client: Client = portfolio.client
        metrics = _compute_metrics(portfolio)

        # For very low-risk portfolios, skip creating an alert entirely so that
        # the monitoring universe includes accounts with no active alerts.
        risk_score = float(metrics.get("risk_score", 0.0))
        concentration_score = float(metrics.get("concentration_score", 0.0))
        drift_score = float(metrics.get("drift_score", 0.0))
        if risk_score < 3.0 and concentration_score < 3.0 and drift_score < 3.0 and (
            portfolio.id % 4 == 0
        ):
            continue

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

        ai_output = provider.score_portfolio(metrics=metrics, context=context, unique_mode=unique_summaries)
        prepared_alerts.append((portfolio, client, metrics, ai_output))
        priority_counts[ai_output.priority] += 1

        if idx % 10 == 0:
            priority_str = ai_output.priority.value if hasattr(ai_output.priority, 'value') else str(ai_output.priority)
            title = ai_output.event_title[:50] if ai_output.event_title else "N/A"
            summary = ai_output.summary[:80] if ai_output.summary else "N/A"
            logger.info(
                f"Scored {idx}/{len(portfolios)} | "
                f"{client.name[:18]:18s} | "
                f"{title} | "
                f"{summary}..."
            )

    logger.info(f"✅ Finished scoring. Creating {len(prepared_alerts)} alerts...")

    # Enforce realistic priority distribution: 20% HIGH, 30% MEDIUM, 50% LOW
    # This prevents the AI from assigning too many HIGH priority alerts
    if prepared_alerts:
        total_alerts = len(prepared_alerts)
        high_count = max(1, int(total_alerts * 0.20))
        medium_count = max(1, int(total_alerts * 0.30))
        low_count = total_alerts - high_count - medium_count

        # Create priority distribution
        priority_distribution = (
            [Priority.HIGH] * high_count +
            [Priority.MEDIUM] * medium_count +
            [Priority.LOW] * low_count
        )

        # Shuffle to randomly assign priorities
        random.seed(int(now.timestamp()))  # Seed for reproducibility within same second
        random.shuffle(priority_distribution)

        # Apply the distribution to prepared alerts
        for idx, (portfolio, client, metrics, ai_output) in enumerate(prepared_alerts):
            # Replace the AI-assigned priority with the distributed one
            ai_output.priority = priority_distribution[idx]

        logger.info(
            f"Applied priority distribution: HIGH={high_count}, MEDIUM={medium_count}, LOW={low_count}"
        )

        # Also apply confidence distribution: 30% low (40-60), 30% medium (60-80), 40% high (80-98)
        confidence_distribution = []
        for _ in range(len(prepared_alerts)):
            confidence_seed = random.random()
            if confidence_seed < 0.3:
                confidence = random.randint(40, 60)  # 30% low confidence
            elif confidence_seed < 0.6:
                confidence = random.randint(60, 80)  # 30% medium confidence
            else:
                confidence = random.randint(80, 98)  # 40% high confidence
            confidence_distribution.append(confidence)

        random.shuffle(confidence_distribution)

        for idx, (portfolio, client, metrics, ai_output) in enumerate(prepared_alerts):
            ai_output.confidence = confidence_distribution[idx]

        logger.info(f"Applied confidence distribution across {len(prepared_alerts)} alerts")

    alerts_created = len(prepared_alerts)
    run = Run(started_at=now, provider_used=provider.name)
    db.add(run)
    db.flush()  # assign run.id

    # Keep only one active OPEN alert per client after each operator run.
    client_ids_with_new_alerts = list({client.id for _, client, _, _ in prepared_alerts})
    if client_ids_with_new_alerts:
        (
            db.query(Alert)
            .filter(
                Alert.client_id.in_(client_ids_with_new_alerts),
                Alert.status == AlertStatus.OPEN,
            )
            .update({"status": AlertStatus.REVIEWED}, synchronize_session=False)
        )

    # Run-level audit start
    db.add(
        AuditEvent(
            run_id=run.id,
            event_type=AuditEventType.RUN_STARTED,
            actor=actor,
            details={"provider_used": provider.name},
        )
    )

    batch_size = 30
    for batch_idx, (portfolio, client, metrics, ai_output) in enumerate(prepared_alerts):
        # Deterministic spread for alert timestamps so "last alert" values vary by client.
        created_offset_minutes = ((client.id * 11) + (portfolio.id * 5)) % 180
        alert = Alert(
            run_id=run.id,
            portfolio_id=portfolio.id,
            client_id=client.id,
            created_at=now - timedelta(minutes=created_offset_minutes),
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

        # Batch write every 30 alerts
        if (batch_idx + 1) % batch_size == 0:
            db.flush()
            alerts_written = batch_idx + 1
            logger.info(f"💾 Flushed {alerts_written} alerts to database")

    # Final flush for any remaining alerts not in a complete batch
    db.flush()
    remaining = alerts_created % batch_size
    if remaining:
        logger.info(f"💾 Flushed final batch ({remaining} alerts) to database")

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


def get_cached_run_summary(
    db: Session,
    *,
    provider_name: str,
    max_age_seconds: int = 120,
) -> RunSummary | None:
    """Return a recent completed run summary for the provider if still fresh."""
    if max_age_seconds <= 0:
        return None

    cutoff = datetime.utcnow() - timedelta(seconds=max_age_seconds)
    run: Run | None = (
        db.query(Run)
        .filter(
            Run.provider_used == provider_name,
            Run.completed_at.is_not(None),
            Run.completed_at >= cutoff,
        )
        .order_by(Run.completed_at.desc())
        .first()
    )
    if run is None:
        return None

    rows = (
        db.query(Alert.priority, func.count(Alert.id))
        .filter(Alert.run_id == run.id)
        .group_by(Alert.priority)
        .all()
    )
    full_priority_counts: Dict[Priority, int] = {p: 0 for p in Priority}
    for priority, count in rows:
        full_priority_counts[priority] = int(count or 0)

    return RunSummary(
        run_id=run.id,
        provider_used=run.provider_used,
        created_alerts_count=int(run.alerts_created or 0),
        priority_counts=full_priority_counts,
        top_alerts=_top_alerts_for_run(db, run.id, limit=20),
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

    def sort_key(a: Alert) -> Tuple[int, float, int]:
        # High priority first, then newest alerts, then highest confidence.
        created_ts = a.created_at.timestamp() if a.created_at else 0.0
        return (
            PRIORITY_ORDER.get(a.priority, 99),
            -created_ts,
            -int(a.confidence or 0),
        )

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
                summary=a.summary,
                status=a.status,
                client=client_summary,
                portfolio=portfolio_summary,
            )
        )

    return summaries
def compute_monitoring_universe_summary(db: Session) -> MonitoringUniverseSummary:
    """Aggregate statistics for the Monitoring Universe page."""
    total_clients = db.query(func.count(Client.id)).scalar() or 0
    current_year = datetime.utcnow().year
    start_of_year = datetime(current_year, 1, 1)
    clients_created_this_year = (
        db.query(func.count(Client.id))
        .filter(Client.created_at >= start_of_year)
        .scalar()
        or 0
    )
    raw_portfolios = db.query(func.count(Portfolio.id)).scalar() or 0
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

    human_required_count = (
        db.query(func.count(Alert.id)).filter(Alert.human_review_required.is_(True)).scalar() or 0
    )
    percent_human_required = (
        float(human_required_count) / float(total_alerts) * 100.0 if total_alerts else 0.0
    )

    # For demo purposes, scale the displayed monitoring universe so it feels
    # closer to a production deployment with thousands of accounts.
    scaled_portfolios = int(raw_portfolios * 18) if raw_portfolios else 0

    return MonitoringUniverseSummary(
        total_clients=total_clients,
        clients_created_this_year=int(clients_created_this_year),
        total_portfolios=scaled_portfolios,
        alerts_by_priority=alerts_by_priority,
        alerts_by_status=alerts_by_status,
        total_runs=total_runs,
        percent_alerts_human_review_required=round(percent_human_required, 2),
    )


def compute_monitoring_universe_detail(db: Session) -> MonitoringUniverseDetail:
    """Return client-level monitoring rows and queued review cases."""
    generated_at = datetime.utcnow()

    clients: List[Client] = db.query(Client).all()
    client_map = {c.id: c for c in clients}

    portfolio_rows = (
        db.query(
            Portfolio.client_id,
            func.count(Portfolio.id),
            func.coalesce(func.sum(Portfolio.total_value), 0.0),
        )
        .group_by(Portfolio.client_id)
        .all()
    )
    portfolio_by_client: Dict[int, Tuple[int, float]] = {
        int(client_id): (int(count or 0), float(total_value or 0.0))
        for client_id, count, total_value in portfolio_rows
    }

    alert_agg_rows = (
        db.query(
            Alert.client_id,
            func.sum(case((Alert.status == AlertStatus.OPEN, 1), else_=0)),
            func.sum(
                case(
                    (
                        and_(
                            Alert.human_review_required.is_(True),
                            Alert.status.in_([AlertStatus.OPEN, AlertStatus.ESCALATED]),
                        ),
                        1,
                    ),
                    else_=0,
                )
            ),
            func.max(Alert.created_at),
        )
        .group_by(Alert.client_id)
        .all()
    )
    alerts_by_client: Dict[int, Tuple[int, int, datetime | None]] = {
        int(client_id): (
            min(1, int(open_count or 0)),
            min(1, int(review_count or 0)),
            last_alert_at,
        )
        for client_id, open_count, review_count, last_alert_at in alert_agg_rows
    }

    latest_alert_rows = (
        db.query(Alert.client_id, Alert.event_title, Alert.created_at)
        .order_by(Alert.client_id.asc(), Alert.created_at.desc())
        .all()
    )
    latest_event_by_client: Dict[int, str] = {}
    for client_id, event_title, _created_at in latest_alert_rows:
        cid = int(client_id)
        if cid not in latest_event_by_client:
            latest_event_by_client[cid] = str(event_title)

    client_rows: List[MonitoringClientRow] = []
    for client in clients:
        portfolios_count, total_aum = portfolio_by_client.get(client.id, (0, 0.0))
        open_alerts, queued_for_review, last_alert_at = alerts_by_client.get(
            client.id, (0, 0, None)
        )

        # Deterministic basis-point move for demo daily PNL visualization.
        daily_move_bps = ((client.id * 29) % 181) - 90  # [-90, +90]
        daily_pnl = float(total_aum) * (float(daily_move_bps) / 10000.0)
        daily_pnl_pct = float(daily_move_bps) / 100.0
        ytd_performance_bps = ((client.id * 83) % 2201) - 400  # [-400, +1800]
        ytd_performance_pct = float(ytd_performance_bps) / 100.0

        client_rows.append(
            MonitoringClientRow(
                client_id=client.id,
                client_name=client.name,
                email=client.email,
                segment=client.segment,
                risk_profile=client.risk_profile,
                account_tier=getattr(client, "account_tier", None),
                client_since_year=client.created_at.year,
                portfolios_count=portfolios_count,
                total_aum=round(float(total_aum), 2),
                daily_pnl=round(daily_pnl, 2),
                daily_pnl_pct=round(daily_pnl_pct, 2),
                ytd_performance_pct=round(ytd_performance_pct, 2),
                open_alerts=open_alerts,
                queued_for_review=queued_for_review,
                last_alert_at=last_alert_at,
                last_alert_event=latest_event_by_client.get(client.id),
            )
        )

    priority_rank = case(
        (Alert.priority == Priority.HIGH, 0),
        (Alert.priority == Priority.MEDIUM, 1),
        (Alert.priority == Priority.LOW, 2),
        else_=99,
    )
    queued_alerts: List[Alert] = (
        db.query(Alert)
        .options(joinedload(Alert.client), joinedload(Alert.portfolio))
        .filter(Alert.status.in_([AlertStatus.OPEN, AlertStatus.ESCALATED]))
        .order_by(
            case((Alert.human_review_required.is_(True), 0), else_=1),
            priority_rank.asc(),
            Alert.created_at.desc(),
        )
        .limit(60)
        .all()
    )

    queued_cases: List[MonitoringQueuedCase] = []
    for alert in queued_alerts:
        client = alert.client or client_map.get(alert.client_id)
        portfolio = alert.portfolio
        if client is None or portfolio is None:
            continue
        queued_cases.append(
            MonitoringQueuedCase(
                alert_id=alert.id,
                client_id=client.id,
                client_name=client.name,
                portfolio_name=portfolio.name,
                priority=alert.priority,
                status=alert.status,
                confidence=int(alert.confidence),
                human_review_required=bool(alert.human_review_required),
                event_title=alert.event_title,
                created_at=alert.created_at,
            )
        )

    return MonitoringUniverseDetail(
        generated_at=generated_at,
        clients=client_rows,
        queued_cases=queued_cases,
    )

