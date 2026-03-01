from __future__ import annotations

import json
import os
import random
import time
from collections import defaultdict
from typing import Dict, List, Set, Tuple

from sqlalchemy.orm import Session, joinedload

try:
    from google import genai
    from google.genai import types
    from google.genai import errors as genai_errors

    _GEMINI_AVAILABLE = True
except ImportError:
    _GEMINI_AVAILABLE = False

from models import (
    Client,
    ClientSummary,
    Portfolio,
    PortfolioSummary,
    SimulationPortfolioImpact,
    SimulationRequest,
    SimulationScenario,
    SimulationSeverity,
    SimulationSummary,
)
from operator_engine import _compute_metrics


# ============================================================================
# Gemini API helpers for direct scenario AI calls
# ============================================================================


def _simulate_with_retry(call_fn, max_retries=8):
    """Retry with exponential backoff and jitter (matches seed.py pattern)."""
    delay = 8.0
    for attempt in range(max_retries):
        try:
            return call_fn()
        except Exception as e:
            msg = str(e)
            if "429" in msg or "RESOURCE_EXHAUSTED" in msg or "503" in msg:
                jittered_delay = delay + random.random()
                time.sleep(jittered_delay)
                delay = min(delay * 2, 20)
                continue
            raise


def _fallback_summary() -> str:
    """Fallback AI summary when Gemini is unavailable."""
    return (
        "Scenario impact computed successfully, but the AI provider is currently "
        "unavailable to generate a narrative summary."
    )


def _fallback_checklist() -> list[str]:
    """Fallback checklist when Gemini is unavailable."""
    return [
        "Review the list of most exposed portfolios in the scenario lab UI.",
        "Confirm which clients have crossed internal risk or drift thresholds.",
        "Once the AI provider is healthy again, re-run this scenario for a richer narrative.",
    ]


def _generate_simulation_ai_summary(
    scenario_label: str,
    severity: str,
    avg_metrics: dict,
    total_portfolios: int,
    portfolios_off: int,
) -> tuple[str, list[str]]:
    """Call Gemini directly to generate scenario lab AI summary and checklist."""
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not _GEMINI_AVAILABLE or not api_key:
        return _fallback_summary(), _fallback_checklist()

    prompt = f"""You are an internal portfolio risk monitoring assistant.
A market scenario has just been simulated. Return ONLY strict JSON with exactly these two keys:
{{
  "summary": "<2-3 sentence plain English summary of the scenario impact>",
  "checklist": ["<action item 1>", "<action item 2>", "<action item 3>", "<action item 4>"]
}}

Scenario: {scenario_label}
Severity: {severity}
Portfolios analysed: {total_portfolios}
Portfolios pushed off trajectory: {portfolios_off}
Average post-scenario metrics (0-10 scale):
  Concentration: {avg_metrics.get('concentration_score', 0):.2f}
  Drift: {avg_metrics.get('drift_score', 0):.2f}
  Volatility: {avg_metrics.get('volatility_proxy', 0):.2f}
  Risk score: {avg_metrics.get('risk_score', 0):.2f}

Constraints:
- Do NOT suggest specific trades or target allocations.
- Checklist items must be advisor-facing operational actions.
- Plain English only, no markdown.
"""

    try:
        client = genai.Client(api_key=api_key)
        response = _simulate_with_retry(
            lambda: client.models.generate_content(
                model="gemini-2.5-flash-lite",
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.9),
            )
        )

        if not response or not response.text:
            raise ValueError("Empty response from Gemini")

        raw_text = response.text.strip()
        if raw_text.startswith("```"):
            raw_text = "\n".join(
                line for line in raw_text.splitlines()
                if not line.strip().startswith("```")
            ).strip()

        parsed = json.loads(raw_text)
        summary = str(parsed.get("summary", "")).strip()
        checklist = [str(x) for x in parsed.get("checklist", []) if x]
        if summary and checklist:
            return summary, checklist
    except Exception:
        pass

    return _fallback_summary(), _fallback_checklist()


