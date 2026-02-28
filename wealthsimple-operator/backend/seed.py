"""
Seed script generating complete client universes with Gemini-powered unique generation.

Each client universe includes:
- Gemini-generated unique name, AUM, investment goals, and motivations
- Probabilistic alert assignment (30% have alerts)
- If alert: Scenario-driven meeting notes with linear progression
- Auto-summarized transcripts for all calls
- Guaranteed: Every client has ≥1 call log + ≥1 meeting note

Run: python seed.py [--clients N] [--gemini-enabled]
"""

from __future__ import annotations

import json
import os
import random
import re
import time
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Tuple, Optional, Dict, Any
from pathlib import Path

from sqlalchemy.orm import Session
from dotenv import load_dotenv

from db import Base, SessionLocal, engine
from models import (
    Client,
    Portfolio,
    Position,
    MeetingNote,
    MeetingNoteType,
    Alert,
    AlertStatus,
    Run,
    AuditEvent,
    AuditEventType,
    Priority,
)
from ai.mock_provider import MockAIProvider

# Try to import Gemini
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

# ============================================================================
# Scenario definitions for structured meeting note progression
# ============================================================================
SCENARIOS = [
    {
        "key": "EDUCATION_WITHDRAWAL",
        "label": "Education Withdrawal",
        "description": "Child starting school soon, RESP withdrawal imminent",
        "timeline_days": [0, 30, 60],  # Initial meeting, 1-month follow-up, 2-month follow-up
    },
    {
        "key": "TAX_LOSS_HARVESTING",
        "label": "Tax Loss Harvesting",
        "description": "End of year, losses in position, client wants to offset gains",
        "timeline_days": [0, 20, 45],
    },
    {
        "key": "HOME_PURCHASE",
        "label": "Home Purchase",
        "description": "Client buying a home in 12-18 months, needs liquidity",
        "timeline_days": [0, 45, 90],
    },
    {
        "key": "RETIREMENT_DRAWDOWN",
        "label": "Retirement Drawdown",
        "description": "Client just retired, switching from accumulation to drawdown",
        "timeline_days": [0, 30, 60],
    },
    {
        "key": "INHERITANCE_WINDFALL",
        "label": "Inheritance Windfall",
        "description": "Client received large inheritance, needs rebalancing",
        "timeline_days": [0, 14, 35],
    },
    {
        "key": "MARGIN_CALL_RISK",
        "label": "Margin Call Risk",
        "description": "Client has leveraged position at risk of margin call in volatile market",
        "timeline_days": [0, 7, 21],
    },
    {
        "key": "CONCENTRATED_STOCK_POSITION",
        "label": "Concentrated Stock Position",
        "description": "Single equity position has grown beyond concentration limits and dominates portfolio risk",
        "timeline_days": [0, 14, 45],
    },
    {
        "key": "BUSINESS_EXIT_LIQUIDITY_EVENT",
        "label": "Business Exit Liquidity Event",
        "description": "Client is expecting proceeds from a business sale and needs staged capital deployment",
        "timeline_days": [0, 21, 60],
    },
    {
        "key": "CROSS_BORDER_RELOCATION",
        "label": "Cross-Border Relocation",
        "description": "Client is relocating internationally and needs tax and currency-aware portfolio adjustments",
        "timeline_days": [0, 30, 75],
    },
    {
        "key": "CHARITABLE_GIVING_STRATEGY",
        "label": "Charitable Giving Strategy",
        "description": "Client wants to donate appreciated securities and optimize tax-efficient giving",
        "timeline_days": [0, 20, 50],
    },
    {
        "key": "ESTATE_FREEZE_PLANNING",
        "label": "Estate Freeze Planning",
        "description": "Client is implementing estate freeze and intergenerational transfer strategy",
        "timeline_days": [0, 28, 70],
    },
    {
        "key": "INTEREST_RATE_REFINANCE_WINDOW",
        "label": "Interest Rate Refinance Window",
        "description": "Rate changes create refinancing decisions that alter liquidity needs and risk posture",
        "timeline_days": [0, 10, 35],
    },
    {
        "key": "DIVORCE_SETTLEMENT_REBALANCE",
        "label": "Divorce Settlement Rebalance",
        "description": "Post-settlement assets need portfolio restructuring and updated risk alignment",
        "timeline_days": [0, 21, 55],
    },
    {
        "key": "RSU_VESTING_TAX_MANAGEMENT",
        "label": "RSU Vesting Tax Management",
        "description": "Upcoming RSU vesting introduces concentration and tax withholding planning needs",
        "timeline_days": [0, 14, 42],
    },
    {
        "key": "PENSION_COMMUTATION_DECISION",
        "label": "Pension Commutation Decision",
        "description": "Client is deciding between pension commutation and annuitized income options",
        "timeline_days": [0, 18, 48],
    },
    {
        "key": "CURRENCY_HEDGE_REVIEW",
        "label": "Currency Hedge Review",
        "description": "Foreign asset exposure has increased and requires updated currency hedging policy",
        "timeline_days": [0, 12, 36],
    },
    {
        "key": "PRIVATE_MARKET_LIQUIDITY_LOCKUP",
        "label": "Private Market Liquidity Lockup",
        "description": "Increased private allocation creates liquidity and cashflow mismatch risk",
        "timeline_days": [0, 25, 65],
    },
    {
        "key": "CRITICAL_ILLNESS_CONTINGENCY",
        "label": "Critical Illness Contingency",
        "description": "Medical contingency planning requires short-term liquidity and defensive allocation",
        "timeline_days": [0, 9, 30],
    },
    {
        "key": "DRAWDOWN_SEQUENCE_RISK",
        "label": "Drawdown Sequence Risk",
        "description": "Early retirement withdrawals increase sequence-of-returns risk under current allocation",
        "timeline_days": [0, 16, 46],
    },
    {
        "key": "ALTERNATIVE_ASSET_OVEREXPOSURE",
        "label": "Alternative Asset Overexposure",
        "description": "Alternatives sleeve has expanded beyond mandate and needs rebalancing discipline",
        "timeline_days": [0, 20, 58],
    },
]
SCENARIO_KEYS_PROMPT = "|".join(s["key"] for s in SCENARIOS)

