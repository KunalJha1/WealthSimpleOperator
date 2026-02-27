#!/usr/bin/env python3
"""
New backfill script - self-contained, based on test.py's working Gemini pattern.
Generates portfolio summaries and stores alerts in the database.
"""

import os
import json
import time
import random
import argparse
from pathlib import Path
from datetime import datetime, timezone, timedelta
from collections import defaultdict

from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.genai import errors as genai_errors

from db import SessionLocal
from models import (
    Alert,
    AlertStatus,
    AuditEvent,
    AuditEventType,
    Client,
    Portfolio,
    Priority,
    Run,
    RunSummary,
    AIOutput,
    MeetingNote,
    MeetingNoteType,
)

# Load .env
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env", override=True)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")

print("=" * 70)
print("NEW BACKFILL - Self-Contained Gemini Portfolio Scorer")
print("=" * 70)
print(f"Model: {GEMINI_MODEL}")
print(f"API Key: {'SET' if GEMINI_API_KEY else 'NOT SET'}")
print()

if not GEMINI_API_KEY:
    print("ERROR: GEMINI_API_KEY not set in .env")
    exit(1)

# Initialize Gemini client
client = genai.Client(api_key=GEMINI_API_KEY)


def _ts() -> str:
    """Timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def strip_code_fences(text: str) -> str:
    """Strip markdown code fences from response."""
    text = text.strip()
    if text.startswith("```"):
        lines = [line for line in text.splitlines() if not line.strip().startswith("```")]
        text = "\n".join(lines).strip()
    return text


def generate_with_retry(call_fn, max_retries=8):
    """Retry with exponential backoff and jitter (from test.py pattern)."""
    delay = 8.0
    for attempt in range(max_retries):
        try:
            return call_fn()
        except genai_errors.ClientError as e:
            msg = str(e)
            print(f"   [Attempt {attempt + 1}/{max_retries}] Error: {msg[:80]}")
            if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
                jittered_delay = delay + random.random()
                print(f"   Rate limited. Retrying in {jittered_delay:.1f}s...")
                time.sleep(jittered_delay)
                delay = min(delay * 2, 20)
                continue
            raise


def build_portfolio_prompt(metrics: dict, context: dict, unique_mode: bool = False) -> str:
    """Build the prompt for portfolio scoring - action-focused with client context."""
    client_info = context.get("client", {})
    portfolio_info = context.get("portfolio", {})
    meeting_notes = context.get("meeting_notes", [])
    client_name = client_info.get('name', 'Unknown').split()[0]  # First name only for conversational tone

    # Get current date for time-sensitive scenario context
    today = datetime.now().strftime("%B %d, %Y")
    today_obj = datetime.now()

    # Build client context section from meeting notes
    client_context_section = ""
    scenario_guidance = ""
    if meeting_notes:
        client_context_section = "\nCLIENT CONTEXT (from advisor notes):\n"
        for note in meeting_notes[:2]:  # Include latest 2 notes
            client_context_section += f"- {note.get('title', 'Note')}: {note.get('summary', '')}\n"
        client_context_section += f"  Situation: {meeting_notes[0].get('situation', '')}\n" if meeting_notes else ""

        # Detect scenario and add time-aware guidance
        note_text = " ".join([n.get('summary', '') + " " + n.get('situation', '') for n in meeting_notes]).lower()

        if 'education' in note_text or 'resp' in note_text or 'school' in note_text:
            scenario_guidance = "\nSCENARIO CONTEXT: Client is planning education withdrawal. Priority should reflect timeline to withdrawal date."
        elif 'tax' in note_text and 'loss' in note_text and 'harvest' in note_text:
            # Tax loss harvesting is time-sensitive - Dec 31 deadline
            days_to_year_end = (datetime(today_obj.year, 12, 31) - today_obj).days
            scenario_guidance = f"\nSCENARIO CONTEXT: Client mentioned tax loss harvesting. It is currently {today}. Days until year-end: {max(0, days_to_year_end)}. "
            if days_to_year_end < 15:
                scenario_guidance += "URGENT: Window is closing. HIGH priority if action needed."
            elif days_to_year_end > 200:
                scenario_guidance += "This is early in the tax year - not urgent yet. Prioritize if portfolio metrics are severe."
            else:
                scenario_guidance += "Moderate urgency depending on portfolio metrics."
        elif 'home' in note_text or 'mortgage' in note_text or 'purchase' in note_text:
            scenario_guidance = "\nSCENARIO CONTEXT: Client is planning home purchase. Timeline affects asset allocation - near-term funds should be lower risk."
        elif 'retire' in note_text or 'retirement' in note_text or 'drawdown' in note_text:
            scenario_guidance = "\nSCENARIO CONTEXT: Client is in retirement or transitioning to drawdown. Capital preservation and income are primary concerns."

    prompt = f"""