_SEVERITY_MULTIPLIER: Dict[SimulationSeverity, float] = {
    SimulationSeverity.MILD: 0.6,
    SimulationSeverity.MODERATE: 1.0,
    SimulationSeverity.SEVERE: 1.6,
}


def _clamp_score(value: float, min_value: float = 0.0, max_value: float = 10.0) -> float:
    """Clamp a metric score into a safe band so pathological inputs do not explode."""
    if value < min_value:
        return min_value
    if value > max_value:
        return max_value
    return value


def _scenario_label(scenario: SimulationScenario) -> str:
    return {
        SimulationScenario.INTEREST_RATE_SHOCK: "Interest rate shock",
        SimulationScenario.BOND_SPREAD_WIDENING: "Bond spread widening",
        SimulationScenario.EQUITY_DRAWDOWN: "Equity drawdown",
        SimulationScenario.MULTI_ASSET_REGIME_CHANGE: "Multi-asset regime change",
    }[scenario]


def _asset_class_exposure(portfolio: Portfolio) -> Tuple[float, float, float]:
    equity_weight = 0.0
    fixed_income_weight = 0.0
    cash_weight = 0.0

    for position in portfolio.positions:
        weight = float(position.weight)
        asset_class = position.asset_class
        if asset_class in ("Equity", "ETF"):
            equity_weight += weight
        elif asset_class == "Fixed Income":
            fixed_income_weight += weight
        elif asset_class == "Cash":
            cash_weight += weight

    return equity_weight, fixed_income_weight, cash_weight


def _apply_scenario_to_metrics(
    metrics: Dict[str, float],
    portfolio: Portfolio,
    scenario: SimulationScenario,
    severity: SimulationSeverity,
) -> Dict[str, float]:
    equity_weight, fixed_income_weight, cash_weight = _asset_class_exposure(portfolio)
    multiplier = _SEVERITY_MULTIPLIER.get(severity, 1.0)

    # Clamp base metrics to a safe operating band so that any upstream
    # changes in the scoring engine cannot produce extreme values here.
    base_concentration = _clamp_score(float(metrics.get("concentration_score", 0.0)))
    base_drift = _clamp_score(float(metrics.get("drift_score", 0.0)))
    base_volatility = _clamp_score(float(metrics.get("volatility_proxy", 0.0)))
    base_risk = _clamp_score(float(metrics.get("risk_score", 0.0)))

    drift_delta = 0.0
    volatility_delta = 0.0
    risk_delta = 0.0

    if scenario is SimulationScenario.INTEREST_RATE_SHOCK:
        # Rate shocks primarily hit fixed income exposures and duration-heavy ladders.
        intensity = fixed_income_weight * 4.0 * multiplier
        drift_delta = intensity * 0.7
        volatility_delta = intensity * 0.4
        risk_delta = intensity
    elif scenario is SimulationScenario.BOND_SPREAD_WIDENING:
        # Credit stress is a bit more severe than a parallel rate move.
        intensity = fixed_income_weight * 5.0 * multiplier
        drift_delta = intensity * 0.8
        volatility_delta = intensity * 0.6
        risk_delta = intensity * 1.1
    elif scenario is SimulationScenario.EQUITY_DRAWDOWN:
        # Equity drawdowns hit growth/return assets.
        intensity = equity_weight * 4.0 * multiplier
        drift_delta = intensity * 0.5
        volatility_delta = intensity * 0.9
        risk_delta = intensity
    elif scenario is SimulationScenario.MULTI_ASSET_REGIME_CHANGE:
        # Combined move across risk factors.
        blended_exposure = equity_weight * 0.6 + fixed_income_weight * 0.6
        intensity = blended_exposure * 5.0 * multiplier
        drift_delta = intensity * 0.7
        volatility_delta = intensity * 0.8
        risk_delta = intensity * 1.1

    new_concentration = _clamp_score(base_concentration + risk_delta * 0.1)
    new_drift = _clamp_score(base_drift + drift_delta)
    new_volatility = _clamp_score(base_volatility + volatility_delta)
    new_risk = _clamp_score(base_risk + risk_delta)

    return {
        "concentration_score": new_concentration,
        "drift_score": new_drift,
        "volatility_proxy": new_volatility,
        "risk_score": new_risk,
    }