# Segments and risk profiles
SEGMENTS = ["Core", "Affluent", "HNW", "UHNW"]
RISK_PROFILES = ["Conservative", "Balanced", "Growth", "Aggressive"]

# Extended name pools for better diversity
FIRST_NAMES = [
    "Alex", "Amelia", "Aria", "Benjamin", "Jordan", "Noah", "Liam", "Taylor",
    "Priya", "Maya", "Morgan", "Ethan", "Olivia", "Casey", "Sofia", "Emma",
    "Riley", "Lucas", "Aiden", "Avery", "Harper", "Nora", "Quinn", "Mateo",
    "Isla", "Jamie", "Leo", "Mila", "Cameron", "Kai", "Zoe", "Aisha",
    "Rohan", "Daniel", "Samira", "Chloe", "Owen", "Ruby", "Gabriel", "Layla",
    "Ivy", "Elias", "Hassan", "Fatima", "Diego", "Lucia", "Anika", "Marcus",
    "Jasmine", "Adrian", "Nina", "Vikram", "Patel", "Sarah", "Michael", "Jennifer",
    "David", "Anna", "James", "Maria", "Robert", "Patricia", "William", "Linda",
    "Richard", "Barbara", "Joseph", "Susan", "Thomas", "Jessica", "Christopher",
    "Karen", "Matthew", "Lisa", "Anthony", "Nancy", "Donald", "Betty", "Mark",
    "Margaret", "Steven", "Sandra", "Paul", "Ashley", "Andrew", "Kimberly",
    "Joshua", "Donna", "Kenneth", "Carol", "Kevin", "Michelle", "Brian", "Amanda",
    "George", "Melissa", "Edward", "Deborah", "Ronald", "Stephanie", "Timothy",
    "Rebecca", "Jason", "Laura", "Jeffrey", "Sharon", "Ryan", "Cynthia", "Jacob",
    "Kathleen", "Gary", "Amy", "Nicholas", "Shirley", "Eric", "Angela", "Jonathan",
    "Helen", "Stephen", "Anna", "Larry", "Brenda", "Justin", "Pamela", "Scott",
    "Nicole", "Brandon", "Samantha", "Benjamin", "Katherine", "Samuel", "Christine"
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
    "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson",
    "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson",
    "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson", "Young",
    "Allen", "King", "Wright", "Scott", "Torres", "Peterson", "Phillips", "Campbell",
    "Parker", "Evans", "Edwards", "Collins", "Reyes", "Stewart", "Morris", "Morales",
    "Murphy", "Cook", "Rogers", "Morgan", "Peterson", "Cooper", "Reed", "Bell",
    "Gomez", "Russell", "Fox", "Freeman", "Wells", "Webb", "Simpson", "Stevens",
    "Tucker", "Porter", "Hunter", "Hicks", "Crawford", "Henry", "Boyd", "Mason",
    "Moreno", "Kennedy", "Warren", "Dixon", "Ramos", "Reeves", "Burns", "Gordon",
    "Shaw", "Holmes", "Rice", "Robertson", "Hunt", "Black", "Daniels", "Palmer",
    "Mills", "Nichols", "Grant", "Knight", "Ferguson", "Stone", "Hawkins", "Dunn",
    "Perkins", "Hudson", "Spencer", "Gardner", "Stephens", "Payne", "Pierce", "Berry",
    "Matthews", "Arnold", "Wagner", "Willis", "Ray", "Watkins", "Olson", "Carroll",
    "Duncan", "Snyder", "Hart", "Cunningham", "Knight", "Benson", "Wilkins", "Carpenter",
    "Mccarthy", "Patel", "Khan", "Kumar", "Gupta", "Singh", "Sharma", "Desai",
    "Chen", "Wang", "Zhang", "Liu", "Li", "Yang", "Wu", "Zhou",
    "Tanaka", "Yamamoto", "Nakamura", "Kobayashi", "Watanabe", "Kimura", "Hayashi",
    "Kim", "Park", "Choi", "Jung", "Lee", "Kang", "Cho", "Yoon",
    "Muller", "Schmidt", "Schneider", "Fischer", "Meyer", "Weber", "Wagner", "Becker",
    "Schulz", "Hoffmann", "Koch", "Bauer", "Richter", "Klein", "Wolf", "Schroeder",
    "Dubois", "Martin", "Bernard", "Clement", "Garand", "Bouchard", "Levesque", "Gagnon",
    "O'Brien", "Sullivan", "Murphy", "Kelly", "Byrne", "Ryan", "Walsh", "Kennedy",
    "McCarthy", "Donnelly", "Flanagan", "Duffy", "Lynch", "Gallagher", "Quinn"
]

# ============================================================================
# Retry and error handling
# ============================================================================


def generate_with_retry(call_fn, max_retries=8):
    """Retry with exponential backoff and jitter."""
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


def _extract_json_object(raw_text: str) -> Dict[str, Any]:
    """Parse model output into dict, even if wrapped with extra text/fences."""
    text = raw_text.strip()
    if text.startswith("```"):
        text = "\n".join(
            [line for line in text.splitlines() if not line.strip().startswith("```")]
        ).strip()

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        maybe = text[start : end + 1]
        parsed = json.loads(maybe)
        if isinstance(parsed, dict):
            return parsed
    raise ValueError("Could not parse model output as JSON object")


