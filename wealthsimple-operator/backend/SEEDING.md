# Database Seeding Guide

This guide explains how to populate the Wealthsimple Operator database with realistic demo data.

## Quick Start

```bash
cd wealthsimple-operator/backend
python bulk_demo_seed.py
```

That's it! The default settings create:
- 20 clients with realistic names
- ~60 portfolios (3 per client on average)
- 3 operator runs with ~20 alerts each (60 alerts total)
- 30 meeting notes with realistic transcripts

---

## Seeding Scripts

### 1. `seed.py` - Original Base Seed (Required First)
Creates the initial 50-client monitoring universe from `data/seed_output.json`.

**Run once:**
```bash
python seed.py
```

**Creates:**
- 50 clients across segments (HNW, UHNW, Affluent, Core)
- ~150 portfolios
- ~1,500 positions
- Baseline database ready for operator runs

---

### 2. `bulk_demo_seed.py` - Comprehensive Demo Data
Generates realistic alerts, meeting notes, and drafts in bulk.

**Basic usage:**
```bash
python bulk_demo_seed.py
```

**Custom sizes:**
```bash
# Create a large demo with 50 clients and 5 operator runs
python bulk_demo_seed.py --clients 50 --runs 5 --alerts-per-run 30 --notes 100

# Small demo for quick testing
python bulk_demo_seed.py --clients 5 --runs 1 --alerts-per-run 10 --notes 5
```

**Options:**
- `--clients N` - Number of clients to create (default: 20)
- `--runs N` - Number of operator runs (default: 3)
- `--alerts-per-run N` - Alerts per run (default: 20)
- `--notes N` - Meeting notes to generate (default: 30)

**Creates:**
- Realistic client profiles (names, segments, risk profiles)
- Varied portfolio allocations
- Alerts with computed risk metrics
- Meeting notes with optional call transcripts
- Follow-up email drafts (60% of alerts)
- Audit events for all actions

---

### 3. `seed_meeting_notes.py` - Meeting Notes Only
Generates additional meeting notes with transcripts for testing AI summarization.

**Usage:**
```bash
python seed_meeting_notes.py          # Creates 12 notes
python seed_meeting_notes.py 50       # Creates 50 notes
```

**Creates:**
- Random dates (spreads across 180 days)
- Mix of meeting types (meeting, phone_call, email, review)
- 60% include call transcripts for AI summarization testing
- Keywords in transcripts trigger AI action items

---

## Data Characteristics

### Client Segments
- **HNW**: High Net Worth ($1M-$10M AUM)
- **UHNW**: Ultra High Net Worth ($10M+ AUM)
- **Affluent**: $250K-$1M AUM
- **Core**: Retail clients

### Risk Profiles
- Conservative
- Balanced
- Growth
- Aggressive

### Portfolio Allocations
- **Equity**: 35-75% (mix of VFV, VSP, VUN, SPY, TSX)
- **Fixed Income**: 15-50% (XGB, XBB, VAB, VBG)
- **Cash**: 5-30% (HISA, GIC)

### Alert Characteristics
- **HIGH priority**: 30% of alerts (concentration/drift/volatility 7-10)
- **MEDIUM priority**: 40% of alerts (4-7)
- **LOW priority**: 30% of alerts (1-4)
- Realistic risk scores (concentration, drift, volatility)
- Confidence scores 70-98%

### Meeting Notes
- Dates spread across last 180 days
- Topics: retirement, taxes, rebalancing, estate, home purchase
- 60% include realistic call transcripts
- Transcripts contain keywords that AI summarizer detects

---

## Typical Workflow

### For Local Development
```bash
# 1. Fresh start
rm operator.db*  # Delete old database

# 2. Create base monitoring universe
python seed.py

# 3. Add demo alerts and notes
python bulk_demo_seed.py --clients 15 --runs 2 --notes 20

# 4. Start frontend and backend
cd ../frontend && npm run dev
# In another terminal:
python main.py
```

