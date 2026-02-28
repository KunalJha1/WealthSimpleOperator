# seed.py v3 - Complete Client Universe Generation

## Overview

The redesigned `seed.py` generates complete client universes using Gemini AI, with each client being a unique, fully-realized profile including:

- **Unique Persona**: Name, segment, risk profile, AUM, investment goals
- **Portfolio**: Assets based on generated profile (Canadian-focused ETFs/funds)
- **Alert Assignment**: 30% probability of receiving an alert with a scenario
- **Meeting Notes**: Linear progression of 3-4 scenario-based calls (or 1 generic review if no alert)
- **Auto-Summarized Transcripts**: Every call transcript is AI-summarized with action items

## Key Features

### 1. Gemini-Powered Universe Generation
Each client is generated completely using Gemini with:
- Realistic Canadian context (names, assets, terminology)
- Segment-appropriate AUM ranges
- Risk-profile-aligned investment goals
- 30% probability of alert assignment

### 2. Linear Scenario Progression
Clients with alerts get a structured meeting note timeline:
```
Initial Planning Meeting (Day 0)
         ↓
Follow-up Check-in (Day 30)
         ↓
Final Review Call (Day 60)
```

Each note flows naturally from one to the next, with realistic advisor-client dialogue.

### 3. Auto-Summarized Transcripts
Every meeting note's transcript is automatically summarized using the AI provider:
- AI Summary paragraph
- Action items list
- Provider attribution

### 4. Guaranteed Coverage
- **Every client** has at least 1 call log (meeting note with transcript)
- **Clients with alerts** have 3+ meeting notes forming a scenario narrative
- **Clients without alerts** have at least 1 generic quarterly review

## Usage

### Basic Usage (Fallback Templates)
```bash
cd wealthsimple-operator/backend
python seed.py --clients 50
```

### With Gemini (Unique Generation)
Requires `GEMINI_API_KEY` in `.env`:
```bash
python seed.py --clients 50 --gemini-enabled
```

### Custom Count
```bash
python seed.py --clients 100
python seed.py --clients 10 --gemini-enabled
```

## Data Generated

For each client universe:

**Client Record:**
- Name (Gemini-generated Canadian names)
- Segment (Core, Affluent, HNW, UHNW)
- Risk Profile (Conservative, Balanced, Growth, Aggressive)
- Account Tier (auto-assigned based on AUM)
- Email (auto-generated)

**Portfolio:**
- Total Value (AUM from 50k to 3M)
- Target Allocations (based on risk profile)
- Positions (5-12 holdings of Canadian ETFs/funds)

**Alert (if assigned, 30%):**
- Scenario (6 possible: Education Withdrawal, Tax Loss Harvesting, Home Purchase, Retirement Drawdown, Inheritance Windfall, Margin Call Risk)
- Priority (50% HIGH, others MEDIUM/LOW)
- Confidence (70-95%)
- Full reasoning and decision trace

**Meeting Notes (guaranteed ≥1):**
- Title
- Meeting Date
- Note Body
- Call Transcript (full dialogue)
- AI Summary (auto-generated)
- Action Items (extracted from transcript)

## Example Output

```
[SEEDING CLIENT UNIVERSES]
Generating 50 clients
Gemini available: True
Using Gemini: True

Gemini client initialized for universe generation

[10/50] Batch committed: 10 clients, 3 alerts, 30 notes
[20/50] Batch committed: 20 clients, 6 alerts, 60 notes
[30/50] Batch committed: 30 clients, 9 alerts, 90 notes
[40/50] Batch committed: 40 clients, 12 alerts, 120 notes
[50/50] Batch committed: 50 clients, 15 alerts, 150 notes

[SEEDING COMPLETE] 50 clients, 15 alerts, 150 meeting notes

[SEED SUCCESS] Database ready for Wealthsimple Operator
```

## Scenario Timeline Details

Each scenario has a configured timeline (days offset from "now"):

