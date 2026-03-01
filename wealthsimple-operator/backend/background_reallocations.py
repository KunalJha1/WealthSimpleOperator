#!/usr/bin/env python
"""
Pre-generate unique AI-powered reallocation plan rationales for all alerts.

Generates diverse, AI-written justifications for each alert's reallocation strategy,
caching them for instant serving in the auto-reallocation UI.

Usage: python background_reallocations.py [--target-cash AMOUNT]
"""

from __future__ import annotations

import argparse
import json
import os
import random
import time
from pathlib import Path

try:
    from google import genai
    from google.genai import types
    from google.genai import errors as genai_errors

    _GEMINI_AVAILABLE = True
except ImportError:
    _GEMINI_AVAILABLE = False

from sqlalchemy.orm import Session, joinedload
from db import SessionLocal
from models import Alert, Portfolio

CACHE_FILE = Path(__file__).parent / ".reallocation_cache.json"


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


def _generate_ai_rationale(
    alert_id: int,
    client_name: str,
    portfolio_name: str,
    current_cash: float,
    target_cash: float,
    additional_needed: float,
    realized_gains: float,
    tax_impact: float,
    volatility_before: float,
    volatility_after: float,
    current_equity_pct: float,
    current_fixed_income_pct: float,
    current_cash_pct: float,
    target_equity_pct: float,
    target_fixed_income_pct: float,
    target_cash_pct: float,
) -> str:
    """Generate a unique, Gemini-powered AI rationale for the reallocation plan."""
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not _GEMINI_AVAILABLE or not api_key:
        return _fallback_rationale(
            additional_needed,
            target_cash,
            volatility_before,
            volatility_after,
            realized_gains,
            tax_impact,
        )

    prompt = f"""You are an AI financial advisor assistant. Generate a 2-3 sentence professional reallocation rationale.

Client Context:
- Name: {client_name}
- Portfolio: {portfolio_name}
- Risk Score: ELEVATED (drift detected)

Current Allocation:
- Equity: {current_equity_pct:.1f}% (target: {target_equity_pct:.1f}%)
- Fixed Income: {current_fixed_income_pct:.1f}% (target: {target_fixed_income_pct:.1f}%)
- Cash: {current_cash_pct:.1f}% (target: {target_cash_pct:.1f}%)

Reallocation Target:
- Current Cash: ${current_cash:,.0f}
- Target Cash: ${target_cash:,.0f}
- Additional Needed: ${additional_needed:,.0f}
- Realized Gains: ${realized_gains:,.0f}
- Estimated Tax Cost: ${tax_impact:,.0f}
- Volatility Reduction: {volatility_before:.2f}% → {volatility_after:.2f}%

Return ONLY plain text rationale (2-3 sentences). No JSON, no markdown. Focus on:
1. Why the current allocation is drifting from target
2. Tax-efficient approach to raise the needed cash
3. How this improves risk profile

Constraints:
- Do NOT suggest specific trades or target allocations beyond what's provided
- Do NOT use markdown or formatting
- Plain English, professional tone
- Advisor-facing language only
"""

    try:
        client = genai.Client(api_key=api_key)
        response = _simulate_with_retry(
            lambda: client.models.generate_content(
                model="gemini-2.5-flash-lite",
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.8),
            )
        )

        if response and response.text:
            rationale = response.text.strip()
            # Remove any leading/trailing markdown
            if rationale.startswith("```"):
                rationale = "\n".join(
                    line for line in rationale.splitlines()
                    if not line.strip().startswith("```")
                ).strip()
            if rationale:
                return rationale
    except Exception as e:
        print(f"      [Gemini error: {str(e)[:60]}... using fallback]")
        pass

    return _fallback_rationale(
        additional_needed,
        target_cash,
        volatility_before,
        volatility_after,
        realized_gains,
        tax_impact,
    )


def _fallback_rationale(
    additional_needed: float,
    target_cash: float,
    volatility_before: float,
    volatility_after: float,
    realized_gains: float,
    tax_impact: float,
) -> str:
    """Fallback rationale when Gemini is unavailable."""
    return (
        f"AI selected low-gain lots first to raise ${additional_needed:,.0f} for a down payment target of "
        f"${target_cash:,.0f}, while reducing volatility from {volatility_before:.2f}% to {volatility_after:.2f}%. "
        f"Projected taxable gains are ${realized_gains:,.0f} with estimated tax impact of ${tax_impact:,.0f}."
    )