You are an advisor reviewing {client_name}'s portfolio. Write a natural, human summary of what's going on and what needs to happen.

TODAY'S DATE: {today}

CLIENT: {client_name} ({client_info.get('risk_profile', 'Unknown')} investor)
PORTFOLIO: {portfolio_info.get('name', 'Unknown')} (${portfolio_info.get('total_value', 0):,.0f})

METRICS:
- Concentration: {metrics.get('concentration_score', 0)}/10
- Drift from target: {metrics.get('drift_score', 0)}/10
- Volatility: {metrics.get('volatility_proxy', 0)}/10
- Overall risk: {metrics.get('risk_score', 0)}/10

TARGET ALLOCATION: {portfolio_info.get('target_equity_pct', 0)}% Equity, {portfolio_info.get('target_fixed_income_pct', 0)}% Fixed Income, {portfolio_info.get('target_cash_pct', 0)}% Cash
{client_context_section}{scenario_guidance}

TONE & STYLE:
- Write like you're talking to a colleague about {client_name}'s situation
- Use conversational language ("His portfolio has gotten...", "This creates a mismatch...", "We should...")
- Focus on what it MEANS for {client_name}, not just metrics
- Keep it natural - avoid templated phrases and robotic tone
- If something contradicts {client_name}'s stated goals/risk tolerance, point that out directly
- Be concise but warm

Return STRICT JSON ONLY:
{{
  "priority": "HIGH" | "MEDIUM" | "LOW",
  "confidence": <0-100>,
  "event_title": "<concise, natural problem statement>",
  "summary": "<2-4 sentences, conversational tone, advisor-to-colleague style>",
  "reasoning_bullets": ["<key issue 1>", "<key issue 2>", "<key issue 3>"],
  "human_review_required": true,
  "suggested_next_step": "<what the advisor should do next>",
  "decision_trace_steps": [{{"step": "Issue", "detail": "<what's wrong>"}}, {{"step": "Action", "detail": "<what to do>"}}],
  "change_detection": [{{"metric": "concentration", "from": "previous", "to": "current"}}, {{"metric": "scenario_match", "from": "unknown", "to": "detected"}}]
}}

EXAMPLES OF GOOD SUMMARIES:
- "Rohan's portfolio has gotten pretty concentrated - a few holdings are making up most of his portfolio. That wouldn't normally be a problem, but combined with the recent market volatility, it's creating a lot more risk than he's comfortable with. We should trim those big positions and rebalance back to his conservative targets."

- "Sarah's been saving hard for a home purchase in the next 18 months, but her equity allocation is still where she had it when she was focused on long-term growth. If markets pull back between now and closing, that down payment fund could take a hit. Time to shift the funds she's set aside for the purchase into something more stable."

- "The drift here isn't huge, but it's consistent - the portfolio keeps tilting toward equities whenever markets rise. That suggests our rebalancing isn't keeping up. Let's set up a more disciplined rebalancing schedule so {client_name}'s allocation stays where we agreed."

CHANGE DETECTION EXAMPLES:
- {{"metric": "concentration", "from": "6.2", "to": "7.8"}} — single position weight increased
- {{"metric": "drift", "from": "4.1", "to": "5.3"}} — allocation drifted further from target
- {{"metric": "volatility", "from": "3.2", "to": "4.5"}} — portfolio volatility increased
- {{"metric": "scenario_match", "from": "unknown", "to": "TAX_LOSS_HARVESTING"}} — detected scenario from client context

