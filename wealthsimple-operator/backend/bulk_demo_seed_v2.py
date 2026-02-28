"""
Improved bulk demo seeding with context-aware meeting notes.
- Generates alerts first, then meeting notes RELATED to those alerts
- Uses Canadian terminology (RRSP, TFSA, not Roth IRA)
- Appends to existing data (doesn't overwrite)
- Meeting note content matches alert types for realistic context

Run: python bulk_demo_seed_v2.py --clients 40 --runs 5 --alerts-per-run 25 --notes 80
"""

import argparse
import random
from datetime import datetime, timedelta
from db import SessionLocal
from models import (
    Client, Portfolio, Position, Run, Alert, AuditEvent,
    MeetingNote, FollowUpDraft, Priority, AlertStatus, AuditEventType,
    MeetingNoteType, FollowUpDraftStatus
)

# ============================================================================
# CANADIAN SEED DATA TEMPLATES
# ============================================================================

FIRST_NAMES = [
    "Alice", "Bob", "Carol", "David", "Emma", "Frank", "Grace", "Henry",
    "Iris", "James", "Karen", "Leo", "Maya", "Nathan", "Olivia", "Paul",
    "Rachel", "Steven", "Taylor", "Victoria"
]

LAST_NAMES = [
    "Johnson", "Smith", "Williams", "Brown", "Jones", "Garcia", "Miller",
    "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez",
    "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin"
]

SEGMENTS = ["HNW", "UHNW", "Affluent", "Core"]
RISK_PROFILES = ["Conservative", "Balanced", "Growth", "Aggressive"]
ACCOUNT_TIERS = ["Core", "Premium", "Elite"]

PORTFOLIO_NAMES = [
    "Primary Portfolio", "Retirement (RRSP)", "Tax-Free Savings (TFSA)",
    "Legacy Portfolio", "Growth Account", "Educational Fund", "Investment Account"
]

TICKERS = {
    "Equity": ["VFV", "VSP", "VUN", "XUS", "XUU", "TSX", "SPY", "XIC", "VSB"],
    "Fixed Income": ["XGB", "XBB", "VAB", "VBG", "XCB", "XSB"],
    "Cash": ["CASH", "HISA", "GIC"]
}

# ============================================================================
# CONTEXT-AWARE MEETING NOTE TEMPLATES
# ============================================================================

# Alert type -> Meeting note context mapping
ALERT_CONTEXT_MAPPING = {
    "concentration": [
        "Client discussed their {concentrated_asset} holdings which have grown significantly. Concerned about concentration risk in tech sector. We reviewed diversification strategies and discussed systematic rebalancing.",
        "Client mentioned their {concentrated_asset} position is now {pct}% of portfolio. Requested we develop a plan to gradually shift to broader exposure. Discussed tax implications of rebalancing.",
        "During review, client noted {concentrated_asset} allocation has become too large relative to overall plan. Wants to discuss selling strategy and tax-loss harvesting opportunities.",
    ],
    "drift": [
        "Quarterly rebalance review. Portfolio has drifted significantly from target allocation. Discussed market-driven changes and recommended rebalancing at year-end for tax efficiency.",
        "Client noted asset allocation no longer matches their risk tolerance due to market movements. Agreed to rebalance back to target of {target_equity}% equities, {target_income}% fixed income.",
        "Portfolio drift assessment: equities have grown to {current_equity}% vs {target_equity}% target due to strong market performance. Discussed whether to lock in gains or maintain exposure.",
    ],
    "leverage": [
        "Client interested in using margin or leverage to amplify returns. Discussed risks including margin calls, forced liquidation, and interest costs. Reviewed their risk tolerance and suggested alternative growth strategies.",
        "Client requested information on leveraged ETFs ({etf}) to enhance portfolio returns. Explained mechanics, risks, and suitability given {risk_profile} risk profile. Decided to discuss further with CPA.",
        "Discussed client's interest in margin borrowing to fund {purpose}. Explained collateral requirements, liquidation triggers, and opportunity cost. Recommended against given current market volatility.",
    ],
    "volatility": [
        "Post-market downturn check-in. Client concerned about recent volatility affecting their portfolio. Reviewed stress test scenarios and reaffirmed long-term plan. Confirmed no changes needed.",
        "Client expressed concern about portfolio volatility impacting sleep at night. Discussed whether allocation is truly suitable or if we should shift to more conservative positioning.",
        "Market volatility triggered client inquiry about reducing equity exposure. Reviewed their goals and timeline - plan remains intact. Agreed to monitor quarterly.",
    ],
    "drift_high": [
        "Critical drift alert: portfolio has moved significantly from target. Client wants to understand why and what corrective actions are needed. Discussed immediate rebalancing plan.",
        "Client expressed concern about notification of HIGH priority drift alert. Reviewed positions and confirmed this is due to market appreciation in equity holdings. Plan to rebalance next month.",
    ],
    "default": [
        "Quarterly portfolio review. Discussed recent market conditions and portfolio performance. Client remains confident with current allocation and strategy. No changes recommended.",
        "Annual rebalance meeting. Reviewed all holdings and confirmed alignment with financial goals. Discussed tax-optimization opportunities for upcoming year.",
        "Client check-in to discuss recent portfolio changes and market outlook. Reviewed cash flow needs and confirmed emergency fund is adequate.",
    ]
}

