## Wealthsimple Operator Console

Internal demo of an AI-native portfolio operations triage tool for advisors. This is **not** a consumer app and must **not** be used for financial advice or trade recommendations. The system monitors a universe of client portfolios, flags items that merit human review, explains why, and records an audit trail of operator actions.

### Architecture overview

- **Frontend**: Next.js (App Router) + TypeScript + Tailwind CSS
  - Sidebar layout with clean, internal-dashboard styling (white background, soft borders, Inter font, minimal green accents).
  - Pages:
    - `/operator` – run the operator, see the priority queue and recent audit events.
    - `/alerts/[id]` – alert detail with risk brief, AI reasoning, confidence, decision trace, and change detection.
    - `/monitoring-universe` – monitoring universe metrics and simple distributions.
    - `/audit-log` – full audit log table.
    - `/settings` – provider selection visibility, scan interval display, API health.
- **Backend**: FastAPI + SQLite (SQLAlchemy)
  - Endpoints:
    - `POST /operator/run` – run a full scan, create alerts, return summary and top alerts.
    - `GET /alerts` – list alerts (filters: priority, status).
    - `GET /alerts/{id}` – alert detail with client + portfolio + reasoning + decision trace + change detection.
    - `POST /alerts/{id}/action` – mark `reviewed` / `escalate` / `false_positive` and log to audit.
    - `GET /audit` – audit log with basic filters.
    - `GET /portfolios/summary` – counts and metrics for the Monitoring Universe view.
    - `GET /health` – current AI provider (mock or Gemini) and basic API/DB status.
  - SQLite schema models:
    - `Client`, `Portfolio`, `Position` – monitoring universe.
    - `Run` – one operator run.
    - `Alert` – AI triage output tied to a portfolio and run.
    - `AuditEvent` – immutable audit trail entries for runs and alert actions.
- **AI layer**: provider abstraction with mock-by-default behaviour
  - `ai/provider.py` exposes a single `AIProvider` interface and `get_provider()` factory.
  - `ai/mock_provider.py` – deterministic, metrics-only triage logic that always works locally.
  - `ai/gemini_provider.py` – optional Google Gemini provider behind the same interface, with:
    - Strict JSON-only schema.
    - Fallback to mock provider on any error.
  - `ai/prompt_builder.py` – builds a JSON-only prompt with:
    - Portfolio risk metrics + last metrics.
    - Client and portfolio context.
    - AI/Human responsibility boundary instructions.

### AI vs Human responsibility

The console is explicitly designed so that:

- **AI responsibility: monitoring/triage**
  - Compute portfolio-level metrics:
    - `concentration_score` – max single-position weight (0–10).
    - `drift_score` – deviation from target allocation (0–10).
    - `volatility_proxy` – deterministic volatility proxy (0–10).
    - `risk_score` – average of the three signals (0–10).
  - Rank portfolios by triage **priority** (`HIGH`/`MEDIUM`/`LOW`).
  - Estimate **confidence** (0–100) for each triage decision.
  - Provide **reasoning bullets** grounded in the metrics.
  - Provide **decision trace steps** so operators can audit how a score was reached.
  - Surface **change detection** vs the last run.

- **Human responsibility: investment decisions**
  - All investment recommendations, trades, rebalancing, and allocation decisions.
  - All client contact, escalation, and interpretation of the AI’s outputs.
  - Labelling alerts as **reviewed**, **escalated**, or **false positive**.

The AI layer is **not allowed** to:

- Suggest or imply **buy/sell** instructions.
- Suggest target allocations or **“rebalance to X%”** instructions.
- Provide consumer-facing financial advice.

The UI reinforces this boundary via a dedicated `ResponsibilityBoundary` component that appears on key pages (e.g. alert detail, settings).

### AI output schema

The AI layer (mock or Gemini) must return **strict JSON only** (no markdown) with this schema:

```json
{
  "priority": "HIGH|MEDIUM|LOW",
  "confidence": 0,
  "event_title": "string",
  "summary": "string",
  "reasoning_bullets": ["string"],
  "human_review_required": true,
  "suggested_next_step": "string",
  "decision_trace_steps": [
    { "step": "string", "detail": "string" }
  ],
  "change_detection": [
    { "metric": "string", "from": "string", "to": "string" }
  ]
}
```