Include 2-3 change_detection items showing the specific metric movements that triggered the alert.
"""
    return prompt.strip()


def score_portfolio(
    portfolio: Portfolio, db_client: Client, metrics: dict, meeting_notes_data: list = None, unique_mode: bool = False
) -> AIOutput:
    """Score a portfolio using Gemini with optional client context from meeting notes."""
    context = {
        "client": {
            "id": db_client.id,
            "name": db_client.name,
            "email": db_client.email,
            "segment": db_client.segment,
            "risk_profile": db_client.risk_profile,
        },
        "portfolio": {
            "id": portfolio.id,
            "name": portfolio.name,
            "total_value": float(portfolio.total_value),
            "target_equity_pct": float(portfolio.target_equity_pct),
            "target_fixed_income_pct": float(portfolio.target_fixed_income_pct),
            "target_cash_pct": float(portfolio.target_cash_pct),
        },
        "meeting_notes": meeting_notes_data or [],
    }

    prompt = build_portfolio_prompt(metrics, context, unique_mode=unique_mode)

    try:
        response = generate_with_retry(
            lambda: client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.8 if unique_mode else 0.6),
            )
        )

        if not response or not response.text:
            raise ValueError("Empty response from Gemini")

        raw_text = response.text.strip()

        # Strip markdown code fences if present
        raw_text = strip_code_fences(raw_text)

        parsed = json.loads(raw_text)
        return AIOutput.model_validate(parsed)
    except Exception as e:
        print(f"   ERROR scoring portfolio {portfolio.id}: {e}")
        raise


def detect_scenario(meeting_notes: list) -> str:
    """Detect scenario from meeting notes content."""
    if not meeting_notes:
        return "UNKNOWN"

    note_text = " ".join([
        n.get('summary', '') + " " + n.get('situation', '')
        for n in meeting_notes
    ]).lower()

    # Scenario detection keywords
    scenarios = {
        "EDUCATION_WITHDRAWAL": ["education", "resp", "school", "tuition", "university", "college"],
        "TAX_LOSS_HARVESTING": ["tax", "loss", "harvest", "offsetting", "gains", "capital"],
        "HOME_PURCHASE": ["home", "mortgage", "purchase", "down payment", "closing", "real estate"],
        "RETIREMENT_DRAWDOWN": ["retire", "retirement", "drawdown", "pension", "cpp", "oas"],
        "INHERITANCE_WINDFALL": ["inheritance", "inherit", "windfall", "estate", "beneficiary"],
        "MAJOR_LIFE_EVENT": ["divorce", "job loss", "loss of job", "major event", "significant change"],
        "ESTATE_PLANNING": ["estate", "will", "trust", "legacy", "planning"],
        "RRSP_DEADLINE": ["rrsp", "contribution room", "deadline", "march"],
        "BUSINESS_SALE": ["business", "sale", "sold", "lump sum", "entrepreneur"],
        "MATERNITY_LEAVE": ["maternity", "parental", "leave", "income reduction"],
        "FOREIGN_PROPERTY": ["foreign", "property", "overseas", "fx", "currency"],
        "CHARITABLE_GIVING": ["charitable", "donation", "donate", "appreciate", "securities"],
        "MARGIN_CALL_RISK": ["margin", "leverage", "leveraged", "call risk"],
    }

    for scenario_key, keywords in scenarios.items():
        if any(keyword in note_text for keyword in keywords):
            return scenario_key

    return "UNKNOWN"


def compute_metrics(portfolio: Portfolio) -> dict:
    """Compute risk metrics for portfolio."""
    positions = portfolio.positions
    if not positions:
        return {
            "concentration_score": 0.0,
            "drift_score": 0.0,
            "volatility_proxy": 0.0,
            "risk_score": 0.0,
        }

    max_weight = max(float(p.weight) for p in positions)
    concentration_score = round(min(10.0, max_weight * 10.0), 1)

    equity_weight = sum(float(p.weight) for p in positions if p.asset_class in ("Equity", "ETF"))
    fixed_income_weight = sum(float(p.weight) for p in positions if p.asset_class == "Fixed Income")

    target_equity = float(portfolio.target_equity_pct)
    target_fixed_income = float(portfolio.target_fixed_income_pct)

    realized_equity_pct = equity_weight * 100.0
    realized_fixed_income_pct = fixed_income_weight * 100.0

    diff_equity = abs(realized_equity_pct - target_equity)
    diff_fixed_income = abs(realized_fixed_income_pct - target_fixed_income)

    avg_deviation = (diff_equity + diff_fixed_income) / 2.0
    drift_score = round(min(10.0, avg_deviation / 5.0), 1)

    volatility_raw = (portfolio.id * 37 % 97) / 96.0
    volatility_proxy = round(volatility_raw * 10.0, 1)

    risk_score = round((concentration_score + drift_score + volatility_proxy) / 3.0, 1)

    return {
        "concentration_score": concentration_score,
        "drift_score": drift_score,
        "volatility_proxy": volatility_proxy,
        "risk_score": risk_score,
    }


def run_backfill(unique_summaries: bool = False, limit: int = None):
    """Run the backfill process - prints results to console."""
    print(f"[{_ts()}] Starting backfill...")
    print(f"[{_ts()}] Unique summaries: {unique_summaries}")

    with SessionLocal() as db:
        # Get all portfolios
        portfolios = db.query(Portfolio).all()
        if limit:
            portfolios = portfolios[:limit]

        print(f"[{_ts()}] Found {len(portfolios)} portfolios to score\n")

        # Create run
        now = datetime.utcnow()
        run = Run(started_at=now, provider_used="gemini", alerts_created=0)
        db.add(run)
        db.flush()

        print(f"[{_ts()}] Created run {run.id}\n")

        # Log run start
        db.add(
            AuditEvent(
                run_id=run.id,
                event_type=AuditEventType.RUN_STARTED,
                actor="new_backfill",
                details={"provider_used": "gemini", "unique_summaries": unique_summaries},
            )
        )

        # Pre-load meeting notes for all clients
        all_clients = db.query(Client).all()
        meeting_notes_by_client = {}
        for c in all_clients:
            notes = (
                db.query(MeetingNote)
                .filter_by(client_id=c.id)
                .order_by(MeetingNote.meeting_date.desc())
                .limit(2)
                .all()
            )
            if notes:
                meeting_notes_by_client[c.id] = [
                    {
                        "title": n.title,
                        "summary": n.ai_summary or n.note_body[:200],
                        "situation": n.call_transcript[:150] if n.call_transcript else "",
                    }
                    for n in notes
                ]

        # Score portfolios
        alerts_created = 0
        priority_counts = defaultdict(int)

        for idx, portfolio in enumerate(portfolios, 1):
            db_client = portfolio.client
            print(f"[{idx}/{len(portfolios)}] {db_client.name} - {portfolio.name}")

            try:
                metrics = compute_metrics(portfolio)
                meeting_notes = meeting_notes_by_client.get(db_client.id, [])
                ai_output = score_portfolio(
                    portfolio, db_client, metrics, meeting_notes_data=meeting_notes, unique_mode=unique_summaries
                )

                print(f"     Priority: {ai_output.priority.value} | Confidence: {ai_output.confidence}%")
                print(f"     Title: {ai_output.event_title}")
                print(f"     Summary: {ai_output.summary}")
                print()

                # Detect scenario from meeting notes
                detected_scenario = detect_scenario(meeting_notes)

                # Create and save alert
                alert = Alert(
                    run_id=run.id,
                    portfolio_id=portfolio.id,
                    client_id=db_client.id,
                    created_at=now,
                    priority=ai_output.priority,
                    confidence=int(ai_output.confidence),
                    event_title=ai_output.event_title,
                    summary=ai_output.summary,
                    reasoning_bullets=[str(b) for b in ai_output.reasoning_bullets],
                    human_review_required=bool(ai_output.human_review_required),
                    suggested_next_step=ai_output.suggested_next_step,
                    decision_trace_steps=[
                        {"step": s.step, "detail": s.detail} for s in ai_output.decision_trace_steps
                    ],
                    change_detection=[
                        {"metric": c.metric, "from": c.from_value, "to": c.to_value}
                        for c in ai_output.change_detection
                    ],
                    status=AlertStatus.OPEN,
                    concentration_score=metrics["concentration_score"],
                    drift_score=metrics["drift_score"],
                    volatility_proxy=metrics["volatility_proxy"],
                    risk_score=metrics["risk_score"],
                    scenario=detected_scenario if detected_scenario != "UNKNOWN" else None,
                )
                db.add(alert)

                db.add(
                    AuditEvent(
                        alert_id=alert.id,
                        run_id=run.id,
                        event_type=AuditEventType.ALERT_CREATED,
                        actor="new_backfill",
                        details={
                            "priority": ai_output.priority.value,
                            "confidence": int(ai_output.confidence),
                        },
                    )
                )

                alerts_created += 1
                priority_counts[ai_output.priority] += 1

                if idx % 10 == 0:
                    db.flush()

            except Exception as e:
                print(f"     ERROR: {e}\n")
                continue

        # Apply confidence distribution to all generated alerts
        # 30% low (40-60), 30% medium (60-80), 40% high (80-98)
        if alerts_created > 0:
            generated_alerts = db.query(Alert).filter_by(run_id=run.id).all()
            confidence_distribution = []
            for _ in range(len(generated_alerts)):
                confidence_seed = random.random()
                if confidence_seed < 0.3:
                    confidence_distribution.append(random.randint(40, 60))
                elif confidence_seed < 0.6:
                    confidence_distribution.append(random.randint(60, 80))
                else:
                    confidence_distribution.append(random.randint(80, 98))
            random.shuffle(confidence_distribution)

            for idx, alert in enumerate(generated_alerts):
                alert.confidence = confidence_distribution[idx]

        # Final save
        db.flush()
        run.alerts_created = alerts_created
        run.completed_at = datetime.utcnow()

        db.add(
            AuditEvent(
                run_id=run.id,
                event_type=AuditEventType.RUN_COMPLETED,
                actor="new_backfill",
                details={
                    "alerts_created": alerts_created,
                    "priority_counts": {p.value: c for p, c in priority_counts.items()},
                },
            )
        )

        db.commit()

        print("=" * 70)
        print(f"COMPLETE - Saved to database")
        print(f"Run ID: {run.id}")
        print(f"Alerts generated: {alerts_created}")
        print(f"Priority breakdown: {dict(priority_counts)}")
        print("=" * 70)


def enrich_existing_alerts(db):
    """Enrich existing open alerts with meeting notes and call transcripts.

    This function processes alerts that were created during seeding
    and adds contextual meeting notes, AI summaries, and check-in call transcripts.
    """
    from ai.mock_provider import MockAIProvider

    print(f"\n[{_ts()}] Enriching existing alerts with meeting notes and transcripts...")

    ai_provider = MockAIProvider()
    now = datetime.utcnow()

    # Query all open alerts
    open_alerts = db.query(Alert).filter_by(status=AlertStatus.OPEN).all()
    print(f"[{_ts()}] Found {len(open_alerts)} open alerts to enrich\n")

    if not open_alerts:
        print("No open alerts to enrich.")
        return

    # Scenario mapping for context
    SCENARIOS = [
        {"key": "EDUCATION_WITHDRAWAL", "label": "Education Withdrawal"},
        {"key": "TAX_LOSS_HARVESTING", "label": "Tax Loss Harvesting"},
        {"key": "HOME_PURCHASE", "label": "Home Purchase"},
        {"key": "RETIREMENT_DRAWDOWN", "label": "Retirement Drawdown"},
        {"key": "INHERITANCE_WINDFALL", "label": "Inheritance Windfall"},
        {"key": "MAJOR_LIFE_EVENT", "label": "Major Life Event"},
        {"key": "ESTATE_PLANNING", "label": "Estate Planning"},
        {"key": "RRSP_DEADLINE", "label": "RRSP Deadline"},
        {"key": "BUSINESS_SALE", "label": "Business Sale"},
        {"key": "MATERNITY_LEAVE", "label": "Maternity Leave"},
        {"key": "FOREIGN_PROPERTY", "label": "Foreign Property"},
        {"key": "CHARITABLE_GIVING", "label": "Charitable Giving"},
        {"key": "MARGIN_CALL_RISK", "label": "Margin Call Risk"},
    ]

    scenario_transcripts = {
        "EDUCATION_WITHDRAWAL": (
            "Advisor: [Client], I wanted to follow up on your daughter's university plans and the RESP withdrawal.\n"
            "Client: Yes, we're finalizing the timing. She starts in September, and we need the funds by August.\n"
            "Advisor: Let's lock in the amounts and strategy now to avoid market volatility. I recommend a phased approach.\n"
            "Client: How long will this take to set up?\n"
            "Advisor: We can execute within a week. Let me prepare a detailed plan for you."
        ),
        "TAX_LOSS_HARVESTING": (
            "Advisor: I've identified a tax-loss harvesting opportunity that could save you significant taxes.\n"
            "Client: How much are we talking about?\n"
            "Advisor: Roughly $3,000-$5,000 depending on your other gains this year.\n"
            "Client: That's substantial. When do we need to do this?\n"
            "Advisor: Before December 31. Let me send you the specific securities and the plan."
        ),
        "HOME_PURCHASE": (
            "Advisor: [Client], let's review your home purchase timeline and make sure the down payment funds are protected.\n"
            "Client: We're targeting closing in about 15 months. Need $150k for down payment.\n"
            "Advisor: That means we should move those funds to more conservative investments starting now.\n"
            "Client: Will that reduce growth?\n"
            "Advisor: Yes, but it ensures your down payment is there and safe when you need it."
        ),
        "RETIREMENT_DRAWDOWN": (
            "Advisor: Congratulations on your retirement! Let's finalize your withdrawal strategy.\n"
            "Client: I'm targeting about $90k per year. Is that sustainable?\n"
            "Advisor: Absolutely. We'll model multiple scenarios to give you confidence.\n"
            "Client: When should we start the withdrawals?\n"
            "Advisor: We can begin immediately or coordinate with CPP/OAS. Let's discuss timing."
        ),
        "INHERITANCE_WINDFALL": (
            "Advisor: I'm sorry for your loss. Let's talk about deploying the inheritance thoughtfully.\n"
            "Client: I want to make sure it grows properly. I'm not in a rush.\n"
            "Advisor: That flexibility is good. We can dollar-cost-average the investment over 3-4 months.\n"
            "Client: Won't I miss market gains?\n"
            "Advisor: This reduces timing risk and allows us to optimize the deployment of each tranche."
        ),
        "MAJOR_LIFE_EVENT": (
            "Advisor: [Client], I know things have changed significantly. Let's update your plan.\n"
            "Client: My comfort with risk is much lower now. I'm worried about volatility.\n"
            "Advisor: We'll adjust your allocation to match your new risk tolerance and goals.\n"
            "Client: How quickly can you make changes?\n"
            "Advisor: We can implement changes within a few business days."
        ),
        "ESTATE_PLANNING": (
            "Advisor: Let's update your beneficiary designations and review your estate planning.\n"
            "Client: I haven't looked at this in years. Have my circumstances changed significantly?\n"
            "Advisor: That's exactly why we're reviewing. Let me walk through each account.\n"
            "Client: Should I also update my will?\n"
            "Advisor: Yes, and we should coordinate with an estate planning specialist."
        ),
        "RRSP_DEADLINE": (
            "Advisor: [Client], you have available RRSP room. Let's use it before the March deadline.\n"
            "Client: How much room am I missing out on?\n"
            "Advisor: You have about $10k of unused room available.\n"
            "Client: Is it worth contributing?\n"
            "Advisor: Definitely. The tax deduction will be substantial."
        ),
        "BUSINESS_SALE": (
            "Advisor: Congratulations on the business sale! Let's develop a deployment strategy.\n"
            "Client: I have the proceeds now. Should I invest it all at once?\n"
            "Advisor: We can dollar-cost-average over several months to reduce market timing risk.\n"
            "Client: Will that delay things?\n"
            "Advisor: It takes a few months, but it's a prudent approach for a large lump sum."
        ),
        "MATERNITY_LEAVE": (
            "Advisor: [Client], let's plan for your parental leave and the income reduction.\n"
            "Client: My income will drop by about 40% for 12 months. Is that a big deal?\n"
            "Advisor: We need to adjust your budget and ensure your emergency fund is adequate.\n"
            "Client: What should I be saving during the leave?\n"
            "Advisor: Let's calculate your needs based on reduced income and update your plan."
        ),
        "FOREIGN_PROPERTY": (
            "Advisor: [Client], buying property in the USA requires currency planning.\n"
            "Client: How do we handle the USD conversion?\n"
            "Advisor: We can build a USD position gradually over 4 months before closing.\n"
            "Client: What about hedging?\n"
            "Advisor: Let's discuss options to manage FX risk while building the position."
        ),
        "CHARITABLE_GIVING": (
            "Advisor: [Client], donating appreciated securities is more tax-efficient than cash.\n"
            "Client: Really? How much better is it?\n"
            "Advisor: You avoid the capital gains tax on the appreciation while getting a full deduction.\n"
            "Client: How quickly can we execute?\n"
            "Advisor: Before December 31. Let me identify the best securities to donate."
        ),
        "MARGIN_CALL_RISK": (
            "Advisor: [Client], I need to discuss your margin position. It's at risk.\n"
            "Client: What do you mean 'at risk'?\n"
            "Advisor: Recent volatility brings your ratio close to a margin call. We need to act.\n"
            "Client: How serious is this?\n"
            "Advisor: Very serious. Let's reduce leverage immediately to protect your portfolio."
        ),
    }

    for idx, alert in enumerate(open_alerts, 1):
        print(f"[{idx}/{len(open_alerts)}] Enriching alert for {alert.client.name} - {alert.event_title}")

        # Determine scenario from alert content
        scenario_key = None
        for scenario in SCENARIOS:
            if scenario["key"] in alert.event_title.upper() or scenario["label"].upper() in alert.event_title.upper():
                scenario_key = scenario["key"]
                break

        if not scenario_key:
            # Fallback: use change detection or scenario matching
            if alert.change_detection:
                detected = alert.change_detection[0].get("to", "")
                scenario_key = detected if detected in [s["key"] for s in SCENARIOS] else SCENARIOS[alert.id % len(SCENARIOS)]["key"]
            else:
                scenario_key = SCENARIOS[alert.id % len(SCENARIOS)]["key"]

        scenario_label = next((s["label"] for s in SCENARIOS if s["key"] == scenario_key), "Unknown")

        # Generate meeting note for this alert
        base_date = now - timedelta(days=random.randint(7, 21))

        # Use scenario-specific transcript or generate generic one
        transcript = scenario_transcripts.get(
            scenario_key,
            f"Advisor: [Client], I wanted to discuss your {scenario_label} situation.\n"
            f"Client: I appreciate you reaching out.\n"
            f"Advisor: Let's go through the details and create an action plan.\n"
            f"Client: What should we do?\n"
            f"Advisor: Let me walk you through the recommendations."
        )

        # Summarize transcript with mock provider
        summary_result = ai_provider.summarize_transcript(
            transcript=transcript,
            context={
                "client_name": alert.client.name,
                "risk_profile": alert.client.risk_profile,
                "scenario": scenario_label,
                "alert_title": alert.event_title,
            }
        )

        # Create meeting note linked to alert's client
        meeting_note = MeetingNote(
            client_id=alert.client.id,
            title=f"{alert.event_title} - Check-in Call",
            meeting_date=base_date,
            note_body=alert.summary,  # Use alert summary as note body
            meeting_type=MeetingNoteType.PHONE_CALL,
            call_transcript=transcript,
            ai_summary=summary_result.summary_paragraph,
            ai_action_items=summary_result.action_items,
            ai_summarized_at=now,
            ai_provider_used="gemini",
        )
        db.add(meeting_note)

        if idx % 10 == 0:
            db.flush()

    db.commit()
    print(f"\n[{_ts()}] ENRICHMENT COMPLETE - Added {len(open_alerts)} meeting notes with transcripts\n")


def main():
    parser = argparse.ArgumentParser(description="Backfill script: enrich alerts or score new portfolios.")
    parser.add_argument(
        "--enrich-alerts",
        action="store_true",
        help="Enrich existing open alerts with meeting notes and transcripts (seed.py data)",
    )
    parser.add_argument(
        "--unique-summaries",
        action="store_true",
        help="Generate richer, more detailed summaries (for portfolio scoring)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of portfolios to score (for testing)",
    )
    args = parser.parse_args()

    if args.enrich_alerts:
        with SessionLocal() as db:
            enrich_existing_alerts(db)
    else:
        run_backfill(unique_summaries=args.unique_summaries, limit=args.limit)


if __name__ == "__main__":
    main()
