from __future__ import annotations

import argparse
import json
import logging
import os
import random
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

# Configure logging to show operator progress
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S%z",
)

# Suppress verbose library logs
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("google_genai").setLevel(logging.WARNING)
logging.getLogger("google.genai").setLevel(logging.WARNING)

from ai.provider import get_provider
from db import SessionLocal
from db_utils import run_with_retry
from generate_client_insights import generate_client_insights
from operator_engine import run_operator
from seed import main as seed_main


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run operator scans in a loop to backfill realistic alert history and refresh client insights."
        )
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=0,
        help="Number of cycles to run. Use 0 for infinite background mode.",
    )
    parser.add_argument(
        "--interval-seconds",
        type=float,
        default=120.0,
        help="Seconds to sleep between cycles.",
    )
    parser.add_argument(
        "--jitter-seconds",
        type=float,
        default=0.0,
        help="Random jitter added/subtracted from interval to vary run timing.",
    )
    parser.add_argument(
        "--insights-every",
        type=int,
        default=1,
        help="Regenerate data/client_insights.json every N cycles.",
    )
    parser.add_argument(
        "--insights-limit",
        type=int,
        default=50,
        help="How many portfolios to include in client_insights.json.",
    )
    parser.add_argument(
        "--seed-first",
        action="store_true",
        help="Reset and reseed database before starting the loop.",
    )
    parser.add_argument(
        "--actor",
        type=str,
        default="background_backfill",
        help="Audit actor label for generated runs.",
    )
    parser.add_argument(
        "--unique-summaries",
        action="store_true",
        help="Generate richer, more detailed and unique summaries (higher Gemini temperature, more detailed prompt).",
    )
    return parser.parse_args()


def write_insights(limit: int) -> int:
    insights = generate_client_insights(limit=limit)
    root = Path(__file__).resolve().parent.parent
    data_dir = root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    out_path = data_dir / "client_insights.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(insights, f, indent=2)
    return len(insights)


def main() -> None:
    args = parse_args()

    if args.interval_seconds < 0:
        raise ValueError("--interval-seconds must be >= 0")
    if args.jitter_seconds < 0:
        raise ValueError("--jitter-seconds must be >= 0")
    if args.insights_every <= 0:
        raise ValueError("--insights-every must be >= 1")
    if args.insights_limit <= 0:
        raise ValueError("--insights-limit must be >= 1")

    # Load backend/.env so PROVIDER/GEMINI_API_KEY are respected.
    env_path = Path(__file__).with_name(".env")
    load_dotenv(dotenv_path=env_path, override=True)
    
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    PROVIDER = os.getenv("PROVIDER")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL")
    print(f"{GEMINI_API_KEY}, {PROVIDER}, {GEMINI_MODEL}")
    print(f"[{_ts()}] ENV PATH: {env_path} | exists: {env_path.exists()}")

    if args.seed_first:
        print(f"[{_ts()}] Resetting and reseeding database...")
        seed_main()
        print(f"[{_ts()}] Seed completed.")

    provider = get_provider()
    print(
        f"[{_ts()}] Starting background backfill | provider={provider.name} | "
        f"runs={'infinite' if args.runs == 0 else args.runs} | interval={args.interval_seconds}s"
    )

    cycle = 0
    try:
        while args.runs == 0 or cycle < args.runs:
            cycle += 1
            cycle_started = time.perf_counter()
            print(f"[{_ts()}] cycle={cycle} started", flush=True)

            operator_started = time.perf_counter()
            print(f"[{_ts()}] cycle={cycle} running operator scan...", flush=True)

            def _run_operator_scan():
                with SessionLocal() as db:
                    return run_operator(db=db, provider=provider, actor=args.actor, unique_summaries=args.unique_summaries)

            summary = run_with_retry(_run_operator_scan)
            operator_elapsed = time.perf_counter() - operator_started

            print(
                f"[{_ts()}] cycle={cycle} run_id={summary.run_id} "
                f"alerts={summary.created_alerts_count} provider={summary.provider_used} "
                f"operator_elapsed={operator_elapsed:.1f}s",
                flush=True,
            )

            if cycle % args.insights_every == 0:
                insights_started = time.perf_counter()
                print(f"[{_ts()}] cycle={cycle} generating client_insights.json...", flush=True)
                count = run_with_retry(lambda: write_insights(limit=args.insights_limit))
                insights_elapsed = time.perf_counter() - insights_started
                print(
                    f"[{_ts()}] cycle={cycle} wrote client_insights.json "
                    f"({count} rows) insights_elapsed={insights_elapsed:.1f}s",
                    flush=True,
                )

            if args.runs != 0 and cycle >= args.runs:
                break

            cycle_elapsed = time.perf_counter() - cycle_started
            print(f"[{_ts()}] cycle={cycle} completed in {cycle_elapsed:.1f}s", flush=True)

            sleep_seconds = args.interval_seconds
            if args.jitter_seconds > 0:
                sleep_seconds += random.uniform(-args.jitter_seconds, args.jitter_seconds)
                sleep_seconds = max(0.0, sleep_seconds)

            if sleep_seconds > 0:
                print(f"[{_ts()}] sleeping for {sleep_seconds:.1f}s", flush=True)
                time.sleep(sleep_seconds)

        print(f"[{_ts()}] Backfill loop completed after {cycle} cycles.")
    except KeyboardInterrupt:
        print(f"[{_ts()}] Stopped by user after {cycle} cycles.")


if __name__ == "__main__":
    main()