`ai/mock_provider.py` implements this contract deterministically from the risk metrics, and `ai/gemini_provider.py` enforces it via the prompt and JSON parsing (falling back to mock on any violation).

### Backend: environment & provider selection

Backend configuration lives in `backend/.env` (template in `backend/.env.example`):

```bash
GEMINI_API_KEY=your_key_here
PROVIDER=mock
```

- If `GEMINI_API_KEY` is missing or empty, or `PROVIDER=mock`, the backend uses the **mock provider**.
- If `GEMINI_API_KEY` is set and `PROVIDER` is not explicitly `mock`, the backend attempts to use the **Gemini provider**, falling back to mock on any runtime error.
- This selection is reflected in:
  - `GET /health` (`provider`, `raw_provider`, `gemini_configured`).
  - The `/settings` page (display-only provider and health status).

To swap providers:

- **Preferred (demo) path**: edit `backend/.env`:
  - Set `PROVIDER=mock` for deterministic local runs without keys.
  - Set `PROVIDER=gemini` and add a valid `GEMINI_API_KEY` to enable Gemini.
- **Advanced**: adjust the factory in `backend/ai/provider.py` if you want different selection logic or to plug in a different LLM altogether.

### Backend: running locally

```bash
cd wealthsimple-operator/backend
python -m venv venv
venv\Scripts\activate  # Windows
# or on macOS/Linux: source venv/bin/activate

pip install -r requirements.txt

cp .env.example .env
# Edit .env and add your GEMINI_API_KEY (optional; mock provider works without it)

python seed.py         # one-time: create SQLite DB and generate ~70 portfolios
python main.py         # starts FastAPI with uvicorn on http://localhost:8000
```

- SQLite DB is created as `operator.db` in `backend/`.
- Seed script inserts:
  - ~70 clients across `Mass`, `Premium`, `HNW` segments.
  - Portfolios with realistic risk profiles and target allocations.
  - 5–12 positions per portfolio across equities, fixed income, ETFs, and cash.
- A snapshot of the seeded data is exported to `data/seed_output.json`.

### Frontend: running locally

```bash
cd wealthsimple-operator/frontend
npm install

cp .env.example .env.local
# NEXT_PUBLIC_API_BASE_URL is pre-filled with /api
# Next.js rewrites /api/* to OPERATOR_BACKEND_ORIGIN (default http://127.0.0.1:8001)

npm run dev            # starts Next.js on http://localhost:3000
```

The frontend calls the backend exclusively via HTTP; no API keys are exposed client-side.

### Demo walkthrough

Once both services are running:

1. **Seed and start backend**
   - Run `python seed.py` (first time only).
   - Run `python main.py` and visit `http://localhost:8000/docs` to see the API.
2. **Start frontend**
   - Run `npm run dev` from `frontend/`.
   - Open `http://localhost:3000`.
3. **Operator console (`/operator`)**
   - The status bar shows:
     - Current provider (`Mock` or `Gemini`).
     - Whether Gemini is configured.
     - Timestamp of the last completed run.
   - Click **“Run operator”**:
     - Backend computes risk metrics for every portfolio.
     - AI provider scores each portfolio and creates `Alert` records.
     - A new `Run` and corresponding `AuditEvent`s are recorded.
   - The **Priority queue** updates with top alerts from the latest run.
   - A **Recent audit events** table shows the last 10 audit entries.
4. **Alert detail (`/alerts/[id]`)**
   - Click a row in the Priority queue to open alert detail.
   - You’ll see:
     - **Risk brief** – client context, portfolio summary, and the four risk metrics.
     - **AI summary & reasoning** – bullets grounded in concentration, drift, and volatility.
     - **Confidence** and **priority** badges.
     - **Responsibility boundary** callout.
     - **Decision trace** – collapsible step-by-step reasoning.
     - **Change detection** – what moved vs the last run (if any).
   - Use the action buttons:
     - **Mark reviewed**
     - **Escalate**
     - **Mark false positive**
   - Each action updates the `Alert.status` and appends an `AuditEvent`.
