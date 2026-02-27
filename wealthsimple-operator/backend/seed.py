from __future__ import annotations

import json
import os
import random
import time
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Tuple
from pathlib import Path

from sqlalchemy.orm import Session
from dotenv import load_dotenv

from db import Base, SessionLocal, engine
from models import Client, Portfolio, Position, MeetingNote, MeetingNoteType, Alert, AlertStatus, Run, AuditEvent, AuditEventType, Priority
from ai.mock_provider import MockAIProvider

# Try to import Gemini for meeting note generation
try:
    from google import genai
    from google.genai import types
    from google.genai import errors as genai_errors
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

# Load .env
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env", override=True)


def generate_with_retry(call_fn, max_retries=8):
    """Retry with exponential backoff and jitter (from build_ai_summary.py pattern)."""
    delay = 8.0
    for attempt in range(max_retries):
        try:
            return call_fn()
        except genai_errors.ClientError as e:
            msg = str(e)
            print(f"   [Attempt {attempt + 1}/{max_retries}] Error: {msg[:80]}")
            if "429" in msg or "RESOURCE_EXHAUSTED" in msg or "503" in msg:
                jittered_delay = delay + random.random()
                print(f"   Rate limited/Overloaded. Retrying in {jittered_delay:.1f}s...")
                time.sleep(jittered_delay)
                delay = min(delay * 2, 20)
                continue
            raise


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
    "Custom",
]

TICKERS_BY_ASSET_CLASS = {
    "Equity": ["WS-CA-EQ1", "WS-CA-EQ2", "WS-US-EQ1", "WS-INTL-EQ1"],
    "Fixed Income": ["WS-CA-BD1", "WS-CA-BD2", "WS-IG-BD1"],
    "ETF": ["WS-ETF-ALL", "WS-ETF-EQ", "WS-ETF-BAL"],
    "Cash": ["CASH-CA"],
}

# Scenario definitions for rich, personalized meeting notes
SCENARIOS = [
    {
        "key": "EDUCATION_WITHDRAWAL",
        "label": "Education Withdrawal",
        "description": "Child starting school soon, RESP withdrawal imminent",
    },
    {
        "key": "TAX_LOSS_HARVESTING",
        "label": "Tax Loss Harvesting",
        "description": "End of year, losses in position, client wants to offset gains",
    },
    {
        "key": "HOME_PURCHASE",
        "label": "Home Purchase",
        "description": "Client buying a home in 12-18 months, needs liquidity",
    },
    {
        "key": "RETIREMENT_DRAWDOWN",
        "label": "Retirement Drawdown",
        "description": "Client just retired, switching from accumulation to drawdown",
    },
    {
        "key": "INHERITANCE_WINDFALL",
        "label": "Inheritance Windfall",
        "description": "Client received large inheritance, needs rebalancing",
    },
    {
        "key": "MAJOR_LIFE_EVENT",
        "label": "Major Life Event",
        "description": "Divorce/job loss, risk tolerance has changed",
    },
    {
        "key": "ESTATE_PLANNING",
        "label": "Estate Planning",
        "description": "Aging client, beneficiary/will update needed",
    },
    {
        "key": "RRSP_DEADLINE",
        "label": "RRSP Deadline",
        "description": "Contribution deadline approaching, room available",
    },
    {
        "key": "BUSINESS_SALE",
        "label": "Business Sale",
        "description": "Client sold business, large lump sum needs deployment strategy",
    },
    {
        "key": "MATERNITY_LEAVE",
        "label": "Maternity Leave",
        "description": "Client going on parental leave, income reduction ahead",
    },
    {
        "key": "FOREIGN_PROPERTY",
        "label": "Foreign Property",
        "description": "Client buying property abroad, needs USD/FX conversion timing",
    },
    {
        "key": "CHARITABLE_GIVING",
        "label": "Charitable Giving",
        "description": "Client wants to donate appreciated securities before year-end",
    },
    {
        "key": "MARGIN_CALL_RISK",
        "label": "Margin Call Risk",
        "description": "Client has leveraged position at risk of margin call in volatile market",
    },
]


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