def run_scenario(
    db: Session,
    request: SimulationRequest,
) -> SimulationSummary:
    portfolios: List[Portfolio] = (
        db.query(Portfolio)
        .options(
            joinedload(Portfolio.client),
            joinedload(Portfolio.positions),
        )
        .all()
    )

    if not portfolios:
        return SimulationSummary(
            scenario=request.scenario,
            severity=request.severity,
            total_clients=0,
            total_portfolios=0,
            clients_off_trajectory=0,
            portfolios_off_trajectory=0,
            portfolios_on_track=0,
            ai_summary="No portfolios are available to simulate.",
            ai_checklist=[
                "Confirm that the monitoring universe is loaded before running simulations.",
                "Once data is available, re-run this scenario to understand which clients may be pushed off trajectory.",
            ],
            impacted_portfolios=[],
        )

    impacted: List[SimulationPortfolioImpact] = []
    client_ids_all: Set[int] = set()
    client_ids_off: Set[int] = set()

    sums_before: Dict[str, float] = defaultdict(float)
    sums_after: Dict[str, float] = defaultdict(float)

    for portfolio in portfolios:
        client: Client = portfolio.client
        client_ids_all.add(client.id)

        metrics = _compute_metrics(portfolio)
        scenario_metrics = _apply_scenario_to_metrics(
            metrics=metrics,
            portfolio=portfolio,
            scenario=request.scenario,
            severity=request.severity,
        )

        for key in ("concentration_score", "drift_score", "volatility_proxy", "risk_score"):
            sums_before[key] += float(metrics.get(key, 0.0))
            sums_after[key] += float(scenario_metrics.get(key, 0.0))

        risk_before = float(metrics.get("risk_score", 0.0))
        risk_after = float(scenario_metrics.get("risk_score", 0.0))
        delta_risk = risk_after - risk_before

        off_trajectory = risk_after >= 7.0 or delta_risk >= 2.5
        if off_trajectory:
            client_ids_off.add(client.id)

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

        impacted.append(
            SimulationPortfolioImpact(
                client=client_summary,
                portfolio=portfolio_summary,
                risk_before=risk_before,
                risk_after=risk_after,
                delta_risk=delta_risk,
                off_trajectory=off_trajectory,
            )
        )

    # Sort by portfolios most negatively impacted.
    impacted.sort(key=lambda i: (not i.off_trajectory, -i.delta_risk, -i.risk_after))

    total_portfolios = len(portfolios)
    total_clients = len(client_ids_all)
    portfolios_off = sum(1 for i in impacted if i.off_trajectory)
    portfolios_on_track = total_portfolios - portfolios_off
    clients_off = len(client_ids_off)

    n = float(total_portfolios) or 1.0
    avg_before = {
        key: value / n for key, value in sums_before.items()
    }
    avg_after = {
        key: value / n for key, value in sums_after.items()
    }

    # Generate AI summary using direct Gemini call (bypass broken provider)
    ai_summary, ai_checklist = _generate_simulation_ai_summary(
        scenario_label=_scenario_label(request.scenario),
        severity=request.severity.value,
        avg_metrics=avg_after,
        total_portfolios=total_portfolios,
        portfolios_off=portfolios_off,
    )

    return SimulationSummary(
        scenario=request.scenario,
        severity=request.severity,
        total_clients=total_clients,
        total_portfolios=total_portfolios,
        clients_off_trajectory=clients_off,
        portfolios_off_trajectory=portfolios_off,
        portfolios_on_track=portfolios_on_track,
        ai_summary=ai_summary,
        ai_checklist=ai_checklist,
        impacted_portfolios=impacted,
    )

