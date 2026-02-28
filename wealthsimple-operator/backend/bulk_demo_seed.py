"""
Comprehensive bulk demo seeding script.
Generates: clients, portfolios, alerts, meeting notes, follow-up drafts, and audit events.

Run: python bulk_demo_seed.py
Or specify options:
  python bulk_demo_seed.py --clients 30 --alerts-per-run 25 --notes 40
"""

import argparse
import random
from datetime import datetime, timedelta
from db import session_scope, SessionLocal
from models import (
    Client, Portfolio, Position, Run, Alert, AuditEvent,
    MeetingNote, FollowUpDraft, Priority, AlertStatus, AuditEventType,
    MeetingNoteType, FollowUpDraftStatus
)

# ============================================================================
# SEED DATA TEMPLATES
# ============================================================================

FIRST_NAMES = [
    "Alice", "Bob", "Carol", "David", "Emma", "Frank", "Grace", "Henry",
    "Iris", "James", "Karen", "Leo", "Maya", "Nathan", "Olivia", "Paul"
]

LAST_NAMES = [
    "Johnson", "Smith", "Williams", "Brown", "Jones", "Garcia", "Miller",
    "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez",
    "Wilson", "Anderson", "Thomas"
]

SEGMENTS = ["HNW", "UHNW", "Affluent", "Core"]
RISK_PROFILES = ["Conservative", "Balanced", "Growth", "Aggressive"]
ACCOUNT_TIERS = ["Core", "Premium", "Elite"]

PORTFOLIO_NAMES = [
    "Primary Portfolio", "Retirement", "Legacy", "Growth", "Income",
    "Educational Fund", "Vacation Fund", "Investment Account"
]

TICKERS = {
    "Equity": ["VFV", "VSP", "VUN", "XUS", "XUU", "VUN", "TSX", "SPY"],
    "Fixed Income": ["XGB", "XBB", "VAB", "VBG", "XCB", "XSB"],
    "Cash": ["CASH", "HISA", "GIC"]
}

MEETING_NOTE_TITLES = [
    "Quarterly Review",
    "Annual Planning",
    "Rebalance Discussion",
    "Retirement Planning",
    "Tax Planning Session",
    "Goal Review",
    "Risk Assessment",
    "Portfolio Check-in",
    "Market Update Discussion",
    "Inheritance Planning",
]

NOTE_TEMPLATES = [
    "Client discussed upcoming retirement in 5 years. Confirmed risk tolerance remains conservative. Reviewed estate plan - all documents current. Recommended increasing fixed income allocation by 5-10% given timeline.",
    "Quarterly rebalance review. Portfolio has drifted: equities at {eq}% vs {target}% target. Client agreed to rebalance at end of month for tax efficiency. Discussed summer travel plans.",
    "Post-market downturn check-in. Client concerned about recent volatility but reaffirmed long-term plan. Reviewed stress test scenarios. No changes needed. Next review in Q3.",
    "Year-end planning meeting. Discussed tax-loss harvesting opportunities - identified ~${loss}k in potential losses. Reviewed beneficiary designations. Planning charitable giving vehicle.",
    "College funding update. Oldest child graduating HS, starting university in fall. 529 plan is on track. Reviewed monthly contribution strategy. No changes needed.",
    "Emergency fund audit. Client concerned about market risk. Moved ${emergency}k to money market. Discussed long-term care insurance. Recommended review next quarter.",
    "Annual comprehensive review. AUM grew {aum_pct}% YTD. Lifestyle changes: {change}. Updated income assumptions. Portfolio rebalanced accordingly.",
    "New client onboarding. Transferred ${transfer}k from previous advisor. Consolidated accounts. Implemented target allocation. Initial risk profile assessment complete.",
]