def _generate_scenario_note_with_gemini(
    gemini_client, client: Client, scenario: dict, note_type: str = "initial"
) -> Tuple[str, str]:
    """Generate unique, personalized meeting note content using Gemini.

    Returns: (note_body, call_transcript)
    """
    scenario_description = scenario["description"]
    scenario_label = scenario["label"]

    if note_type == "initial":
        prompt = f"""Generate a realistic advisor meeting note for:
- Client: {client.name}, {client.risk_profile} investor
- Scenario: {scenario_label}
- Description: {scenario_description}

The note should feel personal, specific, and real. Invent realistic details (child names, schools, amounts, locations, dates, etc.)
Make it a planning meeting discussion between advisor and client.

Return ONLY this JSON (no markdown, no extra text):
{{
  "note_body": "<1-2 paragraphs of advisor's meeting note summary>",
  "call_transcript": "<realistic advisor-client conversation about this scenario>"
}}"""
    else:  # follow-up
        prompt = f"""Generate a realistic follow-up phone call between advisor and client for:
- Client: {client.name}, {client.risk_profile} investor
- Scenario: {scenario_label}
- Description: {scenario_description}

This should be a follow-up call a few weeks after the initial meeting. Include:
- Client asking questions or providing updates
- Advisor making recommendations tied to their situation
- Realistic dialogue, natural back-and-forth

Return ONLY this JSON (no markdown, no extra text):
{{
  "note_body": "<brief note from the call>",
  "call_transcript": "<realistic phone conversation>"
}}"""

    try:
        from google.genai import types as genai_types
        response = generate_with_retry(
            lambda: gemini_client.models.generate_content(
                model="gemini-2.5-flash-lite",
                contents=prompt,
                config=genai_types.GenerateContentConfig(temperature=0.9),
            )
        )

        if not response or not response.text:
            raise ValueError("Empty response from Gemini")

        raw_text = response.text.strip()
        # Strip markdown code fences if present
        if raw_text.startswith("```"):
            raw_text = "\n".join([line for line in raw_text.splitlines() if not line.strip().startswith("```")]).strip()

        parsed = json.loads(raw_text)
        return parsed.get("note_body", ""), parsed.get("call_transcript", "")
    except Exception as e:
        print(f"     ERROR generating with Gemini after retries: {e}")
        return "", ""