| Scenario | Timeline | Notes |
|----------|----------|-------|
| Education Withdrawal | [0, 30, 60] | Child starting school, RESP withdrawal timing |
| Tax Loss Harvesting | [0, 20, 45] | Year-end tax strategy, execute before deadline |
| Home Purchase | [0, 45, 90] | Liquidity planning for down payment in 12-18 months |
| Retirement Drawdown | [0, 30, 60] | Switch from accumulation to income strategy |
| Inheritance Windfall | [0, 14, 35] | Large lump sum deployment planning |
| Margin Call Risk | [0, 7, 21] | Urgent deleveraging and risk mitigation |

## Canadian Context

The generated universes use Canadian-appropriate terminology:
- **Account Types**: RRSP, TFSA, RESP, spousal RRSP, non-registered, margin accounts
- **Tax Strategies**: Tax-loss harvesting, donation of appreciated securities, RRSP contributions, income splitting
- **ETF/Funds**: VFV, VSP, VUN, XIC, XGB, XBB, VAB, VBG, ZCS, ZSP, HBAL, XBAL
- **Regulations**: RRSP deadline, attribution rules, capital gains treatment

## Fallback Behavior

If Gemini is unavailable or fails:
1. Universe generation uses reasonable random defaults
2. Meeting notes use fallback templates (still realistic, just not personalized)
3. Transcripts are still auto-summarized
4. All data integrity is maintained

## Rate Limiting

When using Gemini:
- 1-second delay between API calls to avoid rate limits
- Exponential backoff retry (8.0s initial, max 20s) for 429/503/RESOURCE_EXHAUSTED errors
- Max 8 retries with jitter to prevent thundering herd

## Database Validation

After seeding, verify with:
```python
from db import SessionLocal
from models import Client, Alert, MeetingNote

session = SessionLocal()
clients = session.query(Client).count()
alerts = session.query(Alert).count()
notes = session.query(MeetingNote).count()

print(f"Clients: {clients}")
print(f"Alerts: {alerts} ({int(100*alerts/clients)}%)")
print(f"Notes: {notes} (avg {notes/clients} per client)")
```

Expected: ~30% alerts, 3+ notes per alerted client, 1 note per non-alerted client.

## Performance

Approximate seeding times:

| Clients | With Gemini | Fallback |
|---------|------------|----------|
| 10 | ~30s | ~2s |
| 50 | ~2.5min | ~8s |
| 100 | ~5min | ~15s |

Times include transcript summarization and batch commits.

## Architecture

```
seed.py
├── generate_client_universe_with_gemini()
│   └── Returns complete client profile (name, segment, AUM, assets, alert assignment, scenario)
├── generate_scenario_meeting_notes_with_gemini()
│   └── Creates meeting note + transcript for each timeline point
├── seed_client_universes()
│   ├── For each client:
│   │   ├── Generate universe
│   │   ├── Create client, portfolio, positions
│   │   ├── If alert: Create alert + scenario notes
│   │   └── If no alert: Create generic review note
│   └── Auto-summarize all transcripts
└── main()
    └── Entry point with argparse for --clients and --gemini-enabled
```

## Next Steps

1. Run `python seed.py --clients 50 --gemini-enabled` for full demo data
2. Start backend: `python main.py`
3. Start frontend: `npm run dev`
4. Visit http://localhost:3000/operator to see priority queue
5. Click meeting notes tab to see scenario-driven call logs with summaries

## Troubleshooting

**"GEMINI_API_KEY not set"**
→ Add `GEMINI_API_KEY=your_key` to `.env`

**"Rate limited/Overloaded. Retrying..."**
→ Normal behavior, script will retry with exponential backoff

**"ERROR generating universe with Gemini"**
→ Falls back to default templates, continues seeding

**Database locked**
→ Make sure FastAPI server isn't running: `pkill -f main.py`

**Slow performance**
→ Reduce client count for faster iterations: `python seed.py --clients 10`