CANADIAN_ACCOUNT_TYPES = [
    "RRSP", "TFSA", "non-registered brokerage account", "spousal RRSP",
    "RESP for children", "margin account"
]

CANADIAN_TAX_TOPICS = [
    "tax-loss harvesting", "capital gains distribution",
    "splitting investment income with spouse", "pension income splitting",
    "first-time home buyers plan", "lifelong learning plan"
]

CANADIAN_MARKET_TOPICS = [
    "Canadian bank dividend cuts", "energy sector volatility",
    "interest rate changes from Bank of Canada", "loonie strength",
    "housing market impact on portfolios"
]

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _non_round_dollar_amount(min_amount: int, max_amount: int) -> int:
    amount = random.randint(min_amount, max_amount)
    if amount % 100 != 0:
        return amount

    for _ in range(100):
        candidate = random.randint(min_amount, max_amount)
        if candidate % 100 != 0:
            return candidate
    return amount


def generate_client():
    """Generate a realistic Canadian client profile."""
    first = random.choice(FIRST_NAMES)
    last = random.choice(LAST_NAMES)
    return {
        "name": f"{first} {last}",
        "email": f"{first.lower()}.{last.lower()}@example.ca",
        "segment": random.choice(SEGMENTS),
        "risk_profile": random.choice(RISK_PROFILES),
        "account_tier": random.choice(ACCOUNT_TIERS),
    }