def _normalize_transcript_text(call_transcript: Any) -> str:
    """Convert transcript payload into clean plain text dialogue."""
    transcript: str
    if isinstance(call_transcript, list):
        lines = []
        for entry in call_transcript:
            if isinstance(entry, dict):
                speaker = str(entry.get("speaker", "Unknown")).strip()
                dialogue = str(entry.get("dialogue", "")).strip()
                if dialogue:
                    lines.append(f"{speaker}: {dialogue}")
            else:
                text = str(entry).strip()
                if text:
                    lines.append(text)
        transcript = "\n".join(lines)
    elif isinstance(call_transcript, str):
        text = call_transcript.strip()
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return _normalize_transcript_text(parsed)
            if isinstance(parsed, dict):
                nested = parsed.get("call_transcript") or parsed.get("transcript") or parsed
                return _normalize_transcript_text(nested)
        except Exception:
            pass
        transcript = text
    else:
        transcript = str(call_transcript).strip()

    # If transcript is malformed "quoted lines" block without commas, recover quoted lines.
    if ('"' in transcript) and ("\n" in transcript) and ("Advisor:" not in transcript and "Client:" not in transcript):
        quoted_lines = re.findall(r'"([^"\n]+)"', transcript)
        if quoted_lines:
            transcript = "\n".join(line.strip() for line in quoted_lines if line.strip())

    # Strip scene markers and screenplay-style headings.
    cleaned_lines: List[str] = []
    for line in transcript.splitlines():
        stripped = line.strip().strip("()")
        if not stripped:
            continue
        upper = stripped.upper()
        if upper in {"[SCENE START]", "[SCENE END]"}:
            continue
        if re.match(r"^(INT|EXT)\.\s+.+\s+-\s+(DAY|NIGHT|EVENING|MORNING)$", upper):
            continue
        cleaned_lines.append(stripped)

    return "\n".join(cleaned_lines).strip()


# ============================================================================
# Core Gemini-powered generation
# ============================================================================


def generate_client_universe_with_gemini(
    gemini_client, client_id: int, used_names: set = None
) -> Dict[str, Any]:
    """
    Generate a complete client universe using Gemini.

    Returns a dict with:
    - name: Full name (unique, not in used_names set)
    - segment: Client segment (Core, Affluent, HNW, UHNW)
    - risk_profile: Risk tolerance
    - aum: AUM in dollars
    - assets: List of asset allocations
    - goals: Investment goals (detailed, 3-4 sentences)
    - has_alert: Boolean (30% true)
    - scenario: Scenario key if has_alert, else None
    """
    if used_names is None:
        used_names = set()

    prompt = f"""Generate a unique, realistic Canadian investor universe. Return ONLY JSON (no markdown):

{{
  "name": "<Full Canadian name (first and last)>",
  "segment": "<Core|Affluent|HNW|UHNW>",
  "risk_profile": "<Conservative|Balanced|Growth|Aggressive>",
  "aum": <number from 50000 to 3000000>,
  "goals": "<3-4 detailed sentences about specific investment goals, life motivations, and financial priorities>",
  "assets": [
    {{"ticker": "<Canadian ETF or mutual fund>", "asset_class": "<Equity|Fixed Income|Cash>", "percentage": <0-100>}},
    ...
  ],
  "has_alert": <true or false with 30% probability>,
  "scenario": "<if has_alert, one of: {SCENARIO_KEYS_PROMPT}, else null>"
}}

Requirements:
- name: Unique Canadian context (use surnames like Smith, Chen, Kumar, O'Brien, Bouchard, etc.) - MUST BE DIFFERENT FROM PREVIOUS
- segment: Distribute realistically (60% Core, 25% Affluent, 10% HNW, 5% UHNW)
- aum: Scale to segment (Core: 50k-300k, Affluent: 300k-800k, HNW: 800k-2M, UHNW: 2M+)
- goals: DETAILED (3-4 full sentences). Examples:
  * "I'm planning to retire in 15 years and want to build a diversified portfolio that balances growth with stability. My primary focus is on Canadian dividend-paying stocks and fixed income to generate passive income during retirement. I'm also concerned about tax efficiency and want to maximize my RRSP contributions while taking advantage of TFSA room."
  * "We're saving for our children's post-secondary education and want a balanced approach that grows our RESP while protecting our lifestyle. Our business generates variable income, so we need flexibility in cash flow management. Estate planning is also important as we want to ensure wealth transfer to the next generation."
- assets: Canadian-focused (VFV, VSP, VUN, XIC, XGB, XBB, VAB, VBG, ZCS, ZSP, HXU, HBAL, XBAL, etc.)
- has_alert: Exactly 30% should be true (vary the decision, don't always false or always true)
- scenario: Only set if has_alert=true
"""

    try:
        response = generate_with_retry(
            lambda: gemini_client.models.generate_content(
                model="gemini-2.5-flash-lite",
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.9),
            )
        )

        if not response or not response.text:
            raise ValueError("Empty response from Gemini")

        raw_text = response.text.strip()
        # Strip markdown code fences if present
        if raw_text.startswith("```"):
            raw_text = "\n".join(
                [
                    line
                    for line in raw_text.splitlines()
                    if not line.strip().startswith("```")
                ]
            ).strip()

        parsed = json.loads(raw_text)
        return parsed
    except Exception as e:
        print(f"   ERROR generating universe with Gemini: {e}")
        # Return a fallback universe
        fallback_risk = random.choice(RISK_PROFILES)
        fallback_equity, fallback_fixed_income, fallback_cash = _target_allocations_for_profile(
            fallback_risk
        )
        return {
            "name": f"Client {client_id}",
            "segment": random.choice(SEGMENTS),
            "risk_profile": fallback_risk,
            "aum": _non_round_dollar_amount(50_000, 2_000_000),
            "goals": "Long-term wealth accumulation and retirement planning",
            "assets": [
                {"ticker": "XBAL", "asset_class": "Equity", "percentage": fallback_equity},
                {"ticker": "XBB", "asset_class": "Fixed Income", "percentage": fallback_fixed_income},
                {"ticker": "CASH-CA", "asset_class": "Cash", "percentage": fallback_cash},
            ],
            "has_alert": random.random() < 0.30,
            "scenario": None,
        }


