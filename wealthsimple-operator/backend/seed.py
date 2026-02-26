from __future__ import annotations

import json
import os
import random
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Tuple

from sqlalchemy.orm import Session

from db import Base, SessionLocal, engine
from models import Client, Portfolio, Position, MeetingNote, MeetingNoteType
from ai.mock_provider import MockAIProvider


FIRST_NAMES = [
    # Existing names
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
    # Additional variety
    "Hassan",
    "Fatima",
    "Diego",
    "Lucia",
    "Anika",
    "Vikram",
    "Yara",
    "Hugo",
    "Jasper",
    "Elena",
    "Noor",
    "Silas",
    "Mina",
    "Ada",
    "Nikhil",
    "Bao",
    "Hana",
    "Jonah",
    "Amina",
    "Reese",
    "Imani",
    "Marcos",
    "Clara",
    "Santiago",
    "Leila",
    "Arthur",
    "Mariam",
    "Sven",
    "Greta",
    "Nikola",
    "Elijah",
    "Naomi",
    "Khalil",
    "Rafa",
]

LAST_NAMES = [
    # Existing names
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
    # Additional variety
    "Rodriguez",
    "Das",
    "Silva",
    "Kaur",
    "Romero",
    "Kowalski",
    "Fischer",
    "Costa",
    "Osei",
    "Hassan",
    "Yamamoto",
    "Sato",
    "Moretti",
    "Novak",
    "Ibrahim",
    "Mendes",
    "Schneider",
    "Johansson",
    "Petrov",
    "Smirnov",
    "Okafor",
    "Mahajan",
    "Fernandes",
    "Kumar",
    "Gupta",
    "Sun",
    "Zhang",
    "Fraser",
    "O'Connor",
    "Gallagher",
    "Ahmed",
    "Hussein",
]

SEGMENTS = ["Mass", "Premium", "HNW"]
RISK_PROFILES = ["Conservative", "Balanced", "Growth"]
ACCOUNT_TIERS = ["Core", "Premium", "Generation"]

# Product-style portfolio names to mirror Wealth offerings
PORTFOLIO_PRODUCT_NAMES = [
    "Summit",
    "Classic",
    "Direct Indexing",
    "Income",
]

TICKERS_BY_ASSET_CLASS = {
    "Equity": ["WS-CA-EQ1", "WS-CA-EQ2", "WS-US-EQ1", "WS-INTL-EQ1"],
    "Fixed Income": ["WS-CA-BD1", "WS-CA-BD2", "WS-IG-BD1"],
    "ETF": ["WS-ETF-ALL", "WS-ETF-EQ", "WS-ETF-BAL"],
    "Cash": ["CASH-CA"],
}


def reset_database() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def _account_tier_for_aum(aum: float) -> str:
    """Assign account tier based on AUM.

    Core: $1 - $100k
    Premium: $100k - $500k
    Generation: $500k+
    """
    if aum < 100_000:
        return "Core"
    elif aum < 500_000:
        return "Premium"
    else:
        return "Generation"


def generate_clients_and_portfolios(session: Session, count: int = 70) -> None:
    random.seed(42)
    full_names = _generate_unique_names(count)
    now = datetime.utcnow()

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
            account_tier="Core",  # Will be updated after portfolio creation
            created_at=now - timedelta(days=random.randint(30, 365 * 8)),
        )
        session.add(client)
        session.flush()

        # Cycle through branded portfolio types so the UI reflects real offerings
        product_name = PORTFOLIO_PRODUCT_NAMES[i % len(PORTFOLIO_PRODUCT_NAMES)]
        portfolio_name = product_name
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

        # Assign account tier based on portfolio AUM
        client.account_tier = _account_tier_for_aum(float(total_value))

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