TRANSCRIPTS = [
    """Advisor: Good morning, how are things going with your portfolio?
Client: Pretty good, I'm mostly happy. I did have some questions about the bond allocation though.
Advisor: Sure, let's talk about that. What concerns do you have?
Client: Well, I'm hearing rates might go up again, and bonds seem risky. Should we reduce?
Advisor: That's fair. Historically, bonds provide diversification when stocks decline. Your 40% fixed income is appropriate for your timeline. We could look at duration if you're concerned.
Client: Okay, that makes sense. What about the new technology positions?
Advisor: Those are about 8% in diversified tech funds. Still reasonable given your growth goals. We monitor concentration monthly.
Client: Good. One more thing - I'm planning to retire in 7 years. Should we start adjusting?
Advisor: Absolutely. Let's schedule a deeper planning session next month to model retirement scenarios. I'll send a calendar invite.""",

    """Advisor: Let's do a year-end planning session. How was this year financially?
Client: Really good actually. Got a raise at work, and the portfolio performance was solid.
Advisor: Excellent. That means we might need to revisit your asset allocation. Are you redirecting that raise?
Client: Yes, I want to max out my 401k contributions next year. And maybe bump my monthly from $2k to $3k.
Advisor: Great discipline. That extra thousand per month over 30 years really compounds. Let's also review tax-loss harvesting - I see about $20k in unrealized losses we can harvest this month.
Client: Perfect. What about our charitable giving plan?
Advisor: We could set up a donor-advised fund. You'd get the deduction this year but donate over time. Very tax-efficient for your $150k in giving over 5 years.
Client: That sounds perfect. Let's do it.""",

    """Client: Hi, I'm calling because I'm worried about the market. Everyone's saying recession is coming.
Advisor: I understand the concern. Markets do go through cycles. You're age 52 with a 20-year horizon. Your portfolio is built for long-term wealth building.
Client: But what if I lose everything?
Advisor: Let's run a stress scenario. Even in a 2008-level downturn, your portfolio declines 30-35%, but you're still okay because you're not withdrawing yet. In 15 years when you retire, it has time to recover.
Client: Okay, that's reassuring. But shouldn't I be more conservative?
Advisor: At 52, being 65% equities is quite reasonable. We can monitor quarterly and adjust as you approach retirement. The key is staying disciplined and not selling at the bottom.
Client: You're right. Thanks for talking me through this.""",
]

EMAIL_SUBJECTS = [
    "Your Portfolio Review - Q{} Results",
    "Action Items from Your Recent Meeting",
    "Recommended Rebalancing Plan",
    "Year-End Tax Planning Opportunity",
    "Market Update: What It Means for Your Portfolio",
    "Retirement Planning Check-In",
    "Important Changes to Your Account",
]

EMAIL_BODIES = [
    """Hi {client_name},

Thank you for taking the time to meet with me recently. As discussed, I wanted to follow up with some recommendations for your {portfolio_name} portfolio.

Given the recent market movements and your {risk_profile} risk profile, I recommend we consider the following:

1. Reviewing your current asset allocation
2. Evaluating any tax optimization opportunities
3. Scheduling a comprehensive planning review

Please let me know your availability for a call in the next 2-3 weeks.

Best regards,
Advisor Team""",

    """Hi {client_name},

Following up on our recent call, I wanted to confirm the action items we discussed:

1. Review rebalancing opportunities before year-end
2. Update beneficiary designations on all accounts
3. Discuss tax-loss harvesting possibilities
4. Schedule Q1 comprehensive review

I'll send you a calendar invite for our next meeting.

Best regards,
Advisor Team""",

    """Hi {client_name},

I've analyzed your {portfolio_name} portfolio and identified a rebalancing opportunity that could improve your risk-adjusted returns.

Your current allocation has drifted from your target due to recent market performance. I recommend we discuss the following changes at your earliest convenience.

This is a great opportunity to get your portfolio back on track before year-end.

Best regards,
Advisor Team""",
]

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def generate_client():
    """Generate a realistic client profile."""
    first = random.choice(FIRST_NAMES)
    last = random.choice(LAST_NAMES)
    return {
        "name": f"{first} {last}",
        "email": f"{first.lower()}.{last.lower()}@example.com",
        "segment": random.choice(SEGMENTS),
        "risk_profile": random.choice(RISK_PROFILES),
        "account_tier": random.choice(ACCOUNT_TIERS),
    }

def generate_portfolio(client_id: int):
    """Generate a realistic portfolio for a client."""
    total_value = random.choice([100000, 250000, 500000, 1000000, 2500000, 5000000])
    equity_target = random.choice([40, 50, 60, 70, 80])
    fixed_income_target = random.choice([20, 30, 40, 50])
    cash_target = 100 - equity_target - fixed_income_target

    return {
        "client_id": client_id,
        "name": random.choice(PORTFOLIO_NAMES),
        "total_value": total_value,
        "target_equity_pct": equity_target,
        "target_fixed_income_pct": fixed_income_target,
        "target_cash_pct": cash_target,
    }