def generate_scenario_meeting_notes_with_gemini(
    gemini_client,
    client_name: str,
    risk_profile: str,
    scenario: Dict[str, Any],
    timeline_index: int,
    total_in_timeline: int,
) -> Tuple[str, str]:
    """
    Generate a meeting note and transcript for a specific point in a scenario timeline.

    Args:
        timeline_index: 0 = initial, 1 = follow-up, 2 = final
        total_in_timeline: How many notes total for this scenario
    """
    scenario_label = scenario["label"]
    scenario_desc = scenario["description"]

    if timeline_index == 0:
        meeting_type_desc = "initial planning meeting"
    elif timeline_index == total_in_timeline - 1:
        meeting_type_desc = "final review call"
    else:
        meeting_type_desc = "follow-up check-in"

    prompt = f"""Generate a realistic advisor-client {meeting_type_desc} transcript for:
- Client: {client_name}, {risk_profile} investor
- Scenario: {scenario_label}
- Description: {scenario_desc}
- Timeline: Meeting {timeline_index + 1} of {total_in_timeline}

Requirements:
- Natural dialogue between advisor and client
- Realistic Canadian context (RRSP, TFSA, tax strategies, etc.)
- Specific details (names, amounts, dates)
- Action items and next steps
- DO NOT include screenplay markers or scene headings (no "INT.", "EXT.", "[Sound ...]").

Return ONLY JSON (no markdown):
{{
  "note_body": "<1-2 paragraphs summarizing the meeting>",
  "call_transcript": "<realistic advisor-client conversation>"
}}
"""

    try:
        response = generate_with_retry(
            lambda: gemini_client.models.generate_content(
                model="gemini-2.5-flash-lite",
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.9),
            )
        )

        if not response or not response.text:
            raise ValueError("Empty response from Gemini")

        parsed = _extract_json_object(response.text)
        note_body = str(parsed.get("note_body", "")).strip()
        call_transcript = _normalize_transcript_text(parsed.get("call_transcript", ""))

        return note_body, call_transcript
    except Exception as e:
        print(f"   ERROR generating meeting note with Gemini: {e}")
        return "", ""


# ============================================================================
# Fallback templates
# ============================================================================


def generate_fallback_meeting_note(
    client_name: str, scenario: Dict[str, Any], timeline_index: int, total_in_timeline: int
) -> Tuple[str, str]:
    """Generate a fallback meeting note if Gemini unavailable."""
    scenario_label = scenario["label"]

    if timeline_index == 0:
        note_body = (
            f"Initial planning meeting with {client_name} regarding {scenario_label}. "
            f"Discussed client situation and drafted action plan. Next steps identified."
        )
        transcript = (
            f"Advisor: Good morning, {client_name}! Thanks for coming in today. "
            f"Let's discuss your {scenario_label} situation. "
            f"Client: Yes, I'm looking forward to getting your advice. "
            f"Advisor: Let me walk you through some options. "
            f"Client: That sounds great. What do you recommend? "
            f"Advisor: Let's start by reviewing your current situation and timeline."
        )
    elif timeline_index == total_in_timeline - 1:
        note_body = (
            f"Final review call with {client_name} to finalize {scenario_label} strategy. "
            f"All action items confirmed and next review scheduled."
        )
        transcript = (
            f"Advisor: {client_name}, following up on our plan. "
            f"Client: Yes, I'm ready to move forward. "
            f"Advisor: Excellent. Let's confirm the steps we discussed. "
            f"Client: When will we review this again? "
            f"Advisor: I'll schedule a follow-up in 3 months to ensure everything is on track."
        )
    else:
        note_body = (
            f"Follow-up check-in with {client_name} on {scenario_label} progress. "
            f"Portfolio adjustments in progress, on track with timeline."
        )
        transcript = (
            f"Advisor: {client_name}, just checking in on our {scenario_label} plan. "
            f"Client: Things are going well, thanks for following up. "
            f"Advisor: Great to hear. Any questions or concerns? "
            f"Client: I had one question about the timing. "
            f"Advisor: Of course, let's discuss that."
        )

    return note_body, transcript


# ============================================================================
# Database operations
# ============================================================================


