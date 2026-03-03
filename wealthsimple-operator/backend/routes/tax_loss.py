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
    Deterministic unit price estimation using weighted character hash.
    Returns realistic ETF price ranges per asset class.
    """
    seed = sum((i + 1) * ord(c) for i, c in enumerate(ticker)) % 100
    if asset_class == "Equity":
        return round(15.0 + (seed / 100.0) * 170.0, 2)  # $15–$185
    if asset_class == "Fixed Income":
        return round(10.0 + (seed / 100.0) * 95.0, 2)   # $10–$105
    return 1.0


# Ticker-keyed replacement map for wash sale alternatives
_REPLACEMENT_MAP: Dict[str, str] = {
    # Equity
    "XIT": "ZQQ", "XEG": "ZEO", "XFN": "ZEB", "VFV": "XEQT",
    "ZSP": "VFV", "VUN": "XAW", "XEF": "VIU", "ZEM": "XEC",
    "XEQT": "VEQT", "VEQT": "XEQT", "XIU": "XIC", "XIC": "XIU",
    "ZCN": "XIC", "HXT": "ZCN", "QQC": "ZQQ",
    # Fixed Income
    "XGB": "VAB", "VSB": "ZSB", "XBB": "VAB", "CLF": "XSB",
    "ZAG": "VAB", "VAB": "ZAG", "XSB": "VSB", "HBB": "ZAG",
    "SGOV": "CLF", "ZSB": "VSB",
}

_FALLBACK_REPLACEMENT: Dict[str, str] = {
    "Equity": "XEQT",
    "Fixed Income": "VAB",
    "Cash": "PSA",
}


def _estimate_replacement_ticker(ticker: str, asset_class: str) -> Optional[str]:
    """Suggest a replacement ETF keyed by specific ticker, with asset class fallback."""
    return _REPLACEMENT_MAP.get(ticker) or _FALLBACK_REPLACEMENT.get(asset_class)


def _marginal_tax_rate(segment: str) -> float:
    """
    Effective Canadian capital gains tax rate.
    Based on 50% inclusion rate × marginal income tax rate by wealth segment.
    """
    rates = {
        "UHNW": 0.2677,      # Ultra-high net worth
        "HNW": 0.2476,       # High net worth
        "Affluent": 0.2185,  # Affluent
    }
    return rates.get(segment, 0.1340)  # Default: conservative estimate


def _loss_reason(drift_score: float, concentration_score: float) -> str:
    """Determine loss context based on alert metrics."""
    if drift_score >= 5.0 and concentration_score >= 5.0:
        return "Sector concentration & rebalancing drag"
    if drift_score >= 5.0:
        return "Style/sector drift from benchmark"
    if concentration_score >= 5.0:
        return "Single-sector overweight impairment"
    return "Market volatility impact"


def _estimate_holding_period(ticker: str, portfolio_id: int) -> int:
    """Estimate holding period in days (deterministic, varies 180–900 days)."""
    seed = (sum(ord(c) for c in ticker) + portfolio_id * 7) % 100
    return 180 + int(seed / 100.0 * 720)


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

            # Tax savings (segment-adjusted capital gains rate)
            tax_rate = _marginal_tax_rate(portfolio.client.segment)
            tax_savings_estimate = unrealized_loss * tax_rate

            # Wash sale risk: high concentration = likely reacquired
            wash_sale_risk = position.weight > 0.15

            # Replacement ticker (ticker-specific lookup with fallback)
            replacement_ticker = _estimate_replacement_ticker(position.ticker, position.asset_class)

            # Loss reason (context from alert metrics)
            loss_reason = _loss_reason(
                latest_alert.drift_score if latest_alert else 0.0,
                latest_alert.concentration_score if latest_alert else 0.0
            )

            # Holding period (deterministic, ticker + portfolio dependent)
            holding_period_days = _estimate_holding_period(position.ticker, portfolio.id)

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
                replacement_ticker=replacement_ticker,
                loss_reason=loss_reason,
                holding_period_days=holding_period_days
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