def generate_positions(portfolio_id: int, total_value: float):
    """Generate realistic positions for a portfolio."""
    positions = []
    equity_value = total_value * random.uniform(0.35, 0.75)
    fixed_income_value = total_value * random.uniform(0.15, 0.50)
    cash_value = total_value - equity_value - fixed_income_value

    # Equity positions
    equity_tickers = random.sample(TICKERS["Equity"], k=random.randint(3, 5))
    for ticker in equity_tickers:
        weight = random.uniform(0.1, 0.4)
        positions.append({
            "portfolio_id": portfolio_id,
            "ticker": ticker,
            "asset_class": "Equity",
            "weight": weight,
            "value": equity_value * weight,
        })

    # Fixed income positions
    fi_tickers = random.sample(TICKERS["Fixed Income"], k=random.randint(2, 3))
    for ticker in fi_tickers:
        weight = random.uniform(0.15, 0.5)
        positions.append({
            "portfolio_id": portfolio_id,
            "ticker": ticker,
            "asset_class": "Fixed Income",
            "weight": weight,
            "value": fixed_income_value * weight,
        })

    # Cash
    positions.append({
        "portfolio_id": portfolio_id,
        "ticker": "CASH",
        "asset_class": "Cash",
        "weight": cash_value / total_value,
        "value": cash_value,
    })

    return positions

def generate_alert(run_id: int, portfolio_id: int, client_id: int):
    """Generate a realistic alert."""
    priority = random.choices(
        [Priority.HIGH, Priority.MEDIUM, Priority.LOW],
        weights=[0.3, 0.4, 0.3]
    )[0]

    if priority == Priority.HIGH:
        score_range = (7, 10)
    elif priority == Priority.MEDIUM:
        score_range = (4, 7)
    else:
        score_range = (1, 4)

    concentration = random.uniform(*score_range)
    drift = random.uniform(*score_range)
    volatility = random.uniform(*score_range)
    risk = (concentration + drift + volatility) / 3

    return {
        "run_id": run_id,
        "portfolio_id": portfolio_id,
        "client_id": client_id,
        "priority": priority,
        "confidence": random.randint(70, 98),
        "event_title": random.choice([
            "Portfolio drift detected",
            "Concentration risk alert",
            "Volatility spike detected",
            "Rebalancing recommended",
            "Risk threshold exceeded",
            "Allocation change detected",
        ]),
        "summary": "AI analysis detected portfolio metrics outside normal range. Human review recommended.",
        "reasoning_bullets": [
            "Current allocation has drifted from target",
            "Risk metrics indicate need for review",
            "Market conditions warrant rebalancing",
        ],
        "human_review_required": True,
        "suggested_next_step": "Schedule advisor review to discuss rebalancing",
        "decision_trace_steps": [
            {"step": "Metric Calculation", "detail": "Computed concentration, drift, volatility"},
            {"step": "Risk Scoring", "detail": "Aggregated metrics into risk score"},
            {"step": "Priority Assignment", "detail": f"Assigned {priority} based on thresholds"},
        ],
        "change_detection": [
            {"metric": "Equity Allocation", "from": f"{random.randint(50,80)}%", "to": f"{random.randint(50,80)}%"},
        ],
        "status": random.choice(list(AlertStatus)),
        "concentration_score": concentration,
        "drift_score": drift,
        "volatility_proxy": volatility,
        "risk_score": risk,
    }

def generate_meeting_note(client_id: int):
    """Generate a realistic meeting note with transcript."""
    days_ago = random.randint(1, 365)
    meeting_date = datetime.utcnow() - timedelta(days=days_ago)

    template = random.choice(NOTE_TEMPLATES)
    note_body = template.format(
        eq=random.randint(60, 80),
        target=random.randint(60, 70),
        loss=random.randint(10, 50),
        emergency=random.randint(25, 100),
        aum_pct=random.randint(5, 25),
        change=random.choice(["moved to part-time work", "received inheritance", "planning major purchase"]),
        transfer=random.randint(100, 500),
    )

    return {
        "client_id": client_id,
        "title": random.choice(MEETING_NOTE_TITLES),
        "meeting_date": meeting_date,
        "note_body": note_body,
        "meeting_type": random.choice(list(MeetingNoteType)),
        "call_transcript": random.choice(TRANSCRIPTS) if random.random() > 0.4 else None,
    }

def generate_follow_up_draft(alert_id: int, client_id: int, run_id: int):
    """Generate a realistic follow-up email draft."""
    quarter = random.randint(1, 4)
    subject_template = random.choice(EMAIL_SUBJECTS)
    if "{" in subject_template:
        subject = subject_template.format(quarter)
    else:
        subject = subject_template

    return {
        "alert_id": alert_id,
        "client_id": client_id,
        "status": random.choice(list(FollowUpDraftStatus)),
        "recipient_email": f"client{client_id}@example.com",
        "subject": subject,
        "body": random.choice(EMAIL_BODIES).format(
            client_name=f"Client {client_id}",
            portfolio_name="Primary Portfolio",
            risk_profile="Balanced"
        ),
        "generation_provider": "mock",
        "generated_from": {"alert_id": alert_id},
        "approved_by": "demo_user" if random.random() > 0.5 else None,
        "approved_at": datetime.utcnow() if random.random() > 0.5 else None,
    }