def generate_all_rationales(target_cash_amount: float = 266000.0) -> dict:
    """Generate AI rationales for all alerts and cache them."""
    db: Session = SessionLocal()
    cache = {}

    try:
        alerts = (
            db.query(Alert)
            .options(
                joinedload(Alert.client),
                joinedload(Alert.portfolio).joinedload(Portfolio.positions),
            )
            .all()
        )

        total = len(alerts)
        print(f"Generating rationales for {total} alerts...\n")

        for idx, alert in enumerate(alerts, 1):
            cache_key = f"alert_{alert.id}"
            print(f"[{idx}/{total}] Alert {alert.id} ({alert.client.name})...", end=" ", flush=True)

            try:
                portfolio = alert.portfolio
                positions = portfolio.positions
                total_value = float(portfolio.total_value)

                # Calculate current allocation
                current_cash = sum(float(p.value) for p in positions if p.asset_class == "Cash")
                current_equity = sum(float(p.value) for p in positions if p.asset_class == "Equity")
                current_fixed_income = sum(
                    float(p.value) for p in positions if p.asset_class == "Fixed Income"
                )

                current_cash_pct = (current_cash / total_value * 100) if total_value else 0
                current_equity_pct = (current_equity / total_value * 100) if total_value else 0
                current_fixed_income_pct = (
                    (current_fixed_income / total_value * 100) if total_value else 0
                )

                target_equity_pct = float(portfolio.target_equity_pct)
                target_fixed_income_pct = float(portfolio.target_fixed_income_pct)
                target_cash_pct = float(portfolio.target_cash_pct)

                # Mock financial calculations (simplified from alerts.py)
                additional_cash_needed = max(0.0, target_cash_amount - current_cash)
                realized_gains = additional_cash_needed * random.uniform(0.05, 0.20)
                tax_impact = realized_gains * 0.50 * 0.38  # tax inclusion + marginal rate
                volatility_before = round(10.0 + random.uniform(0, 5), 2)
                volatility_after = round(volatility_before * 0.85, 2)

                rationale = _generate_ai_rationale(
                    alert_id=alert.id,
                    client_name=alert.client.name,
                    portfolio_name=portfolio.name,
                    current_cash=current_cash,
                    target_cash=target_cash_amount,
                    additional_needed=additional_cash_needed,
                    realized_gains=realized_gains,
                    tax_impact=tax_impact,
                    volatility_before=volatility_before,
                    volatility_after=volatility_after,
                    current_equity_pct=current_equity_pct,
                    current_fixed_income_pct=current_fixed_income_pct,
                    current_cash_pct=current_cash_pct,
                    target_equity_pct=target_equity_pct,
                    target_fixed_income_pct=target_fixed_income_pct,
                    target_cash_pct=target_cash_pct,
                )

                cache[cache_key] = rationale
                print("OK")

            except Exception as e:
                print(f"ERROR: {str(e)[:60]}")
                cache[cache_key] = None

        return cache

    finally:
        db.close()


def save_cache(cache: dict) -> None:
    """Save cache to JSON file."""
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2)
    print(f"\nCache saved to {CACHE_FILE}")


def load_cache() -> dict:
    """Load cache from JSON file."""
    if not CACHE_FILE.exists():
        return {}
    with open(CACHE_FILE, "r") as f:
        return json.load(f)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Pre-generate reallocation AI rationales for all alerts"
    )
    parser.add_argument(
        "--target-cash",
        type=float,
        default=266000.0,
        help="Target cash amount (default: 266000)",
    )
    args = parser.parse_args()

    print("=" * 70)
    print("Reallocation AI Rationale Pre-generation")
    print("=" * 70)

    cache = generate_all_rationales(target_cash_amount=args.target_cash)
    save_cache(cache)

    print("\nCache complete! Next steps:")
    print("1. Update routes/alerts.py to serve from cache")
    print("2. Rationales will be varied and AI-powered")
    print("3. Run this script again anytime you want fresh narratives")
