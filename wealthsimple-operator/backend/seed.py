from __future__ import annotations

import json
import os
import random
from decimal import Decimal
from typing import List, Tuple

from sqlalchemy.orm import Session

from db import Base, SessionLocal, engine
from models import Client, Portfolio, Position


FIRST_NAMES = [
    "Alex",
    "Amelia",
    "Aria",
    "Benjamin",
    "Jordan",
    "Noah",
    "Liam",
    "Taylor",
    "Priya",
    "Maya",
    "Morgan",
    "Ethan",
    "Olivia",
    "Casey",
    "Sofia",
    "Emma",
    "Riley",
    "Lucas",
    "Aiden",
    "Avery",
    "Harper",
    "Nora",
    "Quinn",
    "Mateo",
    "Isla",
    "Jamie",
    "Leo",
    "Mila",
    "Cameron",
    "Kai",
    "Zoe",
    "Aisha",
    "Rohan",
    "Daniel",
    "Samira",
    "Chloe",
    "Owen",
    "Ruby",
    "Gabriel",
    "Layla",
    "Ivy",
    "Elias",
]

LAST_NAMES = [
    "Lee",
    "Patel",
    "Nguyen",
    "Garcia",
    "Kim",
    "Singh",
    "Martinez",
    "Brown",
    "Wilson",
    "Dubois",
    "Chen",
    "Khan",
    "Wong",
    "Ali",
    "Morales",
    "Lopez",
    "White",
    "Clark",
    "Young",
    "Rivera",
    "Wright",
    "Scott",
    "Hall",
    "Adams",
    "Baker",
    "Gonzalez",
    "Hernandez",
    "Campbell",
    "Reed",
    "Carter",
]

SEGMENTS = ["Mass", "Premium", "HNW"]
RISK_PROFILES = ["Conservative", "Balanced", "Growth"]

TICKERS_BY_ASSET_CLASS = {
    "Equity": ["WS-CA-EQ1", "WS-CA-EQ2", "WS-US-EQ1", "WS-INTL-EQ1"],
    "Fixed Income": ["WS-CA-BD1", "WS-CA-BD2", "WS-IG-BD1"],
    "ETF": ["WS-ETF-ALL", "WS-ETF-EQ", "WS-ETF-BAL"],
    "Cash": ["CASH-CA"],
}


def reset_database() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def generate_clients_and_portfolios(session: Session, count: int = 70) -> None:
    random.seed(42)
    full_names = _generate_unique_names(count)

    for i in range(count):
        name = full_names[i]
        first, last = name.split(" ", 1)
        email = f"{first.lower()}.{last.lower()}{i}@example.internal"
        segment = random.choice(SEGMENTS)
        risk_profile = random.choice(RISK_PROFILES)

        client = Client(
            name=name,
            email=email,
            segment=segment,
            risk_profile=risk_profile,
        )
        session.add(client)
        session.flush()

        portfolio_name = f"{segment} Portfolio {i + 1}"
        total_value = Decimal(random.randint(50_000, 2_000_000))

        target_equity, target_fixed_income, target_cash = _target_allocations_for_profile(
            risk_profile
        )

        portfolio = Portfolio(
            client_id=client.id,
            name=portfolio_name,
            total_value=total_value,
            target_equity_pct=target_equity,
            target_fixed_income_pct=target_fixed_income,
            target_cash_pct=target_cash,
        )
        session.add(portfolio)
        session.flush()

        _create_positions_for_portfolio(session, portfolio, total_value)


def _generate_unique_names(count: int) -> List[str]:
    """Build unique full names so seeded clients do not look repetitive."""
    all_combinations = [f"{first} {last}" for first in FIRST_NAMES for last in LAST_NAMES]
    if count > len(all_combinations):
        raise ValueError(
            f"Requested {count} clients but only {len(all_combinations)} unique names available."
        )

    random.shuffle(all_combinations)
    return all_combinations[:count]


def _target_allocations_for_profile(profile: str) -> Tuple[float, float, float]:
    if profile == "Conservative":
        return 40.0, 50.0, 10.0
    if profile == "Balanced":
        return 60.0, 30.0, 10.0
    # Growth and others
    return 80.0, 15.0, 5.0


def _create_positions_for_portfolio(
    session: Session,
    portfolio: Portfolio,
    total_value: Decimal,
) -> None:
    min_positions = 5
    max_positions = 12
    num_positions = random.randint(min_positions, max_positions)

    # Generate raw weights and normalize to 1.0
    raw_weights = [random.random() for _ in range(num_positions)]
    total_raw = sum(raw_weights)
    weights = [w / total_raw for w in raw_weights]

    asset_classes = list(TICKERS_BY_ASSET_CLASS.keys())

    for weight in weights:
        asset_class = random.choice(asset_classes)
        tickers = TICKERS_BY_ASSET_CLASS[asset_class]
        ticker = random.choice(tickers)

        value = total_value * Decimal(weight)

        position = Position(
            portfolio_id=portfolio.id,
            ticker=ticker,
            asset_class=asset_class,
            weight=float(weight),
            value=value,
        )
        session.add(position)


def export_seed_snapshot(session: Session) -> None:
    clients: List[Client] = session.query(Client).all()
    portfolios: List[Portfolio] = session.query(Portfolio).all()
    positions: List[Position] = session.query(Position).all()

    data = {
        "clients": [
            {
                "id": c.id,
                "name": c.name,
                "email": c.email,
                "segment": c.segment,
                "risk_profile": c.risk_profile,
            }
            for c in clients
        ],
        "portfolios": [
            {
                "id": p.id,
                "client_id": p.client_id,
                "name": p.name,
                "total_value": float(p.total_value),
                "target_equity_pct": float(p.target_equity_pct),
                "target_fixed_income_pct": float(p.target_fixed_income_pct),
                "target_cash_pct": float(p.target_cash_pct),
            }
            for p in portfolios
        ],
        "positions": [
            {
                "id": pos.id,
                "portfolio_id": pos.portfolio_id,
                "ticker": pos.ticker,
                "asset_class": pos.asset_class,
                "weight": pos.weight,
                "value": float(pos.value),
            }
            for pos in positions
        ],
    }

    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(root_dir, "data")
    os.makedirs(data_dir, exist_ok=True)
    output_path = os.path.join(data_dir, "seed_output.json")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def main() -> None:
    reset_database()
    session = SessionLocal()
    try:
        generate_clients_and_portfolios(session, count=70)
        session.commit()
        export_seed_snapshot(session)
    finally:
        session.close()


if __name__ == "__main__":
    main()