5. **Monitoring universe (`/monitoring-universe`)**
   - See counts of clients and portfolios under monitoring.
   - Simple metrics:
     - Alerts by priority.
     - Alerts by status.
     - Average alerts per run.
     - % of alerts requiring human review.
6. **Audit log (`/audit-log`)**
   - Table of all `AuditEvent`s with timestamps, event types, actor, and condensed details.
7. **Settings (`/settings`)**
   - Shows:
     - Active provider and whether Gemini is configured.
     - Database health.
   - Includes a **scan interval** selector that is intentionally display-only (no scheduler).
   - Reinforces the AI/Human responsibility boundary.

### Known limitations (what would break first at scale)

1. **Alert deduplication**
   - The operator creates a new `Alert` for every run and portfolio, even when nothing changed.
   - At scale this would generate many near-duplicate alerts; a deduplication / suppression layer is needed.
2. **Audit log growth**
   - All `AuditEvent`s are stored in a single table with no pagination/archival strategy.
   - As the log grows, queries (especially joined filters by alert priority/status) will slow down.
3. **Confidence calibration**
   - The mock provider returns **fixed, heuristic** confidence scores based on thresholds.
   - A real Gemini-backed provider would need calibration against observed outcomes and human labels.
4. **Concurrency & SQLite**
   - SQLite is used for simplicity and will lock under concurrent writes.
   - In a production deployment this should move to a production-grade database plus an async task queue for heavy scans.
5. **PII exposure in audit trail**
   - Client names/emails are stored in the main tables and surfaced indirectly through audit details.
   - A real system should introduce a redaction/anonymization layer for logs and analytics outputs.

### Next improvements (not implemented in this MVP)

These are intentionally **out of scope** for the first version but natural follow-ups:

- **Autonomous scheduled runs**
  - Background scheduler / job queue for periodic operator scans (e.g. every hour / daily).
- **Richer AI provider swapping**
  - Pluggable provider registry with UI- or config-driven selection (e.g. Gemini vs other LLMs).
  - Multi-tenant routing (different providers or configs per advisor team).
- **RBAC and multi-user support**
  - Authentication, authorization, and per-user audit trails.
  - Role-based perspectives (advisor vs supervisor vs operations).
- **PII redaction and data minimization**
  - Automatic redaction in logs and AI prompts.
  - Tiered data access for different roles/regions.
- **Alert deduplication and suppression**
  - Collapse identical alerts across runs.
  - Introduce snoozing / suppression windows.
- **Evaluation and calibration metrics**
  - Track outcomes of escalations and reviews.
  - Evaluate triage precision/recall and recalibrate thresholds.
- **Pagination and archival**
  - Proper pagination for alert and audit tables.
  - Archival policy for old runs and events.

### File layout (summary)

- `backend/`
  - `.env`, `.env.example` – backend env config.
  - `main.py` – FastAPI app entrypoint and `/health` endpoint.
  - `db.py` – SQLite engine and session helpers.
  - `models.py` – SQLAlchemy models + Pydantic schemas.
  - `seed.py` – generate fake clients/portfolios/positions and export `data/seed_output.json`.
  - `operator_engine.py` – risk metric computation, AI provider calls, run summary, monitoring summary.
  - `ai/` – provider abstraction, Gemini + mock providers, prompt builder.
  - `routes/` – `operator.py`, `alerts.py`, `audit.py`, `portfolios.py`.
- `frontend/`
  - `.env.example`, `.env.local` – frontend API base URL config.
  - `next.config.js`, `tsconfig.json`, `tailwind.config.js`, `package.json` – standard Next.js/Tailwind setup.
  - `app/` – App Router pages and root layout.
  - `components/` – shared UI (sidebar, badges, queue, audit table, responsibility boundary, etc.).
  - `lib/` – `api.ts`, `types.ts`, `utils.ts` for API calls and shared types/helpers.
- `data/seed_output.json` – snapshot of the seeded monitoring universe.

With this structure in place, you can run the backend and frontend with a single command each and get an end-to-end demo of the Wealthsimple Operator Console that defaults to a local, deterministic mock provider but can be switched to Gemini through configuration.

