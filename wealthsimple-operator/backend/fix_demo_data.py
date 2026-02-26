from __future__ import annotations

import argparse
import json
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import func
from sqlalchemy import text

from ai.provider import get_provider
from db import SessionLocal
from db_utils import run_with_retry
from generate_client_insights import generate_client_insights
from models import Alert, Client, Portfolio, Run
from operator_engine import run_operator
from seed import main as seed_main


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Repair demo data for Monitoring Universe metrics. "
            "Seeds baseline data only when required, then creates operator runs."
        )
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=3,
        help="How many operator runs to create for alert history.",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Force full reseed before creating runs (drops existing DB data).",
    )
    parser.add_argument(
        "--insights-limit",
        type=int,
        default=200,
        help="How many rows to write to data/client_insights.json.",
    )
    parser.add_argument(
        "--skip-insights",
        action="store_true",
        help="Skip writing data/client_insights.json.",
    )
    return parser.parse_args()


def _counts() -> dict[str, int]:
    with SessionLocal() as db:
        return {
            "clients": int(db.query(func.count(Client.id)).scalar() or 0),
            "portfolios": int(db.query(func.count(Portfolio.id)).scalar() or 0),
            "runs": int(db.query(func.count(Run.id)).scalar() or 0),
            "alerts": int(db.query(func.count(Alert.id)).scalar() or 0),
        }


def _has_required_schema() -> bool:
    """Return True if required columns for current models exist."""
    with SessionLocal() as db:
        cols = db.execute(text("PRAGMA table_info(clients)")).fetchall()
    col_names = {str(row[1]) for row in cols}
    return "account_tier" in col_names


def _write_insights(limit: int) -> int:
    insights = generate_client_insights(limit=limit)
    root = Path(__file__).resolve().parent.parent
    out_path = root / "data" / "client_insights.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(insights, indent=2), encoding="utf-8")
    return len(insights)


def _run_once(provider_name):
    with SessionLocal() as db:
        return run_operator(db=db, provider=provider_name, actor="demo_fix_script")


def main() -> None:
    args = parse_args()
    if args.runs < 0:
        raise ValueError("--runs must be >= 0")
    if args.insights_limit <= 0:
        raise ValueError("--insights-limit must be >= 1")

    # Respect backend/.env provider settings.
    load_dotenv(dotenv_path=Path(__file__).with_name(".env"), override=True)

    before = _counts()
    print(f"Before: {before}")

    schema_ok = _has_required_schema()
    if not schema_ok:
        print("Detected outdated DB schema (missing clients.account_tier).")

    must_seed = (
        args.reset
        or before["clients"] == 0
        or before["portfolios"] == 0
        or not schema_ok
    )
    if must_seed:
        if args.reset:
            reason = "--reset requested"
        elif not schema_ok:
            reason = "outdated schema"
        else:
            reason = "missing clients/portfolios"
        print(f"Seeding database ({reason})...")
        seed_main()
        before = _counts()
        print(f"After seed: {before}")

    provider = get_provider()
    print(f"Provider: {provider.name}")

    for i in range(args.runs):
        summary = run_with_retry(lambda: _run_once(provider))
        print(
            f"Run {i + 1}/{args.runs}: run_id={summary.run_id}, alerts={summary.created_alerts_count}"
        )

    if not args.skip_insights:
        count = run_with_retry(lambda: _write_insights(limit=args.insights_limit))
        print(f"Wrote data/client_insights.json with {count} rows.")

    after = _counts()
    print(f"After: {after}")
    print("Done. Reload /monitoring-universe.")


if __name__ == "__main__":
    main()
