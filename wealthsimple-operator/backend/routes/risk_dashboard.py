from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from db import get_db
from models import Alert, Client, Portfolio, RiskClientRow, RiskDashboardResponse

router = APIRouter(prefix="/risk-dashboard", tags=["risk-dashboard"])


@router.get("/summary", response_model=RiskDashboardResponse)
def get_risk_dashboard(db: Session = Depends(get_db)) -> RiskDashboardResponse:
    """
    Get risk dashboard with forward-looking risk scores and trend direction.

    For each client:
    - current_risk: latest alert's risk_score (or None if no alert)
    - previous_risk: second-latest alert's risk_score (if exists, else None)
    - trend: "RISING" if delta > 0.5, "FALLING" if delta < -0.5, "STABLE" otherwise
    - predicted_30d_risk: current * (1.08 if RISING, 0.96 if FALLING, 1.01 if STABLE)
    - days_without_review: days since latest alert was created (if OPEN) or reviewed
    """
    # Load all clients with portfolios
    clients = db.query(Client).all()

    rows: List[RiskClientRow] = []

    for client in clients:
        # Get all portfolios for this client
        portfolios = db.query(Portfolio).filter(Portfolio.client_id == client.id).all()

        for portfolio in portfolios:
            # Get latest 2 alerts for this portfolio
            latest_alerts = (
                db.query(Alert)
                .filter(Alert.portfolio_id == portfolio.id)
                .order_by(Alert.created_at.desc())
                .limit(2)
                .all()
            )

            if not latest_alerts:
                continue  # Skip portfolios with no alerts

            # Current and previous risk
            current_alert = latest_alerts[0]
            current_risk = current_alert.risk_score

            previous_risk: Optional[float] = None
            trend = "STABLE"
            trend_pct: Optional[float] = None

            if len(latest_alerts) >= 2:
                previous_alert = latest_alerts[1]
                previous_risk = previous_alert.risk_score
                delta = current_risk - previous_risk

                if delta > 0.5:
                    trend = "RISING"
                elif delta < -0.5:
                    trend = "FALLING"
                else:
                    trend = "STABLE"

                if previous_risk != 0:
                    trend_pct = round((delta / previous_risk) * 100, 1)

            # Predict 30d risk
            if trend == "RISING":
                predicted_30d_risk = min(10.0, current_risk * 1.08)
            elif trend == "FALLING":
                predicted_30d_risk = max(0.0, current_risk * 0.96)
            else:
                predicted_30d_risk = current_risk * 1.01

            # Days without review
            days_without_review = (datetime.utcnow() - current_alert.created_at).days

            row = RiskClientRow(
                client_id=client.id,
                client_name=client.name,
                segment=client.segment,
                risk_profile=client.risk_profile,
                portfolio_id=portfolio.id,
                portfolio_name=portfolio.name,
                total_value=float(portfolio.total_value),
                current_risk=current_risk,
                previous_risk=previous_risk,
                trend=trend,
                trend_pct=trend_pct,
                predicted_30d_risk=predicted_30d_risk,
                days_without_review=days_without_review,
                latest_priority=current_alert.priority.value,
                latest_alert_status=current_alert.status.value
            )
            rows.append(row)

    # Sort by predicted_30d_risk (descending)
    rows.sort(key=lambda r: r.predicted_30d_risk, reverse=True)

    # Compute aggregates
    if rows:
        avg_current_risk = sum(r.current_risk for r in rows) / len(rows)
        avg_predicted_risk = sum(r.predicted_30d_risk for r in rows) / len(rows)
        rising_count = sum(1 for r in rows if r.trend == "RISING")
        high_risk_count = sum(1 for r in rows if r.predicted_30d_risk >= 7)
    else:
        avg_current_risk = 0.0
        avg_predicted_risk = 0.0
        rising_count = 0
        high_risk_count = 0

    return RiskDashboardResponse(
        rows=rows,
        avg_current_risk=avg_current_risk,
        avg_predicted_risk=avg_predicted_risk,
        rising_count=rising_count,
        high_risk_count=high_risk_count,
        total_clients=len(clients)
    )