### For Demo/Presentation
```bash
# Large realistic dataset
python bulk_demo_seed.py --clients 40 --runs 5 --alerts-per-run 40 --notes 80

# Check volume
sqlite3 operator.db "SELECT 'Clients:' AS metric, COUNT(*) FROM clients UNION ALL
                     SELECT 'Portfolios:', COUNT(*) FROM portfolios UNION ALL
                     SELECT 'Alerts:', COUNT(*) FROM alerts UNION ALL
                     SELECT 'Meeting Notes:', COUNT(*) FROM meeting_notes;"
```

### For Load Testing
```bash
# Heavy dataset
python bulk_demo_seed.py --clients 100 --runs 10 --alerts-per-run 50 --notes 200
```

---

## Data Verification

Check what was created:

```bash
sqlite3 operator.db

# Count by table
SELECT 'Clients', COUNT(*) FROM clients
UNION ALL SELECT 'Portfolios', COUNT(*) FROM portfolios
UNION ALL SELECT 'Alerts', COUNT(*) FROM alerts
UNION ALL SELECT 'Meeting Notes', COUNT(*) FROM meeting_notes
UNION ALL SELECT 'Follow-up Drafts', COUNT(*) FROM follow_up_drafts;

# Alert distribution by priority
SELECT priority, COUNT(*) FROM alerts GROUP BY priority;

# Recent alerts
SELECT id, client_id, priority, event_title, created_at FROM alerts
ORDER BY created_at DESC LIMIT 10;

# Notes with transcripts
SELECT COUNT(*) FROM meeting_notes WHERE call_transcript IS NOT NULL;
```

---

## Resetting Database

To start fresh:

```bash
rm operator.db*
python seed.py
python bulk_demo_seed.py
```

Or with custom sizes:

```bash
rm operator.db*
python seed.py
python bulk_demo_seed.py --clients 50 --runs 5 --notes 100
```

---

## Seeding Times

Approximate times on modern hardware:

| Operation | 20 Clients | 50 Clients | 100 Clients |
|-----------|-----------|-----------|-------------|
| seed.py | ~1s | ~1s | ~1s |
| bulk_demo_seed | ~5s | ~10s | ~20s |
| Total | ~6s | ~11s | ~21s |

---

## Troubleshooting

### Script fails with "no such table"
→ Run `seed.py` first to create base schema

### Database locked
→ Make sure FastAPI server isn't running; close all DB connections

### Want to add more alerts without recreating everything
→ Run `bulk_demo_seed.py` again with different `--runs` or `--clients`; it appends data

### Need different data characteristics
→ Edit the templates and ranges in `bulk_demo_seed.py` (FIRST_NAMES, NOTE_TEMPLATES, etc.)

---

## What to Test After Seeding

✅ **Operator Page**
- Run operator → Should see priority queue with seeded alerts
- Click HIGH alert → View risk brief, change detection
- Check confidence scores are realistic (70-98%)

✅ **Rebalancing Suggestions**
- Click HIGH priority alert with high drift score
- Should see allocation delta table
- Test "Approve Rebalancing Plan"

✅ **Meeting Notes Page**
- Select client → See meeting notes sorted by date
- Click note with transcript → "AI Summarize Transcript" button appears
- Click button → AI extracts summary + action items
- Transcript expands/collapses properly

✅ **Follow-up Drafts**
- Click alert → See follow-up draft (if one was generated)
- Try approve/reject/regenerate workflow

✅ **Audit Log**
- Filter by priority, status, event type
- Verify all actions are logged with proper timestamps

✅ **Simulations**
- Run scenario → See impacted portfolios
- Generate playbook → See batch email drafts

---

## Performance Notes

- SQLite works fine for demo (~1000 alerts, 100+ clients)
- For load testing >10K alerts, consider profiling database queries
- Meeting note summarization is provider-dependent (mock: instant, Gemini: 1-2 seconds)