# ============================================================================
# BULK SEED FUNCTION
# ============================================================================

def bulk_seed(num_clients: int = 20, alerts_per_run: int = 20, num_notes: int = 30, num_runs: int = 3):
    """Generate bulk demo data."""
    session = SessionLocal()

    try:
        print(f"\n[*] Bulk Demo Seeding")
        print(f"   Clients: {num_clients}")
        print(f"   Runs: {num_runs} (with {alerts_per_run} alerts each)")
        print(f"   Meeting Notes: {num_notes}")
        print()

        # ====== CLIENTS & PORTFOLIOS ======
        print("[*] Creating clients and portfolios...")
        clients = []
        portfolios = []
        positions = []

        for i in range(num_clients):
            client_data = generate_client()
            client = Client(**client_data)
            session.add(client)
            session.flush()
            clients.append(client)

            # 1-3 portfolios per client
            for _ in range(random.randint(1, 3)):
                portfolio_data = generate_portfolio(client.id)
                portfolio = Portfolio(**portfolio_data)
                session.add(portfolio)
                session.flush()
                portfolios.append(portfolio)

                # 5-10 positions per portfolio
                position_data = generate_positions(portfolio.id, portfolio_data["total_value"])
                for pos in position_data:
                    position = Position(**pos)
                    session.add(position)

        session.commit()
        print(f"   [OK] Created {len(clients)} clients, {len(portfolios)} portfolios")

        # ====== RUNS & ALERTS ======
        print("[*] Creating operator runs and alerts...")
        total_alerts = 0

        for run_num in range(num_runs):
            run_date = datetime.utcnow() - timedelta(days=random.randint(1, 30))
            run = Run(started_at=run_date, completed_at=run_date, alerts_created=0, provider_used="mock")
            session.add(run)
            session.flush()

            # Create alerts for random portfolios
            run_alerts = 0
            for _ in range(alerts_per_run):
                portfolio = random.choice(portfolios)
                client = session.query(Client).filter(Client.id == portfolio.client_id).first()

                alert_data = generate_alert(run.id, portfolio.id, client.id)
                alert = Alert(**alert_data)
                session.add(alert)
                session.flush()

                # Occasionally add follow-up draft
                if random.random() > 0.6:
                    draft_data = generate_follow_up_draft(alert.id, client.id, run.id)
                    draft = FollowUpDraft(**draft_data)
                    session.add(draft)

                # Audit event for alert creation
                audit = AuditEvent(
                    alert_id=alert.id,
                    run_id=run.id,
                    event_type=AuditEventType.ALERT_CREATED,
                    actor="operator_bulk_seed",
                    details={"priority": alert_data["priority"].value},
                )
                session.add(audit)
                run_alerts += 1
                total_alerts += 1

            run.alerts_created = run_alerts
            session.commit()
            print(f"   [OK] Run {run_num + 1}: {run_alerts} alerts")

        print(f"   [OK] Total alerts: {total_alerts}")

        # ====== MEETING NOTES ======
        print("[*] Creating meeting notes...")
        for i in range(num_notes):
            client = random.choice(clients)
            note_data = generate_meeting_note(client.id)
            note = MeetingNote(**note_data)
            session.add(note)

            if (i + 1) % 10 == 0:
                session.commit()
                print(f"   [OK] Created {i + 1} meeting notes...")

        session.commit()
        print(f"   [OK] Total meeting notes: {num_notes}")

        # ====== SUMMARY ======
        print("\n[SUCCESS] Bulk seeding complete!")
        print(f"\n[SUMMARY]")
        print(f"   {len(clients)} clients")
        print(f"   {len(portfolios)} portfolios")
        print(f"   {total_alerts} alerts across {num_runs} operator runs")
        print(f"   {num_notes} meeting notes")
        print(f"   Ready for demo!\n")

    except Exception as e:
        session.rollback()
        print(f"\n[ERROR] Error during seeding: {e}")
        raise
    finally:
        session.close()


# ============================================================================
# CLI
# ============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bulk demo data seeding")
    parser.add_argument("--clients", type=int, default=20, help="Number of clients")
    parser.add_argument("--alerts-per-run", type=int, default=20, help="Alerts per operator run")
    parser.add_argument("--runs", type=int, default=3, help="Number of operator runs")
    parser.add_argument("--notes", type=int, default=30, help="Number of meeting notes")

    args = parser.parse_args()

    bulk_seed(
        num_clients=args.clients,
        alerts_per_run=args.alerts_per_run,
        num_runs=args.runs,
        num_notes=args.notes,
    )