def _generate_scenario_note_fallback(client: Client, scenario: dict, note_type: str = "initial") -> Tuple[str, str]:
    """Fallback template-based generation if Gemini unavailable."""
    scenario_key = scenario["key"]

    # Scenario-specific fallback templates - both initial and follow-up
    templates = {
        "EDUCATION_WITHDRAWAL": {
            "initial": (
                f"Client {client.name} discussed upcoming education withdrawal. Child starting university soon, "
                f"planning to withdraw ~$30-35k from RESP by August. Concerned about market timing and tax implications.",
                f"Advisor: {client.name}, congrats on your child's university acceptance! "
                f"Client: Thanks! They got into their top choice. We need to figure out the RESP withdrawal. "
                f"Advisor: Let's plan the timing carefully. Current market conditions are important. "
                f"Client: What's your recommendation? "
                f"Advisor: We should spread the withdrawal across Q2-Q3 to reduce market timing risk.",
            ),
            "follow-up": (
                f"Follow-up call with {client.name} regarding RESP withdrawal execution and timing.",
                f"Advisor: {client.name}, following up on the RESP withdrawal plan we discussed. "
                f"Client: Yes, we're getting ready for the withdrawal. What's the next step? "
                f"Advisor: Let's lock in the withdrawal schedule now and prepare the paperwork. "
                f"Client: How long will this take to complete? "
                f"Advisor: About one week from submission to completion.",
            ),
        },
        "TAX_LOSS_HARVESTING": {
            "initial": (
                f"Client {client.name} has position with unrealized losses. Wants to harvest losses before year-end "
                f"to offset capital gains. Discussed tax-efficient strategy without triggering wash sale rules.",
                f"Advisor: {client.name}, I've identified some tax-loss harvesting opportunities. "
                f"Client: How much can we save? "
                f"Advisor: Roughly $3-5k in taxes if we execute before December 31. "
                f"Client: What positions are we looking at? "
                f"Advisor: Let me send you a detailed analysis with the wash sale considerations.",
            ),
            "follow-up": (
                f"Follow-up call regarding tax-loss harvesting execution before year-end deadline.",
                f"Advisor: {client.name}, ready to move forward with the tax-loss harvesting? "
                f"Client: Yes, let's do it. What exactly happens? "
                f"Advisor: We sell the losing positions and immediately buy similar alternatives. "
                f"Client: Won't that change my allocation? "
                f"Advisor: We rebalance back to your targets, so no permanent change.",
            ),
        },
        "HOME_PURCHASE": {
            "initial": (
                f"Client {client.name} planning home purchase in 18 months. Discussing liquidity needs and "
                f"whether to adjust portfolio risk on down payment funds. Target purchase amount ~$600k.",
                f"Advisor: {client.name}, let's talk about your home purchase timeline. "
                f"Client: We're targeting late 2027 or early 2028. Need about $150k down payment. "
                f"Advisor: That means we should move those funds to more stable investments now. "
                f"Client: What do you suggest? "
                f"Advisor: Bonds and GICs for the down payment portion, keep growth allocation separate.",
            ),
            "follow-up": (
                f"Follow-up on home purchase planning and down payment fund allocation strategy.",
                f"Advisor: {client.name}, I've drafted a plan to protect your down payment funds. "
                f"Client: Perfect, let's review it. When should we start moving money? "
                f"Advisor: We can start this month with a gradual shift to lower-risk investments. "
                f"Client: Will I still earn some growth? "
                f"Advisor: Yes, bonds provide steady income while protecting your principal.",
            ),
        },
        "RETIREMENT_DRAWDOWN": {
            "initial": (
                f"Client {client.name} recently retired. Transitioning from accumulation to sustainable withdrawal strategy. "
                f"Discussed CPP/OAS timing and transition to income-focused allocation.",
                f"Advisor: {client.name}, congratulations on retirement! "
                f"Client: Thanks! It feels surreal. I'm a bit worried about making sure the money lasts. "
                f"Advisor: We'll set up a sustainable withdrawal plan. What's your annual spending target? "
                f"Client: Probably $80-100k per year. "
                f"Advisor: That's well within your portfolio capacity. Let's model a few scenarios.",
            ),
            "follow-up": (
                f"Follow-up call to finalize retirement income withdrawal strategy and adjust portfolio.",
                f"Advisor: {client.name}, I've modeled your retirement withdrawal scenarios. "
                f"Client: How does it look? "
                f"Advisor: Your plan is sustainable well into your 90s with your current spending. "
                f"Client: That's reassuring. When do we implement the new allocation? "
                f"Advisor: This week. We'll transition you to our income-focused portfolio.",
            ),
        },
        "INHERITANCE_WINDFALL": {
            "initial": (
                f"Client {client.name} received inheritance of ~$250k. Needs strategy for deploying capital efficiently. "
                f"Discussed tax implications and allocation strategy aligned with existing portfolio.",
                f"Advisor: {client.name}, I'm sorry for your loss, but let's talk about next steps. "
                f"Client: Yes, I need to figure out what to do with the inheritance. "
                f"Advisor: We'll integrate it thoughtfully. How soon do you need the money? "
                f"Client: No urgent timeline, I just want it working well. "
                f"Advisor: Perfect. We have flexibility to optimize the implementation.",
            ),
            "follow-up": (
                f"Follow-up to discuss inheritance deployment strategy and investment approach.",
                f"Advisor: {client.name}, I've prepared a deployment plan for the inheritance. "
                f"Client: How will you invest it? "
                f"Advisor: We'll dollar-cost-average over 3-4 months to reduce market timing risk. "
                f"Client: That sounds prudent. When can we start? "
                f"Advisor: This month, with monthly investments going forward.",
            ),
        },
        "MAJOR_LIFE_EVENT": {
            "initial": (
                f"Client {client.name} experienced major life change affecting risk tolerance. "
                f"Reassessing investment objectives and rebalancing portfolio to reflect new circumstances.",
                f"Advisor: {client.name}, I understand things have changed significantly. "
                f"Client: Yes, and my comfort with risk has changed too. "
                f"Advisor: Let's update your risk profile and adjust the portfolio accordingly. "
                f"Client: When can we make changes? "
                f"Advisor: We can implement changes within the week.",
            ),
            "follow-up": (
                f"Follow-up to implement portfolio changes based on updated risk profile.",
                f"Advisor: {client.name}, ready to move forward with the portfolio rebalancing? "
                f"Client: Yes, I feel much better about a more conservative approach. "
                f"Advisor: I've prepared a new allocation that matches your updated risk tolerance. "
                f"Client: How long will the transition take? "
                f"Advisor: We'll phase in the changes over 2-3 weeks to manage costs.",
            ),
        },
        "ESTATE_PLANNING": {
            "initial": (
                f"Client {client.name} initiated estate planning review. Discussed beneficiary designations, will review, "
                f"and power of attorney documentation. Connected with estate planning specialist.",
                f"Advisor: {client.name}, let's update your beneficiary designations today. "
                f"Client: I haven't looked at this in years. Have things changed? "
                f"Advisor: Let me review the current list and we'll confirm everything is current. "
                f"Client: What else should I consider? "
                f"Advisor: We should also review your will and power of attorney.",
            ),
            "follow-up": (
                f"Follow-up on estate planning documentation and beneficiary designation updates.",
                f"Advisor: {client.name}, I've worked with our estate planner on your documents. "
                f"Client: What needs to be updated? "
                f"Advisor: Your beneficiaries on several accounts and your will needs refreshing. "
                f"Client: How quickly can we get this done? "
                f"Advisor: The estate planner can meet with you next month to finalize everything.",
            ),
        },
        "RRSP_DEADLINE": {
            "initial": (
                f"Client {client.name} has available RRSP room. Discussed importance of contribution before deadline "
                f"to maximize tax deduction. $8-10k contribution recommended.",
                f"Advisor: {client.name}, you have good RRSP room available. "
                f"Client: How much room am I missing out on? "
                f"Advisor: You have about $10k of unused room. "
                f"Client: Should I contribute? "
                f"Advisor: Definitely. We need to do it before the March deadline for tax purposes.",
            ),
            "follow-up": (
                f"Follow-up to execute RRSP contribution before March deadline.",
                f"Advisor: {client.name}, let's get your RRSP contribution in before the deadline. "
                f"Client: How much should I contribute? "
                f"Advisor: I recommend using the full $10k to maximize your tax deduction. "
                f"Client: Where will the money come from? "
                f"Advisor: We can take it from your cash reserves and rebalance your portfolio.",
            ),
        },
        "BUSINESS_SALE": {
            "initial": (
                f"Client {client.name} sold business and received substantial lump sum (~$800k). "
                f"Developing deployment strategy considering tax optimization and risk tolerance.",
                f"Advisor: {client.name}, congratulations on the sale! "
                f"Client: Thanks, it's a relief. Now I need to figure out what to do with the proceeds. "
                f"Advisor: We'll deploy it systematically across several months. "
                f"Client: Why not all at once? "
                f"Advisor: Dollar-cost averaging reduces market timing risk and allows us to optimize each tranche.",
            ),
            "follow-up": (
                f"Follow-up to begin business sale proceeds deployment strategy.",
                f"Advisor: {client.name}, let's begin deploying your business sale proceeds. "
                f"Client: What's the timeline? "
                f"Advisor: We'll invest the money monthly over 6-8 months to manage risk. "
                f"Client: And what will we invest in? "
                f"Advisor: A diversified portfolio aligned with your long-term goals and risk tolerance.",
            ),
        },
        "MATERNITY_LEAVE": {
            "initial": (
                f"Client {client.name} going on parental leave soon. Income will reduce by ~40% for the leave period. "
                f"Discussed emergency fund and budget adjustments.",
                f"Advisor: {client.name}, excited about your expanding family! "
                f"Client: Thanks! But I'm nervous about the leave impact on finances. "
                f"Advisor: Let's plan for the income reduction and make sure you're comfortable. "
                f"Client: How much should I have in emergency savings? "
                f"Advisor: At least 6 months of your reduced expenses. Let's calculate that together.",
            ),
            "follow-up": (
                f"Follow-up to finalize parental leave financial planning and emergency fund setup.",
                f"Advisor: {client.name}, I've calculated your emergency fund needs for parental leave. "
                f"Client: How much do I need? "
                f"Advisor: We should have about $30k liquid before you take leave. "
                f"Client: How do we build that up? "
                f"Advisor: We can redirect some investments to cash over the next few months.",
            ),
        },
        "FOREIGN_PROPERTY": {
            "initial": (
                f"Client {client.name} purchasing property in the USA. Needs USD strategy and FX hedging discussion. "
                f"Planning $400k USD purchase, discussing currency conversion timing.",
                f"Advisor: {client.name}, tell me about the US property. "
                f"Client: We're buying a place in Arizona, about $400k USD. "
                f"Advisor: We need to plan the currency conversion carefully. When do you close? "
                f"Client: About 4 months from now. "
                f"Advisor: That gives us time to build a USD position efficiently and discuss hedging options.",
            ),
            "follow-up": (
                f"Follow-up on USD currency strategy and timing for international property purchase.",
                f"Advisor: {client.name}, let's discuss the USD building strategy for your purchase. "
                f"Client: What's your recommendation? "
                f"Advisor: Build the USD position monthly to average the exchange rate. "
                f"Client: When should we start? "
                f"Advisor: Immediately, so we have the full $400k USD by closing time.",
            ),
        },
        "CHARITABLE_GIVING": {
            "initial": (
                f"Client {client.name} wants to donate appreciated securities before year-end. "
                f"Discussed tax benefits of donating securities directly vs. selling and donating cash.",
                f"Advisor: {client.name}, I like your charitable giving plan. "
                f"Client: I want to donate to the food bank but I'm not sure how. "
                f"Advisor: If you donate appreciated securities directly, you avoid the capital gains tax. "
                f"Client: Really? That's better? "
                f"Advisor: Much better. You get the full deduction without the tax hit.",
            ),
            "follow-up": (
                f"Follow-up to execute charitable giving of appreciated securities before year-end.",
                f"Advisor: {client.name}, ready to make your charitable donation before year-end? "
                f"Client: Yes, let's do it. Which securities should I donate? "
                f"Advisor: The ones with the largest gains—that maximizes your tax benefit. "
                f"Client: How quickly can we transfer them to the charity? "
                f"Advisor: Within a few days. We can coordinate with the charity's fund manager.",
            ),
        },
        "MARGIN_CALL_RISK": {
            "initial": (
                f"Client {client.name} has leveraged position that's at risk. Market volatility could trigger margin call. "
                f"Discussed reducing leverage and establishing safeguards.",
                f"Advisor: {client.name}, I want to discuss your margin position. "
                f"Client: What's the concern? "
                f"Advisor: Recent volatility brings your margin ratio close to triggering a call. "
                f"Client: How serious is this? "
                f"Advisor: We should reduce leverage now while we can, proactively.",
            ),
            "follow-up": (
                f"URGENT follow-up to reduce margin position and implement risk safeguards.",
                f"Advisor: {client.name}, we need to act on reducing your margin immediately. "
                f"Client: What exactly needs to happen? "
                f"Advisor: We'll liquidate some positions to pay down the margin loan. "
                f"Client: How much impact will this have? "
                f"Advisor: Minimal to your portfolio, but it protects you from a forced liquidation.",
            ),
        },
    }

    template = templates.get(scenario_key, {}).get(note_type, ("Generic meeting note.", "Generic transcript."))
    return template[0], template[1]


