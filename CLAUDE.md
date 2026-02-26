# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Quick Start: Commands

### Backend
```bash
cd wealthsimple-operator/backend
python -m venv venv
venv\Scripts\activate  # Windows; use source venv/bin/activate on macOS/Linux
pip install -r requirements.txt
cp .env.example .env  # Add GEMINI_API_KEY if needed; PROVIDER=mock works without it
python seed.py         # One-time: creates and seeds SQLite DB (operator.db)
python main.py         # Starts API at http://localhost:8000
```

### Frontend
```bash
cd wealthsimple-operator/frontend
npm install
npm run dev            # Starts Next.js at http://localhost:3000
npm run build          # Production build
npm run lint           # Run ESLint
```

### Optional: Background backfill (populates insights)
```bash
cd wealthsimple-operator/backend
python background_backfill.py --runs 5 --insights-limit 50
```

## Architecture Overview

### Core Flow
1. **Operator run** (`POST /operator/run`) → computes risk metrics for all portfolios in `operator_engine.py`
2. **AI triage** → AI provider (mock or Gemini) scores each portfolio, returns structured JSON alert
3. **Database** → `Alert`, `Run`, `AuditEvent` records stored in SQLite
4. **UI** (`/operator`) → displays priority queue and audit trail

### Key Architectural Concepts

#### Provider Abstraction (Critical Pattern)
The AI layer is abstracted behind `backend/ai/provider.py`:
- **`AIProvider`** interface: all providers implement `analyze_portfolio(portfolio_data) → Dict`
- **Mock provider** (`mock_provider.py`): deterministic metrics-only scoring—**no external calls**
- **Gemini provider** (`gemini_provider.py`): uses Google Gemini API; falls back to mock on any error
- **Factory** (`get_provider()`): selected via `backend/.env` (`PROVIDER=mock` or `PROVIDER=gemini`)

**When modifying**: keep strict separation—mock provider must always work locally; Gemini provider must gracefully degrade.

#### AI/Human Responsibility Boundary
This is **explicitly enforced** in the code and UI:

**AI responsibility** (risk metrics, triage, reasoning):
- Compute `concentration_score`, `drift_score`, `volatility_proxy` (0–10 scale)
- Rank by priority: `HIGH`/`MEDIUM`/`LOW`
- Return structured JSON with reasoning bullets, decision trace, and change detection

**Human responsibility** (all investment decisions):
- Review alerts, escalate, mark false positives
- Client contact, rebalancing, allocation decisions
- UI has `ResponsibilityBoundary` component reinforcing this

**AI is forbidden** from suggesting trades, target allocations, or consumer-facing advice.

#### Alert/Run/AuditEvent Model
- **`Run`**: one operator execution; tracks when it ran
- **`Alert`**: AI triage output for a portfolio + run; has `status` (unreviewed/reviewed/escalated/false_positive) and `priority` (HIGH/MEDIUM/LOW)
- **`AuditEvent`**: immutable log entry for every run and alert action (reviewed/escalated/false_positive); actor + timestamp

All three drive the UI: `/operator` shows latest run's alerts; `/audit-log` shows event stream.

### Database & Models
- **`backend/models.py`**: SQLAlchemy models (`Client`, `Portfolio`, `Position`, `Alert`, `Run`, `AuditEvent`) + Pydantic schemas
- **`backend/db.py`**: SQLite engine and session management
- **Schema**: see README.md for details; minimal—no cascade deletes or triggers

### Routes
- **`backend/routes/operator.py`**: `POST /operator/run` (main entry point); `GET /operator/summary`
- **`backend/routes/alerts.py`**: CRUD for alerts + action endpoint (`POST /alerts/{id}/action`)
- **`backend/routes/audit.py`**: `/audit` query (filter by priority/status)
- **`backend/routes/portfolios.py`**: `/portfolios/summary` (monitoring universe metrics)

### Frontend Structure
- **Pages** (`frontend/app/`): `/operator`, `/alerts/[id]`, `/monitoring-universe`, `/audit-log`, `/settings`
- **Components** (`frontend/components/`): `Sidebar`, `PriorityQueue`, `RiskBrief`, `Buttons`, etc.
- **Lib** (`frontend/lib/`): `api.ts` (HTTP calls), `types.ts` (shared TS interfaces), `utils.ts` (helpers)

**Key pattern**: API calls via `api.ts`; responses typed against `types.ts`; keep frontend stateless (all state on backend).

## Common Development Tasks

### Adding an AI Provider
1. Create `backend/ai/new_provider.py`; implement `AIProvider` interface with `analyze_portfolio()`
2. Return strict JSON matching the schema in README.md
3. Update factory in `backend/ai/provider.py` to conditionally import and use it
4. Add env var (e.g., `PROVIDER=new_provider`) and test fallback to mock

### Adding an Alert Action
1. Add new status value to `Alert.status` enum in `backend/models.py`
2. Add route handler in `backend/routes/alerts.py` to update alert + log `AuditEvent`
3. Add UI button in `frontend/components/Buttons.tsx` or alert detail page
4. Call `/alerts/{id}/action` endpoint with new action type

### Adding a Dashboard Metric
1. Compute metric in `backend/operator_engine.py` (in `OperatorEngine.get_monitoring_summary()`)
2. Add field to `MonitoringSummary` Pydantic schema in `backend/models.py`
3. Expose via new endpoint or extend existing `/portfolios/summary`
4. Render in `/monitoring-universe` page

### Debugging an Alert
1. Check `backend/main.py` logs (run the API with debug enabled)
2. Query the database directly: `python -c "from db import get_session; from models import Alert; print([a for a in get_session().query(Alert).all()])"`
3. Check the alert's `reasoning_bullets` and `decision_trace_steps` (populated by AI provider)
4. If using Gemini: check fallback to mock (confirm in `/health` endpoint)

## Code Style & Conventions
- **Python**: PEP 8, 4-space indentation, `snake_case` functions/variables, `PascalCase` classes
- **TypeScript/React**: strict typing, `PascalCase` components, `camelCase` functions/hooks, avoid `any`
- **API shapes**: keep synchronized with `frontend/lib/types.ts` (Pydantic schemas on backend must match)
- **Error handling**: backend returns 400/422 with structured `detail`; frontend displays in UI

## Testing & Validation
- **Before commit**: `npm run lint` in `frontend/` + `python -m py_compile backend/*.py` for syntax
- **Smoke test**: run backend + frontend, execute one `/operator/run`, verify `/operator` and `/audit-log` render correctly
- **No automated test suite yet**: prioritize manual end-to-end verification

## Configuration
- **Backend env** (`backend/.env`):
  - `PROVIDER` → `mock` (default) or `gemini`
  - `GEMINI_API_KEY` → (required if `PROVIDER=gemini`)
- **Frontend env** (`frontend/.env.local`):
  - `NEXT_PUBLIC_API_BASE_URL` → default is `http://localhost:8000`

## Known Limitations & Future Work
See README.md "Known limitations" and "Next improvements" sections for context on:
- Alert deduplication (creates duplicates every run)
- Audit log growth (no archival)
- Confidence calibration (mock provider uses fixed heuristics)
- SQLite concurrency (will lock under writes)
- PII exposure in audit trail

## Project References
- **AGENTS.md**: coding style, naming conventions, commit/PR guidelines
- **README.md**: full architecture, AI/Human boundary, file layout, demo walkthrough
- **`data/seed_output.json`**: snapshot of seeded monitoring universe (portfolios, positions)
