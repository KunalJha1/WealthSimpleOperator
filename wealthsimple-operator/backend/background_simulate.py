#!/usr/bin/env python
"""
Pre-generate and cache all scenario/severity simulation combinations.

Runs all 12 simulations (4 scenarios × 3 severities) and caches results in
a JSON file for instant serving in the UI (no on-demand Gemini calls).

Usage: python background_simulate.py
"""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy.orm import Session

from db import SessionLocal
from models import SimulationRequest, SimulationScenario, SimulationSeverity
from simulation_engine import run_scenario


SCENARIOS = [
    SimulationScenario.INTEREST_RATE_SHOCK,
    SimulationScenario.BOND_SPREAD_WIDENING,
    SimulationScenario.EQUITY_DRAWDOWN,
    SimulationScenario.MULTI_ASSET_REGIME_CHANGE,
]

SEVERITIES = [
    SimulationSeverity.MILD,
    SimulationSeverity.MODERATE,
    SimulationSeverity.SEVERE,
]

CACHE_FILE = Path(__file__).parent / ".simulation_cache.json"


def run_all_simulations() -> dict:
    """Generate all 12 scenario/severity combinations and return cached dict."""
    cache = {}

    total = len(SCENARIOS) * len(SEVERITIES)
    count = 0

    for scenario in SCENARIOS:
        for severity in SEVERITIES:
            count += 1
            scenario_name = scenario.value
            severity_name = severity.value
            cache_key = f"{scenario_name}_{severity_name}"

            print(
                f"[{count}/{total}] Generating {scenario_name} ({severity_name})...",
                end=" ",
                flush=True,
            )

            # Create fresh session for each simulation to avoid SQLAlchemy caching issues
            db: Session = SessionLocal()
            try:
                request = SimulationRequest(
                    scenario=scenario,
                    severity=severity,
                )
                result = run_scenario(db=db, request=request)
                cache[cache_key] = result.model_dump()
                print("OK")
            except Exception as e:
                print(f"ERROR: {e}")
                cache[cache_key] = None
            finally:
                db.close()

    return cache


def save_cache(cache: dict) -> None:
    """Save cache to JSON file."""
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2, default=str)
    print(f"\nCache saved to {CACHE_FILE}")


def load_cache() -> dict:
    """Load cache from JSON file."""
    if not CACHE_FILE.exists():
        return {}
    with open(CACHE_FILE, "r") as f:
        return json.load(f)


if __name__ == "__main__":
    print("Pre-generating all scenario/severity simulations...")
    print(f"Total combinations: {len(SCENARIOS) * len(SEVERITIES)}\n")

    cache = run_all_simulations()
    save_cache(cache)

    print("\nCache complete! Next steps:")
    print("1. Update routes/simulations.py to serve from cache")
    print("2. Or add a /simulations/cached endpoint")