def seed_meeting_notes(session: Session, use_gemini: bool = True, force: bool = False) -> None:
    """Seed realistic, scenario-based meeting notes for first 50 clients.

    Each client is assigned a unique scenario and gets 2 notes:
    1. Initial planning meeting (with transcript)
    2. Follow-up phone call (with transcript)

    If Gemini is available and use_gemini=True, generates unique personalized content.
    Otherwise falls back to scenario templates.

    Args:
        session: Database session
        use_gemini: Whether to attempt Gemini generation
        force: If True, re-seed all clients. If False, skip clients that already have notes.
    """
    print("\n[SEEDING MEETING NOTES]")
    print(f"Scenarios to use: {len(SCENARIOS)}")
    print(f"Gemini available: {GEMINI_AVAILABLE}")
    print(f"Force re-seed: {force}\n")

    now = datetime.utcnow()
    ai_provider = MockAIProvider()

    # Query first 50 clients
    clients: List[Client] = session.query(Client).limit(50).all()

    # If not forcing, filter out clients that already have meeting notes
    if not force:
        clients_with_notes = set(
            session.query(MeetingNote.client_id).distinct().all()
        )
        clients_with_notes = {row[0] for row in clients_with_notes}
        clients = [c for c in clients if c.id not in clients_with_notes]
        print(f"Skipping {len(clients_with_notes)} clients that already have notes")

    print(f"Seeding notes for {len(clients)} clients\n")

    if not clients:
        print("[MEETING NOTES SEEDING] No clients to seed\n")
        return

    # Initialize Gemini if available
    gemini_client = None
    if GEMINI_AVAILABLE and use_gemini:
        gemini_api_key = os.getenv("GEMINI_API_KEY")
        if gemini_api_key:
            gemini_client = genai.Client(api_key=gemini_api_key)
            print("Gemini client initialized for note generation\n")
        else:
            print("WARNING: GEMINI_API_KEY not set, will use fallback templates\n")

    notes_created = 0
    for idx, client in enumerate(clients, 1):
        try:
            # Assign scenario based on client ID
            scenario_idx = client.id % len(SCENARIOS)
            scenario = SCENARIOS[scenario_idx]

            print(f"[{idx}/{len(clients)}] {client.name} -> {scenario['label']}")

            base_date = now - timedelta(days=30 + (client.id % 60))

            # Note 1: Initial planning meeting with Gemini-generated content
            if gemini_client and use_gemini:
                note1_body, note1_transcript = _generate_scenario_note_with_gemini(
                    gemini_client, client, scenario, note_type="initial"
                )
                if not note1_body or not note1_transcript:  # Fallback if Gemini call failed
                    note1_body, note1_transcript = _generate_scenario_note_fallback(client, scenario, note_type="initial")
                time.sleep(1)  # Rate limit: 1 second between Gemini calls
            else:
                note1_body, note1_transcript = _generate_scenario_note_fallback(client, scenario, note_type="initial")

            # Use mock provider to summarize the transcript (with safe defaults)
            if note1_transcript and isinstance(note1_transcript, str) and note1_transcript.strip():
                summary_result = ai_provider.summarize_transcript(
                    transcript=note1_transcript,
                    context={
                        "client_name": client.name,
                        "risk_profile": client.risk_profile,
                        "scenario": scenario["label"],
                    }
                )
            else:
                # Fallback summary if transcript is empty
                summary_result = ai_provider.summarize_transcript(
                    transcript=f"Advisor discussed {scenario['label']} with {client.name}.",
                    context={
                        "client_name": client.name,
                        "risk_profile": client.risk_profile,
                        "scenario": scenario["label"],
                    }
                )

            # Ensure call_transcript is a string, not a list
            note1_transcript_str = note1_transcript or ""
            if isinstance(note1_transcript_str, list):
                note1_transcript_str = json.dumps(note1_transcript_str)
            elif not isinstance(note1_transcript_str, str):
                note1_transcript_str = str(note1_transcript_str)

            note1 = MeetingNote(
                client_id=client.id,
                title=f"{scenario['label']} - Planning Meeting",
                meeting_date=base_date,
                note_body=note1_body or f"Meeting regarding {scenario['label']}",
                meeting_type=MeetingNoteType.PHONE_CALL,
                call_transcript=note1_transcript_str,
                ai_summary=summary_result.summary_paragraph,
                ai_action_items=summary_result.action_items if isinstance(summary_result.action_items, list) else [],
                ai_summarized_at=datetime.utcnow(),
                ai_provider_used="mock",
            )
            session.add(note1)

            # Note 2: Follow-up call
            if gemini_client and use_gemini:
                note2_body, note2_transcript = _generate_scenario_note_with_gemini(
                    gemini_client, client, scenario, note_type="follow-up"
                )
                if not note2_body or not note2_transcript:  # Fallback if Gemini call failed
                    note2_body, note2_transcript = _generate_scenario_note_fallback(client, scenario, note_type="follow-up")
                time.sleep(1)  # Rate limit
            else:
                note2_body, note2_transcript = _generate_scenario_note_fallback(client, scenario, note_type="follow-up")

            # Summarize follow-up transcript (with safe defaults)
            if note2_transcript and isinstance(note2_transcript, str) and note2_transcript.strip():
                summary_result2 = ai_provider.summarize_transcript(
                    transcript=note2_transcript,
                    context={
                        "client_name": client.name,
                        "risk_profile": client.risk_profile,
                        "scenario": scenario["label"],
                    }
                )
            else:
                summary_result2 = ai_provider.summarize_transcript(
                    transcript=f"Follow-up call with {client.name} regarding {scenario['label']}.",
                    context={
                        "client_name": client.name,
                        "risk_profile": client.risk_profile,
                        "scenario": scenario["label"],
                    }
                )

            # Ensure call_transcript is a string, not a list
            note2_transcript_str = note2_transcript or ""
            if isinstance(note2_transcript_str, list):
                note2_transcript_str = json.dumps(note2_transcript_str)
            elif not isinstance(note2_transcript_str, str):
                note2_transcript_str = str(note2_transcript_str)

            note2 = MeetingNote(
                client_id=client.id,
                title=f"{scenario['label']} - Follow-up Call",
                meeting_date=base_date - timedelta(days=14),
                note_body=note2_body or f"Follow-up regarding {scenario['label']}",
                meeting_type=MeetingNoteType.PHONE_CALL,
                call_transcript=note2_transcript_str,
                ai_summary=summary_result2.summary_paragraph,
                ai_action_items=summary_result2.action_items if isinstance(summary_result2.action_items, list) else [],
                ai_summarized_at=datetime.utcnow(),
                ai_provider_used="mock",
            )
            session.add(note2)
            notes_created += 2

            # Batch flush every 10 clients
            if idx % 10 == 0:
                session.flush()
                session.commit()
                print(f"   ✓ Batch committed: {idx} clients, {notes_created} notes\n")

        except Exception as e:
            print(f"   ERROR processing {client.name}: {e}")
            session.rollback()
            continue

    # Final commit
    session.commit()
    print(f"\n[MEETING NOTES SEEDING COMPLETE] {len(clients)} clients, {notes_created} notes created\n")


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


