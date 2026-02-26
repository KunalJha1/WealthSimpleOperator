from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, Optional

from dotenv import load_dotenv
from sqlalchemy.orm import joinedload

from ai.provider import get_provider
from db import SessionLocal
from models import Alert, Client, Portfolio
from operator_engine import run_operator


load_dotenv(dotenv_path=Path(__file__).with_name(".env"), override=False)


def _is_blank(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    return False


def _needs_description_backfill(alert: Alert) -> bool:
    return (
        _is_blank(alert.event_title)
        or _is_blank(alert.summary)
        or not isinstance(alert.reasoning_bullets, list)
        or len(alert.reasoning_bullets) == 0
        or _is_blank(alert.suggested_next_step)
        or not isinstance(alert.decision_trace_steps, list)
        or len(alert.decision_trace_steps) == 0
    )


def _build_context(portfolio: Portfolio, client: Client, last_metrics: Dict[str, float]) -> Dict:
    return {
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
        "last_metrics": last_metrics,
    }


def _previous_metrics_for_alert(db, alert: Alert) -> Dict[str, float]:
    previous: Optional[Alert] = (
        db.query(Alert)
        .filter(
            Alert.portfolio_id == alert.portfolio_id,
            Alert.created_at < alert.created_at,
        )
        .order_by(Alert.created_at.desc())
        .first()
    )
    if not previous:
        return {}
    return {
        "concentration_score": float(previous.concentration_score),
        "drift_score": float(previous.drift_score),
        "volatility_proxy": float(previous.volatility_proxy),
        "risk_score": float(previous.risk_score),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill missing Risk Brief AI descriptions for existing alerts."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Maximum alerts to backfill. 0 means all missing alerts.",
    )
    parser.add_argument(
        "--commit-every",
        type=int,
        default=10,
        help="Commit every N updated alerts.",
    )
    parser.add_argument(
        "--run-operator-first",
        action="store_true",
        help="Run one full operator scan before backfilling missing descriptions.",
    )
    args = parser.parse_args()

    provider = get_provider()
    db = SessionLocal()

    updated = 0
    failed = 0
    scanned = 0

    try:
        if args.run_operator_first:
            summary = run_operator(db=db, provider=provider, actor="description_backfill")
            print(
                f"Created fresh run first | run_id={summary.run_id} | alerts={summary.created_alerts_count}"
            )

        alerts = (
            db.query(Alert)
            .options(
                joinedload(Alert.client),
                joinedload(Alert.portfolio).joinedload(Portfolio.positions),
            )
            .order_by(Alert.created_at.asc())
            .all()
        )

        for alert in alerts:
            scanned += 1
            if not _needs_description_backfill(alert):
                continue

            if args.limit > 0 and updated >= args.limit:
                break

            try:
                metrics = {
                    "concentration_score": float(alert.concentration_score),
                    "drift_score": float(alert.drift_score),
                    "volatility_proxy": float(alert.volatility_proxy),
                    "risk_score": float(alert.risk_score),
                }
                last_metrics = _previous_metrics_for_alert(db, alert)
                context = _build_context(
                    portfolio=alert.portfolio,
                    client=alert.client,
                    last_metrics=last_metrics,
                )
                ai_output = provider.score_portfolio(metrics=metrics, context=context)

                alert.event_title = ai_output.event_title
                alert.summary = ai_output.summary
                alert.reasoning_bullets = [str(b) for b in (ai_output.reasoning_bullets or [])]
                alert.human_review_required = bool(ai_output.human_review_required)
                alert.suggested_next_step = ai_output.suggested_next_step
                alert.decision_trace_steps = [
                    {"step": s.step, "detail": s.detail}
                    for s in (ai_output.decision_trace_steps or [])
                ]
                alert.change_detection = [
                    {"metric": c.metric, "from": c.from_value, "to": c.to_value}
                    for c in (ai_output.change_detection or [])
                ]

                updated += 1
                if updated % max(1, args.commit_every) == 0:
                    db.commit()
                    print(f"Committed {updated} backfilled alerts...")
            except Exception as exc:
                failed += 1
                db.rollback()
                print(f"Failed alert_id={alert.id}: {exc}")

        db.commit()
        print(
            f"Backfill complete | provider={getattr(provider, 'name', 'unknown')} "
            f"| scanned={scanned} | updated={updated} | failed={failed}"
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