def reset_database() -> None:
    """Reset the entire database."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def _account_tier_for_aum(aum: float) -> str:
    """Assign account tier based on AUM."""
    if aum < 100_000:
        return "Core"
    elif aum < 500_000:
        return "Premium"
    else:
        return "Generation"


def _non_round_dollar_amount(min_amount: int, max_amount: int) -> int:
    """Generate a dollar amount that avoids obvious round-number endings."""
    amount = random.randint(min_amount, max_amount)
    if amount % 100 != 0:
        return amount

    for _ in range(20):
        delta = random.choice([11, 27, 37, 53, 71, 89, 97])
        candidate = amount + delta if random.random() < 0.5 else amount - delta
        if min_amount <= candidate <= max_amount and candidate % 100 != 0:
            return candidate

    for _ in range(100):
        candidate = random.randint(min_amount, max_amount)
        if candidate % 100 != 0:
            return candidate

    return amount


def _normalize_non_round_aum(
    value: Any, min_amount: int = 50_000, max_amount: int = 3_000_000
) -> int:
    """Normalize potentially messy AUM input into a bounded, non-round integer amount."""
    try:
        amount = int(float(value))
    except (TypeError, ValueError):
        amount = _non_round_dollar_amount(min_amount, max_amount)

    bounded = max(min_amount, min(max_amount, amount))
    if bounded % 100 != 0:
        return bounded
    return _non_round_dollar_amount(min_amount, max_amount)


def _format_approx_amount(min_k: int, max_k: int) -> str:
    """Format an approximate amount using exact dollars instead of rounded 'k' values."""
    amount = _non_round_dollar_amount(min_k * 1_000, max_k * 1_000)
    return f"${amount:,}"


def _target_allocations_for_profile(profile: str) -> Tuple[float, float, float]:
    """Get target allocations for a risk profile."""
    base_allocations = {
        "Conservative": (40.0, 50.0, 10.0),
        "Balanced": (60.0, 30.0, 10.0),
        "Growth": (75.0, 20.0, 5.0),
        "Aggressive": (85.0, 12.0, 3.0),
    }

    base_equity, base_fixed_income, _ = base_allocations.get(profile, (85.0, 12.0, 3.0))
    equity = round(base_equity + random.uniform(-2.4, 2.4), 1)
    fixed_income = round(base_fixed_income + random.uniform(-2.0, 2.0), 1)
    cash = round(100.0 - equity - fixed_income, 1)

    if cash < 1.0:
        fixed_income = round(max(1.0, fixed_income - (1.0 - cash)), 1)
    elif cash > 20.0:
        fixed_income = round(fixed_income + (cash - 20.0), 1)

    cash = round(100.0 - equity - fixed_income, 1)
    return equity, fixed_income, cash


def _create_positions_for_portfolio(
    session: Session, portfolio: Portfolio, total_value: Decimal, assets: Optional[List[Dict]] = None
) -> None:
    """Create positions for a portfolio."""
    if assets is None:
        # Fallback: generate random positions
        min_positions = 5
        max_positions = 12
        num_positions = random.randint(min_positions, max_positions)

        raw_weights = [random.random() for _ in range(num_positions)]
        total_raw = sum(raw_weights)
        weights = [w / total_raw for w in raw_weights]

        tickers = [
            "VFV",
            "VSP",
            "VUN",
            "XIC",
            "XGB",
            "XBB",
            "VAB",
            "VBG",
            "ZCS",
            "ZSP",
            "HBAL",
            "XBAL",
        ]
        asset_classes_list = ["Equity", "Equity", "Equity", "Fixed Income", "Cash"]

        for weight in weights:
            ticker = random.choice(tickers)
            asset_class = random.choice(asset_classes_list)
            value = total_value * Decimal(weight)

            position = Position(
                portfolio_id=portfolio.id,
                ticker=ticker,
                asset_class=asset_class,
                weight=float(weight),
                value=value,
            )
            session.add(position)
    else:
        # Use provided assets
        for asset in assets:
            ticker = asset.get("ticker", "XBAL")
            asset_class = asset.get("asset_class", "Equity")
            percentage = asset.get("percentage", 1.0) / 100.0  # Convert from percentage

            value = total_value * Decimal(percentage)

            position = Position(
                portfolio_id=portfolio.id,
                ticker=ticker,
                asset_class=asset_class,
                weight=float(percentage),
                value=value,
            )
            session.add(position)


def seed_client_universes(session: Session, count: int = 70, use_gemini: bool = True) -> None:
    """
    Seed complete client universes.

    Each universe includes:
    - Client with generated name, segment, risk profile, AUM
    - Portfolio(s) with generated asset allocation
    - Optional alert (30% probability)
    - If alert: Scenario with linear progression of meeting notes
    - Auto-summarized transcripts for all meeting notes
    """
    print(f"\n[SEEDING CLIENT UNIVERSES]")
    print(f"Generating {count} clients")
    print(f"Gemini available: {GEMINI_AVAILABLE}")
    print(f"Using Gemini: {use_gemini and GEMINI_AVAILABLE}")
    print(f"Provider env: {os.getenv('PROVIDER', 'mock')}")
    print(f"GEMINI_API_KEY set: {bool(os.getenv('GEMINI_API_KEY', '').strip())}")
    print(f"Loaded env file: {BASE_DIR / '.env'}\n")

    now = datetime.utcnow()
    started_at = time.perf_counter()
    ai_provider = MockAIProvider()

    # Initialize Gemini if available and enabled
    gemini_client = None
    if GEMINI_AVAILABLE and use_gemini:
        gemini_api_key = os.getenv("GEMINI_API_KEY")
        if gemini_api_key:
            gemini_client = genai.Client(api_key=gemini_api_key)
            print("Gemini client initialized for universe generation\n")
        else:
            print("WARNING: GEMINI_API_KEY not set, will use fallback generation\n")

    # Create a single Run for all seeded alerts
    run = Run(started_at=now, provider_used="seed", alerts_created=0)
    session.add(run)
    session.flush()

    created_clients = 0
    created_alerts = 0
    created_notes = 0
    used_names = set()  # Track names to avoid duplicates

    for i in range(count):
        try:
            if i == 0 or (i + 1) % 5 == 0:
                elapsed = time.perf_counter() - started_at
                print(f"[{i+1}/{count}] Processing client universe... ({elapsed:.1f}s elapsed)")

            # Generate complete universe with Gemini or fallback
            universe = None

            if gemini_client and use_gemini:
                universe = generate_client_universe_with_gemini(gemini_client, i + 1)
                time.sleep(1)  # Rate limit
            else:
                # Fallback: generate universe with local name generation
                first = random.choice(FIRST_NAMES)
                last = random.choice(LAST_NAMES)
                name = f"{first} {last}"

                # Ensure unique name in fallback mode
                attempts = 0
                while name in used_names and attempts < 50:
                    first = random.choice(FIRST_NAMES)
                    last = random.choice(LAST_NAMES)
                    name = f"{first} {last}"
                    attempts += 1

                fallback_risk = random.choice(RISK_PROFILES)
                fallback_equity, fallback_fixed_income, fallback_cash = _target_allocations_for_profile(
                    fallback_risk
                )
                universe = {
                    "name": name,
                    "segment": random.choice(SEGMENTS),
                    "risk_profile": fallback_risk,
                    "aum": _non_round_dollar_amount(50_000, 2_000_000),
                    "goals": "Building long-term wealth through disciplined investing and regular portfolio reviews. Planning for retirement with a focus on tax-efficient strategies and diversification across Canadian and international markets. I want to maximize tax-efficient withdrawals and ensure my portfolio continues to grow even during market downturns.",
                    "assets": [
                        {"ticker": "XBAL", "asset_class": "Equity", "percentage": fallback_equity},
                        {"ticker": "XBB", "asset_class": "Fixed Income", "percentage": fallback_fixed_income},
                        {"ticker": "CASH-CA", "asset_class": "Cash", "percentage": fallback_cash},
                    ],
                    "has_alert": random.random() < 0.30,
                    "scenario": None,
                }

            # Check if name is unique and handle duplicates
            if universe:
                client_name = universe.get("name", f"Client {i + 1}")
                if client_name in used_names:
                    print(f"   [DUPLICATE] Name '{client_name}' already used, generating replacement...")
                    # Generate a unique name locally to replace the duplicate
                    first = random.choice(FIRST_NAMES)
                    last = random.choice(LAST_NAMES)
                    replacement_name = f"{first} {last}"
                    attempts = 0
                    while replacement_name in used_names and attempts < 50:
                        first = random.choice(FIRST_NAMES)
                        last = random.choice(LAST_NAMES)
                        replacement_name = f"{first} {last}"
                        attempts += 1

                    if replacement_name not in used_names:
                        universe["name"] = replacement_name
                        client_name = replacement_name
                        print(f"   [REPLACEMENT] Using '{replacement_name}' instead")
                    else:
                        print(f"   [ERROR] Could not find unique name, skipping client {i + 1}")
                        continue

                used_names.add(client_name)
            else:
                print(f"   [ERROR] Could not generate universe for client {i + 1}, skipping")
                continue
            segment = universe.get("segment", "Core")
            risk_profile = universe.get("risk_profile", "Balanced")
            aum = _normalize_non_round_aum(universe.get("aum", 500000), 50_000, 3_000_000)
            goals = universe.get("goals", "Wealth accumulation")
            assets = universe.get("assets", [])
            has_alert = universe.get("has_alert", False)
            scenario_key = universe.get("scenario", None)

            # Create client
            client = Client(
                name=client_name,
                email=f"{client_name.lower().replace(' ', '.')}{i+1}@example.internal",
                segment=segment,
                risk_profile=risk_profile,
                account_tier=_account_tier_for_aum(aum),
                created_at=now - timedelta(days=random.randint(30, 365 * 5)),
            )
            session.add(client)
            session.flush()
            created_clients += 1

            # Create portfolio with generated assets
            total_value = Decimal(aum)
            target_equity, target_fixed_income, target_cash = _target_allocations_for_profile(
                risk_profile
            )

            portfolio = Portfolio(
                client_id=client.id,
                name="Primary Portfolio",
                total_value=total_value,
                target_equity_pct=target_equity,
                target_fixed_income_pct=target_fixed_income,
                target_cash_pct=target_cash,
            )
            session.add(portfolio)
            session.flush()

            # Create positions
            _create_positions_for_portfolio(session, portfolio, total_value, assets)

            # If client has alert, create it with scenario
            alert = None
            if has_alert and scenario_key:
                # Find the scenario
                scenario = None
                for s in SCENARIOS:
                    if s["key"] == scenario_key:
                        scenario = s
                        break

                if scenario:
                    # Create alert with detailed description
                    priority = random.choice(
                        [Priority.HIGH, Priority.HIGH, Priority.MEDIUM, Priority.LOW]
                    )  # 50% HIGH
                    confidence = random.randint(70, 95)

                    # Generate detailed alert summary based on scenario
                    scenario_summaries = {
                        "EDUCATION_WITHDRAWAL": f"{client_name}'s child is approaching post-secondary education with an estimated start date within 8-12 months. The current portfolio allocation may expose education funds to unnecessary volatility given the near-term withdrawal needs. We recommend gradually shifting the designated education portion (approximately {_format_approx_amount(20, 100)}) to a more conservative allocation to protect against market downturns and lock in current asset values.",
                        "TAX_LOSS_HARVESTING": f"With the tax year approaching its end, {client_name}'s portfolio contains {_format_approx_amount(10, 80)} in unrealized losses that can be strategically harvested to offset capital gains and reduce overall tax liability. This window is time-sensitive and closes December 31st. Prompt action is needed to execute these trades while maintaining desired asset exposure through substitute holdings.",
                        "HOME_PURCHASE": f"{client_name} is planning a home purchase in 12-18 months with an estimated down payment requirement of {_format_approx_amount(50, 300)}. The current portfolio allocation exposes these funds to significant market volatility. We recommend establishing a dedicated, conservative portfolio for the down payment funds while maintaining growth-oriented allocations for longer-term goals.",
                        "RETIREMENT_DRAWDOWN": f"{client_name} has recently transitioned from an accumulation phase to retirement drawdown. The portfolio structure is not optimized for generating sustainable income while managing sequence of returns risk. We recommend restructuring to include a 2-3 year cash reserve, laddered fixed income, and a balanced equity allocation for long-term growth.",
                        "INHERITANCE_WINDFALL": f"{client_name} recently received an inheritance of approximately {_format_approx_amount(100, 1000)}. The current portfolio structure is not designed to efficiently absorb and deploy capital of this magnitude. A systematic deployment plan over 6-12 months can help optimize average entry prices and manage market timing risk.",
                        "MARGIN_CALL_RISK": f"{client_name}'s leveraged position is at elevated risk given current market conditions. Recent volatility has brought the margin ratio dangerously close to triggering a forced liquidation. Immediate action to reduce leverage by {_format_approx_amount(50, 300)} is critical to protect the portfolio from forced sales at unfavorable prices.",
                        "CONCENTRATED_STOCK_POSITION": f"{client_name}'s largest holding has appreciated to a level that now represents a disproportionate share of total portfolio risk. This concentration creates downside vulnerability if the single name experiences a drawdown. We recommend a staged de-risking plan to reduce exposure by {_format_approx_amount(30, 180)} while managing taxes and preserving long-term growth objectives.",
                        "BUSINESS_EXIT_LIQUIDITY_EVENT": f"{client_name} is preparing for a business sale that is expected to generate significant liquidity in the coming quarters. Without a structured deployment plan, idle cash drag and timing risk could materially affect long-term outcomes. We recommend a phased investment policy with short-term reserves and scheduled deployment of {_format_approx_amount(200, 1500)} into diversified mandates.",
                        "CROSS_BORDER_RELOCATION": f"{client_name} is planning a cross-border relocation, introducing new tax residency and currency-management considerations. The current portfolio is not optimized for withholding tax exposure, account-structure portability, or FX volatility. A transition plan should reposition assets and build a currency hedge framework ahead of relocation timelines.",
                        "CHARITABLE_GIVING_STRATEGY": f"{client_name} intends to make a meaningful charitable contribution in the near term and is evaluating donation methods. Donating appreciated securities could improve after-tax outcomes versus donating cash, but requires coordinated asset selection and timing. We recommend pre-identifying eligible lots and a gifting schedule to maximize impact while preserving portfolio balance.",
                        "ESTATE_FREEZE_PLANNING": f"{client_name} has begun estate freeze and intergenerational transfer planning, which changes liquidity and tax priorities across account types. Current allocations may not align with upcoming trust, corporate-share, and succession structures. We recommend re-segmenting assets by horizon and risk budget to support the estate strategy while maintaining portfolio resilience.",
                        "INTEREST_RATE_REFINANCE_WINDOW": f"Recent rate movements have created a refinance decision point for {client_name}, affecting monthly cash flow and liquidity buffers. The existing portfolio does not currently reflect the revised short-term cash requirements and rate sensitivity. We recommend a temporary liquidity sleeve and targeted rebalancing to support financing decisions without compromising core long-term allocation.",
                        "DIVORCE_SETTLEMENT_REBALANCE": f"{client_name} has completed a divorce settlement and now requires a full post-settlement portfolio redesign. Asset ownership, liquidity timing, and updated goals have materially changed risk capacity and drawdown requirements. We recommend re-mapping accounts into a new strategic allocation and building a near-term liquidity buffer of {_format_approx_amount(30, 160)}.",
                        "RSU_VESTING_TAX_MANAGEMENT": f"{client_name} has significant RSU vesting events approaching over the next two quarters, creating concentration and tax withholding complexity. Without a plan, post-vest exposure could exceed risk limits and increase tax drag. We recommend a staged sell policy with explicit tax-lot handling and systematic diversification of {_format_approx_amount(40, 220)}.",
                        "PENSION_COMMUTATION_DECISION": f"{client_name} is evaluating whether to commute a defined-benefit pension or accept lifetime annuitized payments. This decision materially impacts longevity risk, liquidity flexibility, and required portfolio return assumptions. We recommend scenario testing both paths and preparing an allocation policy tied to the chosen income structure.",
                        "CURRENCY_HEDGE_REVIEW": f"{client_name}'s foreign equity exposure has risen materially, increasing sensitivity to CAD currency swings. The current hedge ratio may no longer align with risk objectives or spending currency needs. We recommend re-establishing a target hedge corridor and rebalancing FX exposure using a phased implementation schedule.",
                        "PRIVATE_MARKET_LIQUIDITY_LOCKUP": f"{client_name} has increased private-market allocations with multi-year lockups, reducing portfolio liquidity flexibility. Upcoming cash needs may now conflict with the current lockup profile and distribution timelines. We recommend a liquidity stress test and rebalancing public sleeves to create an accessible reserve of {_format_approx_amount(60, 260)}.",
                        "CRITICAL_ILLNESS_CONTINGENCY": f"{client_name} is implementing a critical illness contingency plan requiring higher short-term liquidity and reduced drawdown risk. Current allocation assumes longer horizons and may not support sudden cash needs. We recommend a defensive rebalance with a dedicated contingency reserve and lower volatility positioning.",
                        "DRAWDOWN_SEQUENCE_RISK": f"{client_name} has entered early drawdown, and current withdrawal rates make the portfolio vulnerable to sequence-of-returns shocks. A market decline in the next 12-24 months could materially impair sustainability. We recommend a bucket strategy with near-term cash/fixed-income funding and adjusted equity risk budgets.",
                        "ALTERNATIVE_ASSET_OVEREXPOSURE": f"{client_name}'s alternatives sleeve has grown beyond policy limits due to strong performance and new commitments. The resulting allocation drift reduces transparency and complicates liquidity forecasting. We recommend a disciplined rebalance program to bring alternatives back within mandate while preserving long-term diversification benefits.",
                    }

                    # Generate realistic "change detection" from state
                    prior_states = [
                        "standard allocation",
                        "balanced portfolio",
                        "normal structure",
                        "unchanged status",
                        "maintenance mode",
                        "baseline configuration",
                        "typical positioning",
                    ]
                    prior_state = random.choice(prior_states)

                    detailed_summary = scenario_summaries.get(
                        scenario_key,
                        f"{client_name} requires portfolio review and adjustment regarding {scenario['label']}. Meeting recommended to discuss strategy and next steps."
                    )

                    alert = Alert(
                        run_id=run.id,
                        portfolio_id=portfolio.id,
                        client_id=client.id,
                        created_at=now - timedelta(days=random.randint(1, 10)),
                        priority=priority,
                        confidence=confidence,
                        event_title=f"{scenario['label']} - Portfolio Review Required",
                        summary=detailed_summary,
                        reasoning_bullets=[
                            f"Scenario: {scenario['label']}",
                            scenario["description"],
                            f"Current AUM: ${float(portfolio.total_value):,.0f}",
                            f"Risk Profile: {client.risk_profile}",
                            "Advisor review and client discussion recommended to align portfolio with current life circumstances",
                        ],
                        human_review_required=True,
                        suggested_next_step=f"Schedule comprehensive meeting with {client_name} to discuss {scenario['label'].lower()} strategy and implement recommendations",
                        decision_trace_steps=[
                            {"step": "Detection", "detail": f"{scenario['label']} event identified in client profile"},
                            {"step": "Assessment", "detail": f"Current portfolio allocation may not be optimal for {scenario['label'].lower()} scenario"},
                            {"step": "Analysis", "detail": f"Analyzing {client.risk_profile} portfolio against {scenario['label']} requirements"},
                            {"step": "Recommendation", "detail": "Advisor meeting required to discuss adjustments and implementation timeline"},
                        ],
                        change_detection=[
                            {
                                "metric": "life_event_status",
                                "from": prior_state,
                                "to": scenario['label']
                            }
                        ],
                        status=AlertStatus.OPEN,
                        concentration_score=random.uniform(2, 8),
                        drift_score=random.uniform(2, 9),
                        volatility_proxy=random.uniform(1, 8),
                        risk_score=random.uniform(2, 8),
                        scenario=scenario_key,
                    )
                    session.add(alert)
                    session.flush()
                    created_alerts += 1

            # Create meeting notes for this client
            # Case 1: Client has alert with scenario -> linear progression
            if has_alert and scenario_key and alert:
                scenario = None
                for s in SCENARIOS:
                    if s["key"] == scenario_key:
                        scenario = s
                        break

                if scenario:
                    timeline_days = scenario.get("timeline_days", [0, 30, 60])

                    for timeline_idx, days_offset in enumerate(timeline_days):
                        meeting_date = now - timedelta(days=days_offset)

                        # Generate meeting note and transcript
                        if gemini_client and use_gemini:
                            note_body, call_transcript = generate_scenario_meeting_notes_with_gemini(
                                gemini_client,
                                client_name,
                                risk_profile,
                                scenario,
                                timeline_idx,
                                len(timeline_days),
                            )
                            time.sleep(1)  # Rate limit

                            if not note_body or not call_transcript:
                                note_body, call_transcript = generate_fallback_meeting_note(
                                    client_name, scenario, timeline_idx, len(timeline_days)
                                )
                        else:
                            note_body, call_transcript = generate_fallback_meeting_note(
                                client_name, scenario, timeline_idx, len(timeline_days)
                            )

                        # Auto-summarize transcript
                        ai_summary = ""
                        action_items = []
                        if call_transcript and isinstance(call_transcript, str) and call_transcript.strip():
                            summary_result = ai_provider.summarize_transcript(
                                transcript=call_transcript,
                                context={
                                    "client_name": client_name,
                                    "risk_profile": risk_profile,
                                    "scenario": scenario["label"],
                                },
                            )
                            ai_summary = summary_result.summary_paragraph
                            action_items = (
                                summary_result.action_items
                                if isinstance(summary_result.action_items, list)
                                else []
                            )

                        # Ensure action_items is a list
                        if not isinstance(action_items, list):
                            action_items = []

                        # Create meeting note
                        meeting_note = MeetingNote(
                            client_id=client.id,
                            title=f"{scenario['label']} - {['Planning', 'Follow-up', 'Review'][min(timeline_idx, 2)]}",
                            meeting_date=meeting_date,
                            note_body=note_body or f"Meeting regarding {scenario['label']}",
                            meeting_type=MeetingNoteType.PHONE_CALL,
                            call_transcript=str(call_transcript) if call_transcript else "",
                            ai_summary=ai_summary,
                            ai_action_items=action_items,
                            ai_summarized_at=datetime.utcnow() if ai_summary else None,
                            ai_provider_used="mock",
                        )
                        session.add(meeting_note)
                        created_notes += 1

            else:
                # Case 2: Client without alert -> create at least 1 generic meeting note
                meeting_date = now - timedelta(days=random.randint(1, 60))

                note_body = (
                    f"Quarterly review with {client_name}. Reviewed portfolio performance and discussed investment goals. "
                    f"{goals}"
                )
                call_transcript = (
                    f"Advisor: {client_name}, thanks for meeting with me today. Let's review your portfolio. "
                    f"Client: Sure, how have my investments been doing? "
                    f"Advisor: Overall, your portfolio is performing well and aligned with your goals. "
                    f"Client: That's good to hear. Do you have any recommendations? "
                    f"Advisor: Let's discuss your current allocation and make sure it still matches your objectives."
                )

                # Auto-summarize
                summary_result = ai_provider.summarize_transcript(
                    transcript=call_transcript,
                    context={
                        "client_name": client_name,
                        "risk_profile": risk_profile,
                        "scenario": "Quarterly Review",
                    },
                )

                # Ensure action items is a list
                action_items_list = (
                    summary_result.action_items
                    if isinstance(summary_result.action_items, list)
                    else []
                )

                meeting_note = MeetingNote(
                    client_id=client.id,
                    title="Quarterly Portfolio Review",
                    meeting_date=meeting_date,
                    note_body=note_body,
                    meeting_type=MeetingNoteType.PHONE_CALL,
                    call_transcript=str(call_transcript) if call_transcript else "",
                    ai_summary=summary_result.summary_paragraph,
                    ai_action_items=action_items_list,
                    ai_summarized_at=datetime.utcnow(),
                    ai_provider_used="mock",
                )
                session.add(meeting_note)
                created_notes += 1

            # Batch commit every 10 clients
            if (i + 1) % 10 == 0:
                session.flush()
                session.commit()
                print(
                    f"[{i+1}/{count}] Batch committed: {created_clients} clients, "
                    f"{created_alerts} alerts, {created_notes} notes"
                )

        except Exception as e:
            print(f"ERROR processing client {i+1}: {e}")
            session.rollback()
            continue

    # Final commit
    run.alerts_created = created_alerts
    session.flush()
    session.commit()

    print(
        f"\n[SEEDING COMPLETE] {created_clients} clients, "
        f"{created_alerts} alerts, {created_notes} meeting notes\n"
    )


# ============================================================================
# Main entry point
# ============================================================================


def main() -> None:
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Seed database with complete client universes using Gemini-powered generation."
    )
    parser.add_argument("--clients", type=int, default=70, help="Number of clients to generate")
    parser.set_defaults(gemini_enabled=True)
    parser.add_argument(
        "--gemini-enabled",
        action="store_true",
        dest="gemini_enabled",
        help="Enable Gemini for unique generation (default: enabled).",
    )
    parser.add_argument(
        "--no-gemini",
        action="store_false",
        dest="gemini_enabled",
        help="Disable Gemini and use fallback generation.",
    )
    args = parser.parse_args()

    reset_database()
    session = SessionLocal()

    try:
        seed_client_universes(session, count=args.clients, use_gemini=args.gemini_enabled)
        print("[SEED SUCCESS] Database ready for Wealthsimple Operator\n")
    except Exception as e:
        print(f"[SEED ERROR] {e}\n")
        session.rollback()
    finally:
        session.close()


if __name__ == "__main__":
    main()