def seed_custom_portfolios_with_alerts(session: Session) -> None:
    """Seed 243 custom portfolios with realistic alerts.

    - 40% split among Classic/Summit/Direct Indexing/Income
    - 60% Custom portfolios
    - 30% of portfolios have open alerts
    - Alert priority: 20% HIGH, 30% MEDIUM, 50% LOW
    - Alert statuses: 60% OPEN, 20% REVIEWED, 12% ESCALATED, 8% FALSE_POSITIVE
    """
    from models import Run, Alert, AlertStatus, Priority, AuditEvent, AuditEventType

    print("\n[SEEDING CUSTOM PORTFOLIOS WITH ALERTS]")

    random.seed(42)
    full_names = _generate_unique_names(243)
    now = datetime.utcnow()

    # Portfolio type distribution: 40% split (10% each) + 60% Custom
    standard_types = ["Classic", "Summit", "Direct Indexing", "Income"]

    # Alert configuration
    total_portfolios = 243
    alert_percentage = 0.30
    portfolios_with_alerts = int(total_portfolios * alert_percentage)

    # Priority distribution among alerted portfolios: 20% HIGH, 30% MEDIUM, 50% LOW
    high_count = int(portfolios_with_alerts * 0.20)
    medium_count = int(portfolios_with_alerts * 0.30)
    low_count = portfolios_with_alerts - high_count - medium_count

    print(f"Total portfolios: {total_portfolios}")
    print(f"Portfolios with alerts: {portfolios_with_alerts}")
    print(f"  HIGH: {high_count}, MEDIUM: {medium_count}, LOW: {low_count}\n")

    # Create run for seeded alerts
    run = Run(started_at=now, provider_used="seed", alerts_created=0)
    session.add(run)
    session.flush()

    alert_portfolio_ids = set(random.sample(range(total_portfolios), portfolios_with_alerts))
    alert_priorities = (
        [Priority.HIGH] * high_count +
        [Priority.MEDIUM] * medium_count +
        [Priority.LOW] * low_count
    )
    random.shuffle(alert_priorities)
    alert_idx = 0

    # Alert status distribution for demo
    # 60% OPEN, 20% REVIEWED, 12% ESCALATED, 8% FALSE_POSITIVE
    status_distribution = (
        [AlertStatus.OPEN] * int(portfolios_with_alerts * 0.60) +
        [AlertStatus.REVIEWED] * int(portfolios_with_alerts * 0.20) +
        [AlertStatus.ESCALATED] * int(portfolios_with_alerts * 0.12)
    )
    # Fill remaining with FALSE_POSITIVE
    status_distribution += [AlertStatus.FALSE_POSITIVE] * (portfolios_with_alerts - len(status_distribution))
    random.shuffle(status_distribution)
    status_idx = 0

    for i in range(total_portfolios):
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
            account_tier="Core",
            created_at=now - timedelta(days=random.randint(30, 365 * 8)),
        )
        session.add(client)
        session.flush()

        # Portfolio type distribution: 40% standard (10% each), 60% Custom
        if i < int(total_portfolios * 0.4):
            # Standard types (40%)
            type_idx = (i // int(total_portfolios * 0.1)) % len(standard_types)
            portfolio_name = standard_types[type_idx]
        else:
            # Custom portfolios (60%)
            portfolio_name = "Custom"

        total_value = Decimal(random.randint(50_000, 2_000_000))
        target_equity, target_fixed_income, target_cash = _target_allocations_for_profile(risk_profile)

        # Custom allocations for custom portfolios (add variation)
        if portfolio_name == "Custom":
            total_equity, total_fixed_income, total_cash = target_equity, target_fixed_income, target_cash
            # Random variations for custom
            variation = random.uniform(-5, 5)
            target_equity = max(0, min(100, target_equity + variation))
            target_fixed_income = max(0, min(100, target_fixed_income - variation / 2))
            target_cash = max(0, 100 - target_equity - target_fixed_income)

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

        client.account_tier = _account_tier_for_aum(float(total_value))

        _create_positions_for_portfolio(session, portfolio, total_value)

        # Seed alert if this portfolio is selected
        if i in alert_portfolio_ids:
            scenario_idx = client.id % len(SCENARIOS)
            scenario = SCENARIOS[scenario_idx]
            scenario_key = scenario["key"]

            priority = alert_priorities[alert_idx]
            alert_status = status_distribution[status_idx]

            # More varied confidence: 40-98 with clustering around different values
            confidence_seed = random.random()
            if confidence_seed < 0.3:
                confidence = random.randint(40, 60)  # 30% low confidence
            elif confidence_seed < 0.6:
                confidence = random.randint(60, 80)  # 30% medium confidence
            else:
                confidence = random.randint(80, 98)  # 40% high confidence

            status_idx += 1

            # Scenario-specific alert titles and summaries
            scenario_alerts = {
                "EDUCATION_WITHDRAWAL": {
                    "title": "RESP Withdrawal Timing - Child Starting University",
                    "summary": f"Client {name} needs to plan RESP withdrawal for child starting university in ~8 months. Current portfolio volatility may impact withdrawal amount. Recommend locking in stable allocation for the withdrawal portion now.",
                },
                "TAX_LOSS_HARVESTING": {
                    "title": "Year-End Tax Loss Harvesting Opportunity",
                    "summary": f"Client {name} has unrealized losses in {portfolio_name} portfolio. Before year-end, can harvest these losses to offset gains and reduce tax liability. Window is closing—recommend executing before December 31.",
                },
                "HOME_PURCHASE": {
                    "title": "Home Purchase Down Payment Risk",
                    "summary": f"Client {name} planning home purchase in 12-18 months. Current equity allocation poses risk to down payment funds. Recommend gradually shifting allocated funds to stable investments.",
                },
                "RETIREMENT_DRAWDOWN": {
                    "title": "Retirement Income Drawdown Not Aligned",
                    "summary": f"Client {name} recently retired. Portfolio structure isn't optimized for sustainable withdrawals. Need to transition to income-focused allocation with appropriate cash reserves.",
                },
                "INHERITANCE_WINDFALL": {
                    "title": "Inheritance Capital Deployment Strategy",
                    "summary": f"Client {name} received inheritance. Current portfolio allocation not designed to efficiently absorb and deploy this capital. Recommend systematic deployment plan.",
                },
                "MAJOR_LIFE_EVENT": {
                    "title": "Risk Profile Change - Major Life Event",
                    "summary": f"Client {name} experienced major life change. Current portfolio risk doesn't align with updated risk tolerance. Recommend urgent rebalancing discussion.",
                },
                "ESTATE_PLANNING": {
                    "title": "Estate Planning Review Due",
                    "summary": f"Client {name} beneficiary designations not reviewed in years. Should coordinate portfolio structure with estate planning strategy.",
                },
                "RRSP_DEADLINE": {
                    "title": "RRSP Contribution Room Expiring",
                    "summary": f"Client {name} has available RRSP room ({random.randint(5, 15)}k) to use before March deadline. Tax deduction opportunity closing soon.",
                },
                "BUSINESS_SALE": {
                    "title": "Business Sale Proceeds - Strategic Deployment",
                    "summary": f"Client {name} sold business. Large lump sum needs careful deployment strategy to manage tax, risk, and market timing.",
                },
                "MATERNITY_LEAVE": {
                    "title": "Parental Leave Income Reduction Planning",
                    "summary": f"Client {name} going on parental leave. Income reduction ahead—need to adjust budget and emergency fund strategy.",
                },
                "FOREIGN_PROPERTY": {
                    "title": "International Property Purchase - USD Strategy",
                    "summary": f"Client {name} buying property in USA. Need currency conversion strategy and timing to minimize FX risk.",
                },
                "CHARITABLE_GIVING": {
                    "title": "Year-End Charitable Giving Strategy",
                    "summary": f"Client {name} wants to donate appreciated securities. Direct donation strategy more tax-efficient than selling first.",
                },
                "MARGIN_CALL_RISK": {
                    "title": "URGENT: Margin Call Risk - Leverage Too High",
                    "summary": f"Client {name} has leveraged position at risk. Recent volatility brings margin ratio dangerously close. Recommend immediate deleveraging.",
                },
            }

            alert_info = scenario_alerts.get(scenario_key, {
                "title": f"{scenario['label']} Alert",
                "summary": f"Portfolio requires review based on {scenario['label']} scenario.",
            })

            alert = Alert(
                run_id=run.id,
                portfolio_id=portfolio.id,
                client_id=client.id,
                created_at=now,
                priority=priority,
                confidence=confidence,
                event_title=alert_info["title"],
                summary=alert_info["summary"],
                reasoning_bullets=[
                    f"Scenario: {scenario['label']}",
                    f"Client situation: {scenario['description']}",
                    f"Action required: Advisor review and client discussion needed",
                ],
                human_review_required=True,
                suggested_next_step="Schedule meeting with client to discuss scenario and adjust strategy",
                decision_trace_steps=[
                    {"step": "Detection", "detail": scenario["label"]},
                    {"step": "Assessment", "detail": "Scenario-driven risk identified"},
                    {"step": "Action", "detail": "Advisor review required"},
                ],
                change_detection=[
                    {"metric": "scenario_match", "from": "unknown", "to": scenario_key}
                ],
                status=alert_status,
                concentration_score=random.uniform(2, 8),
                drift_score=random.uniform(2, 9),
                volatility_proxy=random.uniform(1, 8),
                risk_score=random.uniform(2, 8),
                scenario=scenario_key,
            )
            session.add(alert)

            # Add AuditEvent for non-OPEN alerts (to show demo history)
            if alert_status == AlertStatus.REVIEWED:
                audit_event = AuditEvent(
                    run_id=run.id,
                    alert_id=alert.id,
                    event_type=AuditEventType.ALERT_REVIEWED,
                    actor=random.choice(["advisor_sarah", "advisor_james", "advisor_priya"]),
                    details={
                        "priority": priority.value,
                        "confidence": confidence,
                        "review_notes": "Alert reviewed and assessed. No immediate action required at this time."
                    }
                )
                session.add(audit_event)
            elif alert_status == AlertStatus.ESCALATED:
                audit_event = AuditEvent(
                    run_id=run.id,
                    alert_id=alert.id,
                    event_type=AuditEventType.ALERT_ESCALATED,
                    actor=random.choice(["advisor_sarah", "advisor_james", "advisor_priya"]),
                    details={
                        "priority": priority.value,
                        "escalation_reason": "Requires immediate client contact and portfolio adjustment",
                        "escalated_to": "portfolio_manager"
                    }
                )
                session.add(audit_event)
            elif alert_status == AlertStatus.FALSE_POSITIVE:
                audit_event = AuditEvent(
                    run_id=run.id,
                    alert_id=alert.id,
                    event_type=AuditEventType.ALERT_FALSE_POSITIVE,
                    actor=random.choice(["advisor_sarah", "advisor_james", "advisor_priya"]),
                    details={
                        "reason": "Alert triggered by temporary market conditions. Client confirmed satisfaction with current strategy.",
                        "confidence": confidence
                    }
                )
                session.add(audit_event)

            alert_idx += 1

    # Apply confidence distribution to all seeded alerts (overrides Gemini values)
    # 30% low (40-60), 30% medium (60-80), 40% high (80-98)
    seeded_alerts = session.query(Alert).filter_by(run_id=run.id).all()
    confidence_distribution = []
    for _ in range(len(seeded_alerts)):
        confidence_seed = random.random()
        if confidence_seed < 0.3:
            confidence_distribution.append(random.randint(40, 60))
        elif confidence_seed < 0.6:
            confidence_distribution.append(random.randint(60, 80))
        else:
            confidence_distribution.append(random.randint(80, 98))
    random.shuffle(confidence_distribution)

    for idx, alert in enumerate(seeded_alerts):
        alert.confidence = confidence_distribution[idx]

    run.alerts_created = portfolios_with_alerts
    session.flush()

    print(f"[SEEDED ALERTS] Created {portfolios_with_alerts} alerts in run {run.id}\n")


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Seed database with custom portfolios and meeting notes.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-seed all clients' meeting notes (default: skip clients that already have notes)",
    )
    args = parser.parse_args()

    reset_database()
    session = SessionLocal()
    try:
        # Seed custom portfolios with intelligent alert distribution
        seed_custom_portfolios_with_alerts(session)
        session.commit()

        # Seed meeting notes for first 50 clients with scenario context
        seed_meeting_notes(session, force=args.force)
        session.commit()

        export_seed_snapshot(session)
        print("[SEED COMPLETE] Database ready for new_backfill.py\n")
    finally:
        session.close()


if __name__ == "__main__":
    main()

