"""
Seed meeting notes with realistic demo data for testing.
Run: python seed_meeting_notes.py
"""

from datetime import datetime, timedelta
import random
from db import SessionLocal
from models import MeetingNote, MeetingNoteType, Client

# Sample meeting note bodies
NOTE_TEMPLATES = [
    "Client discussed upcoming retirement in 5 years. Confirmed risk tolerance remains conservative. Reviewed estate plan with lawyer - all documents current. Recommended increasing fixed income allocation by 5-10% given timeline.",
    "Quarterly rebalance review. Portfolio has drifted: equities at 68% vs 60% target. Client agreed to rebalance at end of month for tax efficiency. Discussed summer travel plans and updated contact preferences.",
    "Post-market downturn check-in. Client concerned about recent volatility but reaffirmed long-term plan. Reviewed stress test scenarios. No changes needed. Next review in Q3.",
    "Year-end planning meeting. Discussed tax-loss harvesting opportunities - identified ~$15k in potential losses. Reviewed beneficiary designations (all current). Planning charitable giving vehicle for 2027.",
    "College funding update. Oldest child graduating HS, starting university in fall. 529 plan is on track ($187k accumulated). Reviewed monthly contribution strategy. No changes needed.",
    "Inherited portfolio review. Client received $450k from parent's estate. Discussed integration strategy and tax implications. Agreed on phased deployment over 6 months to avoid market timing risk.",
    "Annual comprehensive review. AUM grew 12% YTD (strong market + client additions). Lifestyle changes: moved to part-time work. Updated income assumptions and cash flow needs. Rebalanced accordingly.",
    "Emergency fund audit. Client concerned about market risk given health issues. Moved $50k to money market (3 months expenses). Discussed long-term care insurance options. Recommended review with advisor next quarter."
]

# Sample transcripts for summarization testing
TRANSCRIPT_TEMPLATES = [
    """Advisor: Good morning, how are things going with your portfolio?
Client: Pretty good, I'm mostly happy with how it's performing. I did have some questions about the bond allocation though.
Advisor: Sure, let's talk about that. What concerns do you have?
Client: Well, I'm hearing rates might go up again, and bonds seem risky. Should we reduce that position?
Advisor: That's a fair question. Historically, bonds provide diversification when stocks decline. Your 40% fixed income allocation is appropriate for your timeline and risk tolerance. We could look at duration if you're concerned about rate risk.
Client: Okay, that makes sense. What about the new technology positions?
Advisor: Those are about 8% of your portfolio in diversified tech funds. Still reasonable given your growth goals. We monitor concentration monthly.
Client: Good. One more thing - I'm planning to retire in 7 years. Should we start adjusting?
Advisor: Absolutely. Let's schedule a deeper planning session next month to model retirement scenarios and adjust your glide path. I'll send a calendar invite.""",

    """Advisor: Let's do a year-end planning session. How was 2026 for you financially?
Client: Really good actually. Got a raise at work, and the portfolio performance was solid.
Advisor: Excellent. That means we might need to revisit your asset allocation. Are you thinking of redirecting that raise into savings?
Client: Yes, I want to max out my 401k contributions next year. And maybe bump my monthly investments from $2k to $3k.
Advisor: Great discipline. That extra thousand per month over 30 years really compounds. Let's also review tax-loss harvesting in your taxable account - I see about $20k in unrealized losses we can harvest this month.
Client: Perfect. What about our charitable giving plan?
Advisor: We could set up a donor-advised fund. You'd get the deduction this year, but can donate to causes over time. With your estimated $150k in charitable giving over the next 5 years, this is very tax-efficient.
Client: That sounds perfect. Let's do it.""",

    """Client: Hi, I'm calling because I'm worried about the market. Everyone's saying a recession is coming.
Advisor: I understand the concern. Markets do go through cycles. Let's look at your situation - you're age 52 with a 20-year horizon. Your portfolio is built for long-term wealth building, not short-term market predictions.
Client: But what if I lose everything?
Advisor: Let's run a stress scenario. Even in a 2008-level downturn, your portfolio declines 30-35%, but you're still okay because you're not withdrawing yet. In 15 years when you retire, it has time to recover.
Client: Okay, that's reassuring. But shouldn't I be more conservative?
Advisor: At 52, being 65% equities is actually quite reasonable. We can monitor quarterly and adjust as you approach retirement. The key is staying disciplined and not selling at the bottom.
Client: You're right. Thanks for talking me through this.""",
]

def seed_meeting_notes(num_notes: int = 12):
    """Generate and insert demo meeting notes."""
    session = SessionLocal()

    try:
        # Get all clients
        clients = session.query(Client).all()
        if not clients:
            print("[ERROR] No clients found. Run seed.py first to create clients.")
            return

        # Generate notes
        created_count = 0
        base_date = datetime.utcnow() - timedelta(days=180)

        for i in range(num_notes):
            client = random.choice(clients)
            days_ago = random.randint(1, 180)
            meeting_date = base_date + timedelta(days=days_ago)
            meeting_types = ["meeting", "phone_call", "email", "review"]
            meeting_type = random.choice(meeting_types)

            # 60% chance of including a transcript
            has_transcript = random.random() < 0.6

            note = MeetingNote(
                client_id=client.id,
                title=f"{random.choice(['Quarterly Review', 'Annual Planning', 'Rebalance Discussion', 'Retirement Planning', 'Tax Planning', 'Check-in', 'Goal Review', 'Risk Assessment'])}",
                meeting_date=meeting_date,
                note_body=random.choice(NOTE_TEMPLATES),
                meeting_type=random.choice(meeting_types),
                call_transcript=random.choice(TRANSCRIPT_TEMPLATES) if has_transcript else None,
            )

            session.add(note)
            created_count += 1

            # Commit in batches
            if created_count % 5 == 0:
                session.commit()
                print(f"[OK] Created {created_count} meeting notes...")

        session.commit()
        print(f"\n[SUCCESS] Successfully created {created_count} meeting notes!")

        # Show summary
        for client in clients[:3]:
            note_count = session.query(MeetingNote).filter(MeetingNote.client_id == client.id).count()
            if note_count > 0:
                print(f"   {client.name}: {note_count} notes")

    except Exception as e:
        session.rollback()
        print(f"[ERROR] Error: {e}")
    finally:
        session.close()


if __name__ == "__main__":
    import sys

    # Allow override: python seed_meeting_notes.py 20
    num_notes = int(sys.argv[1]) if len(sys.argv) > 1 else 12

    print(f"🌱 Seeding {num_notes} demo meeting notes...")
    seed_meeting_notes(num_notes)