def seed_meeting_notes(session: Session) -> None:
    """Seed realistic meeting notes with call transcripts for first 30 clients.

    Each client gets 3 notes:
    1. Q4 Portfolio Review (meeting type, no transcript)
    2. Annual Planning Meeting (review type, no transcript)
    3. Client Check-in Call (phone_call type, with transcript and AI summary)
    """
    ai_provider = MockAIProvider()
    now = datetime.utcnow()

    # Query first 30 clients
    clients: List[Client] = session.query(Client).limit(30).all()

    # Three transcript templates parameterized by client data
    transcript_templates = [
        # Template A: RRSP/retirement focus
        lambda name, risk_profile: (
            f"Advisor: Hi {name}, thanks for taking the time to meet with me today. "
            f"I wanted to check in on your RRSP contribution room and discuss your retirement timeline. "
            f"Client: Absolutely, I've been meaning to do this. I know I have some room left for this year. "
            f"Advisor: Great. We should maximize that before year-end for the tax deduction. "
            f"I also want to review your retirement target and make sure we're on track. "
            f"Client: My goal is to retire in about 15 years. With my current savings rate, I think we're doing okay. "
            f"Advisor: Let's run the numbers. I'll send you a retirement projection and we can schedule a follow-up. "
            f"Also, have you thought about estate planning? Given your risk profile of {risk_profile}, "
            f"I think it's important to have clarity on beneficiaries and a will in place. "
            f"Client: I haven't, but I know I should. Can you refer me to someone? "
            f"Advisor: Of course. I'll set you up with an estate planning specialist we work with."
        ),
        # Template B: Market volatility and purchase timing
        lambda name, risk_profile: (
            f"Advisor: {name}, with recent market volatility, I wanted to touch base. "
            f"How are you feeling about the portfolio, given your {risk_profile} risk tolerance? "
            f"Client: I'm a bit concerned about the recent swings. I wasn't expecting things to move this fast. "
            f"Advisor: That's completely normal. Your allocation is designed to handle this. "
            f"Tell me, do you still have any major purchases planned in the next few years? "
            f"Client: Actually, we're thinking about buying a home in the next 18-24 months. "
            f"Advisor: Excellent—that's important to know. We need to look at liquidity and whether we should adjust "
            f"the portfolio to reduce risk on the funds earmarked for the purchase. "
            f"Let me send you an account statement and we can discuss at our next meeting. "
            f"Client: That would be helpful. When can we schedule? "
            f"Advisor: Let me check my calendar and send you a few options."
        ),
        # Template C: Annual review and beneficiary check
        lambda name, risk_profile: (
            f"Advisor: Welcome back, {name}. This is our annual portfolio review. "
            f"Overall, the portfolio has performed well given the {risk_profile} allocation. "
            f"Client: That's good to hear. How are we doing relative to my goals? "
            f"Advisor: You're ahead of schedule on your retirement goal, and your current withdrawals "
            f"remain sustainable. I want to cover a few housekeeping items today. "
            f"First, let's confirm your beneficiary designations are still current. "
            f"Client: I haven't updated them in a few years. My circumstances have changed. "
            f"Advisor: We should review that today, then. Also, I'll send you a tax summary for year-end planning. "
            f"And I'd like to schedule a follow-up in 30 days to go over any questions you have. "
            f"Client: Sounds good. I appreciate the thoroughness."
        ),
    ]

    for idx, client in enumerate(clients):
        base_date = now - timedelta(days=30 + (client.id % 60))

        # Note 1: Q4 Portfolio Review (meeting, no transcript)
        note1 = MeetingNote(
            client_id=client.id,
            title="Q4 Portfolio Review",
            meeting_date=base_date,
            note_body=(
                "Client reported satisfaction with performance. Discussed major planned purchase "
                "and the need for liquidity planning. Client requested a gradual risk reduction "
                "ahead of expected withdrawals."
            ),
            meeting_type=MeetingNoteType.MEETING,
            call_transcript=None,
            ai_summary=None,
            ai_action_items=None,
            ai_summarized_at=None,
            ai_provider_used=None,
        )
        session.add(note1)

        # Note 2: Annual Planning Meeting (review, no transcript)
        note2 = MeetingNote(
            client_id=client.id,
            title="Annual Planning Meeting",
            meeting_date=base_date - timedelta(days=43),
            note_body=(
                "Reviewed goals, confirmed risk tolerance, and validated beneficiary/estate details. "
                "Retirement target remains on track with periodic monitoring."
            ),
            meeting_type=MeetingNoteType.REVIEW,
            call_transcript=None,
            ai_summary=None,
            ai_action_items=None,
            ai_summarized_at=None,
            ai_provider_used=None,
        )
        session.add(note2)

        # Note 3: Client Check-in Call (phone_call, with transcript and AI summary)
        template_idx = idx % len(transcript_templates)
        transcript = transcript_templates[template_idx](client.name, client.risk_profile)

        # Use mock provider to summarize the transcript
        summary_result = ai_provider.summarize_transcript(
            transcript=transcript,
            context={
                "client_name": client.name,
                "risk_profile": client.risk_profile,
            }
        )

        note3 = MeetingNote(
            client_id=client.id,
            title="Client Check-in Call",
            meeting_date=base_date - timedelta(days=75),
            note_body="Phone call with client to review recent portfolio performance and discuss upcoming goals.",
            meeting_type=MeetingNoteType.PHONE_CALL,
            call_transcript=transcript,
            ai_summary=summary_result.summary_paragraph,
            ai_action_items=summary_result.action_items,
            ai_summarized_at=datetime.utcnow(),
            ai_provider_used="mock",
        )
        session.add(note3)


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
        # Seed a larger monitoring universe so the operator dashboard
        # reflects hundreds of portfolios instead of just a small demo set.
        generate_clients_and_portfolios(session, count=1260)
        session.commit()

        # Seed meeting notes with transcripts for first 30 clients
        seed_meeting_notes(session)
        session.commit()

        export_seed_snapshot(session)
    finally:
        session.close()


if __name__ == "__main__":
    main()

