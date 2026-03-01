from __future__ import annotations

from typing import Dict, List, Optional

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from db import get_db
from models import Alert, Client, Portfolio, Position, TaxLossOpportunity, TaxLossResponse

router = APIRouter(prefix="/tax-loss", tags=["tax-loss"])


def _estimate_unit_price(ticker: str, asset_class: str) -> float:
    """
    Deterministic unit price estimation using ticker hash.
    Pattern reused from routes/alerts.py:87-93.
    """
    seed = (sum(ord(c) for c in ticker) % 35) + 40
    if asset_class == "Equity":
        return float(seed + 60)
    if asset_class == "Fixed Income":
        return float(seed // 2 + 85)
    return 1.0


def _estimate_replacement_ticker(asset_class: str) -> Optional[str]:
    """Suggest a replacement ETF based on asset class."""
    replacements = {
        "Equity": "VFV",  # Vanguard US Index
        "Fixed Income": "VAB",  # Vanguard Aggregate Bond
        "Cash": "PSA",  # Psagot Cash Management
    }
    return replacements.get(asset_class)


@router.get("/opportunities", response_model=TaxLossResponse)
def get_tax_loss_opportunities(db: Session = Depends(get_db)) -> TaxLossResponse:
    """
    Scan all positions for tax-loss harvesting opportunities.

    Uses synthetic estimates (no historical cost basis):
    - unit_price: deterministic hash-based estimate
    - estimated_units: position.value / unit_price
    - loss_factor: derived from alert drift + concentration scores
    - cost_basis_per_unit: unit_price * (1 + loss_factor)
    - unrealized_loss: estimated_units * (cost_basis_per_unit - unit_price)
    - tax_savings_estimate: unrealized_loss * 0.2 (20% capital gains rate proxy)
    - wash_sale_risk: True if position.weight > 0.15 (high concentration)
    """
    # Load all portfolios with positions
    portfolios = db.query(Portfolio).all()

    opportunities: List[TaxLossOpportunity] = []

    for portfolio in portfolios:
        # Get latest alert for this portfolio (for drift/concentration scores)
        latest_alert = (
            db.query(Alert)
            .filter(Alert.portfolio_id == portfolio.id)
            .order_by(Alert.created_at.desc())
            .first()
        )

        # Scan each position
        for position in portfolio.positions:
            # Estimate unit price
            unit_price = _estimate_unit_price(position.ticker, position.asset_class)

            # Estimate units (convert Decimal to float for calculation)
            estimated_units = float(position.value) / unit_price if unit_price > 0 else 0

            # Compute loss factor from alert scores
            if latest_alert:
                loss_factor = min(
                    0.25,
                    (latest_alert.drift_score + latest_alert.concentration_score) / 40.0
                )
            else:
                loss_factor = 0.05  # Baseline if no alert

            # Skip if loss factor too small
            if loss_factor < 0.03:
                continue

            # Estimate cost basis per unit
            cost_basis_per_unit = unit_price * (1 + loss_factor)

            # Calculate unrealized loss
            unrealized_loss = estimated_units * (cost_basis_per_unit - unit_price)

            # Tax savings (20% capital gains rate proxy)
            tax_savings_estimate = unrealized_loss * 0.2

            # Wash sale risk: high concentration = likely reacquired
            wash_sale_risk = position.weight > 0.15

            # Replacement ticker
            replacement_ticker = _estimate_replacement_ticker(position.asset_class)

            opportunity = TaxLossOpportunity(
                portfolio_id=portfolio.id,
                portfolio_name=portfolio.name,
                client_name=portfolio.client.name,
                client_id=portfolio.client_id,
                ticker=position.ticker,
                asset_class=position.asset_class,
                position_value=float(position.value),
                unrealized_loss=unrealized_loss,
                tax_savings_estimate=tax_savings_estimate,
                cost_basis_per_unit=cost_basis_per_unit,
                current_price=unit_price,
                estimated_units=estimated_units,
                wash_sale_risk=wash_sale_risk,
                replacement_ticker=replacement_ticker
            )
            opportunities.append(opportunity)

    # Sort by tax savings (descending) and take top 20
    opportunities.sort(key=lambda o: o.tax_savings_estimate, reverse=True)
    top_opportunities = opportunities[:20]

    # Compute aggregates
    total_harvestable_loss = sum(o.unrealized_loss for o in top_opportunities)
    total_tax_savings = sum(o.tax_savings_estimate for o in top_opportunities)
    portfolios_with_opportunities = len(
        set(o.portfolio_id for o in top_opportunities)
    )

    return TaxLossResponse(
        opportunities=top_opportunities,
        total_harvestable_loss=total_harvestable_loss,
        total_tax_savings=total_tax_savings,
        portfolios_with_opportunities=portfolios_with_opportunities
    )