def generate_portfolio(client_id: int):
    """Generate a realistic portfolio for a client."""
    total_value = _non_round_dollar_amount(85_000, 5_000_000)
    equity_target = round(random.uniform(38.0, 82.0), 1)
    fixed_income_target = round(random.uniform(12.0, 52.0), 1)
    cash_target = round(100.0 - equity_target - fixed_income_target, 1)

    if cash_target < 2.0:
        fixed_income_target = round(max(10.0, fixed_income_target - (2.0 - cash_target)), 1)
        cash_target = round(100.0 - equity_target - fixed_income_target, 1)
    elif cash_target > 25.0:
        fixed_income_target = round(fixed_income_target + (cash_target - 25.0), 1)
        cash_target = round(100.0 - equity_target - fixed_income_target, 1)

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
        event_choices = ["Portfolio drift detected", "Concentration risk alert",
                        "Leverage/Margin exposure detected", "Volatility spike"]
    elif priority == Priority.MEDIUM:
        score_range = (4, 7)
        event_choices = ["Allocation change detected", "Rebalancing recommended",
                        "Risk threshold exceeded"]
    else:
        score_range = (1, 4)
        event_choices = ["Minor drift detected", "Position review suggested",
                        "Routine monitoring alert"]

    concentration = random.uniform(*score_range)
    drift = random.uniform(*score_range)
    volatility = random.uniform(*score_range)
    risk = (concentration + drift + volatility) / 3

    event_title = random.choice(event_choices)

    return {
        "run_id": run_id,
        "portfolio_id": portfolio_id,
        "client_id": client_id,
        "priority": priority,
        "confidence": random.randint(70, 98),
        "event_title": event_title,
        "summary": "AI analysis detected portfolio metrics outside normal range. Human review recommended.",
        "reasoning_bullets": [
            "Current allocation has drifted from target",
            "Risk metrics indicate need for review",
            "Market conditions warrant monitoring",
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
        "_event_title": event_title,  # Store for context
    }

def get_alert_context(alert_title: str) -> str:
    """Determine alert context type from alert title."""
    title_lower = alert_title.lower()

    if "concentration" in title_lower:
        return "concentration"
    elif "drift" in title_lower:
        return "drift"
    elif "leverage" in title_lower or "margin" in title_lower:
        return "leverage"
    elif "volatility" in title_lower:
        return "volatility"
    else:
        return "default"

def generate_context_aware_meeting_note(client_id: int, alert: dict = None):
    """Generate meeting note that relates to alert if provided."""
    days_ago = random.randint(1, 30)
    meeting_date = datetime.utcnow() - timedelta(days=days_ago)

    # Determine context
    context_type = "default"
    if alert:
        context_type = get_alert_context(alert.get("_event_title", ""))

    # Get appropriate template
    templates = ALERT_CONTEXT_MAPPING.get(context_type, ALERT_CONTEXT_MAPPING["default"])
    note_template = random.choice(templates)

    # Fill in context variables
    context_vars = {
        "concentrated_asset": random.choice(["Canadian banks", "tech sector", "energy stocks", "real estate"]),
        "pct": random.randint(35, 60),
        "target_equity": random.randint(50, 70),
        "target_income": random.randint(20, 40),
        "current_equity": random.randint(65, 85),
        "etf": random.choice(["HLU.TO", "PSA.TO", "TSX.TO"]),
        "risk_profile": random.choice(RISK_PROFILES).lower(),
        "purpose": random.choice(["business opportunity", "real estate investment", "major purchase"]),
        "account": random.choice(CANADIAN_ACCOUNT_TYPES),
    }

    note_body = note_template.format(**context_vars)

    # Add Canadian-relevant topics
    if random.random() > 0.5:
        note_body += f"\n\nAlso discussed: {random.choice(CANADIAN_TAX_TOPICS)} to optimize their {random.choice(CANADIAN_ACCOUNT_TYPES)}."

    return {
        "client_id": client_id,
        "title": random.choice([
            "Portfolio Review", "Rebalancing Discussion", "Risk Assessment",
            "Retirement Planning", "Tax Planning", "Annual Review", "Market Discussion"
        ]),
        "meeting_date": meeting_date,
        "note_body": note_body,
        "meeting_type": random.choice(list(MeetingNoteType)),
        "call_transcript": None,  # Can add later if needed
    }

# ============================================================================
# BULK SEED FUNCTION
# ============================================================================

def bulk_seed(num_clients: int = 20, alerts_per_run: int = 20, num_notes: int = 30, num_runs: int = 3):
    """Generate bulk demo data with context-aware notes."""
    session = SessionLocal()

    try:
        print(f"\n[*] Bulk Demo Seeding (v2 - Context-Aware)")
        print(f"   Clients: {num_clients}")
        print(f"   Runs: {num_runs} (with {alerts_per_run} alerts each)")
        print(f"   Meeting Notes: {num_notes}")
        print()

        # Check existing clients to avoid exact duplicates
        existing_client_count = session.query(Client).count()
        print(f"[*] Existing clients in database: {existing_client_count}")
        print(f"[*] Will ADD {num_clients} more (not replace)")
        print()

        # ====== CLIENTS & PORTFOLIOS ======
        print("[*] Creating clients and portfolios...")
        clients = []
        portfolios = []

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

                # Positions
                position_data = generate_positions(portfolio.id, portfolio_data["total_value"])
                for pos in position_data:
                    position = Position(**pos)
                    session.add(position)

        session.commit()
        print(f"   [OK] Created {len(clients)} clients, {len(portfolios)} portfolios")

        # ====== RUNS & ALERTS ======
        print("[*] Creating operator runs and alerts...")
        total_alerts = 0
        all_alerts = []

        for run_num in range(num_runs):
            run_date = datetime.utcnow() - timedelta(days=random.randint(1, 60))
            run = Run(started_at=run_date, completed_at=run_date, alerts_created=0, provider_used="mock")
            session.add(run)
            session.flush()

            run_alerts = 0
            for _ in range(alerts_per_run):
                portfolio = random.choice(portfolios)
                client = session.query(Client).filter(Client.id == portfolio.client_id).first()

                alert_data = generate_alert(run.id, portfolio.id, client.id)

                # Extract internal fields before creating Alert
                event_title_for_context = alert_data.pop("_event_title", alert_data.get("event_title"))

                alert = Alert(**alert_data)
                session.add(alert)
                session.flush()

                # Store alert for context-aware notes
                all_alerts.append({
                    "alert": alert_data,
                    "client_id": client.id,
                    "alert_obj": alert,
                    "event_title": event_title_for_context
                })

                # Occasionally add follow-up draft
                if random.random() > 0.6:
                    draft = FollowUpDraft(
                        alert_id=alert.id,
                        client_id=client.id,
                        status=random.choice(list(FollowUpDraftStatus)),
                        recipient_email=client.email,
                        subject=f"Portfolio Review Required - {alert_data['event_title']}",
                        body=f"We detected {alert_data['event_title'].lower()} in your portfolio. Please review the details.",
                        generation_provider="mock",
                        generated_from={"alert_id": alert.id},
                    )
                    session.add(draft)

                # Audit event
                audit = AuditEvent(
                    alert_id=alert.id,
                    run_id=run.id,
                    event_type=AuditEventType.ALERT_CREATED,
                    actor="bulk_seed_v2",
                    details={"priority": alert_data["priority"].value},
                )
                session.add(audit)
                run_alerts += 1
                total_alerts += 1

            run.alerts_created = run_alerts
            session.commit()
            print(f"   [OK] Run {run_num + 1}: {run_alerts} alerts")

        print(f"   [OK] Total alerts: {total_alerts}")

        # ====== CONTEXT-AWARE MEETING NOTES ======
        print("[*] Creating context-aware meeting notes...")

        for i in range(num_notes):
            # 50% chance to create note related to an existing alert
            if all_alerts and random.random() > 0.5:
                alert_ref = random.choice(all_alerts)
                note_data = generate_context_aware_meeting_note(
                    alert_ref["client_id"],
                    {"_event_title": alert_ref.get("event_title", "Portfolio review")}
                )
            else:
                # Generic note for a random client
                client = random.choice(clients)
                note_data = generate_context_aware_meeting_note(client.id)

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
        print(f"   {len(clients)} new clients added")
        print(f"   {len(portfolios)} new portfolios")
        print(f"   {total_alerts} alerts across {num_runs} operator runs")
        print(f"   {num_notes} context-aware meeting notes (linked to alerts)")
        print(f"   Ready for demo!\n")

    except Exception as e:
        session.rollback()
        print(f"\n[ERROR] Error during seeding: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        session.close()


# ============================================================================
# CLI
# ============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bulk demo data seeding (v2 - context-aware)")
    parser.add_argument("--clients", type=int, default=20, help="Number of NEW clients to create")
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
