# Wealthsimple Operator

AI-assisted internal operations console for portfolio monitoring, alert triage, and audit logging.

This project is a local/demo environment and is not intended for direct trading execution or consumer-facing financial advice.

## Screenshots (Placeholder Paths)

Add your screenshots at these paths (or rename and update the README links):

- `wealthsimple-operator/docs/images/operator-overview.png`
- `wealthsimple-operator/docs/images/alert-detail.png`
- `wealthsimple-operator/docs/images/meeting-notes.png`
- `wealthsimple-operator/docs/images/monitoring-universe.png`
- `wealthsimple-operator/docs/images/scenario-lab.png`

### Operator Overview
![Operator Overview](wealthsimple-operator/docs/images/operator-overview.png)

### Alert Detail
![Alert Detail](wealthsimple-operator/docs/images/alert-detail.png)

### Meeting Notes
![Meeting Notes](wealthsimple-operator/docs/images/meeting-notes.png)

### Monitoring Universe
![Monitoring Universe](wealthsimple-operator/docs/images/monitoring-universe.png)

### Scenario Lab
![Scenario Lab](wealthsimple-operator/docs/images/scenario-lab.png)

## Tech Stack

- Backend: FastAPI, SQLAlchemy, SQLite, Python
- Frontend: Next.js (App Router), React, TypeScript, Tailwind CSS
- AI Providers: `mock` (default), `gemini` (optional)

## Repository Structure

```text
wealthsimple-operator/
|- backend/
|  |- ai/
|  |- routes/
|  |- main.py
|  |- operator_engine.py
|  |- seed.py
|  |- requirements.txt
|- frontend/
|  |- app/
|  |- components/
|  |- lib/
|  |- package.json
|- data/
|  |- seed_output.json
|- docs/
|  |- images/
|- README.md
```

## Prerequisites

- Python 3.10+
- Node.js 18+
- npm 9+

## Quick Start

### 1) Backend Setup

```bash
cd wealthsimple-operator/backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Create backend env file:

```bash
copy .env.example .env
```

Optional provider config in `backend/.env`:

- `PROVIDER=mock` for deterministic local runs
- `PROVIDER=gemini` plus `GEMINI_API_KEY=...` to use Gemini

Initialize demo data:

```bash
python seed.py
```

Start backend API:

```bash
python main.py
```

Backend runs at:

- `http://127.0.0.1:8001` if using `backend/.env.example` values
- otherwise fallback is `http://127.0.0.1:8000`

Swagger docs:

- `http://127.0.0.1:8001/docs` (or `:8000/docs` if fallback port)

### 2) Frontend Setup

```bash
cd wealthsimple-operator/frontend
npm install
```

Create frontend env file:

```bash
copy .env.example .env.local
```

Start frontend:

```bash
npm run dev
```

Frontend runs at:

- `http://localhost:3000`

The frontend proxies `/api/*` to `OPERATOR_BACKEND_ORIGIN` in `frontend/next.config.js`.

## Core App Routes

- `/operator` - Run operator scans and review queue
- `/alerts/[id]` - Alert detail and operator actions
- `/monitoring-universe` - Monitoring metrics view
- `/audit-log` - Full audit trail
- `/settings` - Provider and health settings
- `/risk-dashboard` - Risk dashboard view
- `/simulations` - Scenario simulations
- `/meeting-notes` - Meeting note workflows
- `/contact-scheduler` - Contact scheduling
- `/tax-loss-harvesting` - Tax loss harvesting workflow
- `/auto-reallocation` - Auto reallocation workflow

## Key Backend Endpoints

- `POST /operator/run` - Execute portfolio scan and generate alerts
- `GET /alerts` - List alerts
- `GET /alerts/{id}` - Alert details
- `POST /alerts/{id}/action` - Mark reviewed/escalated/false positive
- `GET /audit` - Fetch audit events
- `GET /portfolios/summary` - Monitoring universe summary
- `GET /health` - Provider + API/DB status

## Development Commands

### Backend

```bash
cd wealthsimple-operator/backend
python -m py_compile *.py ai\*.py routes\*.py
```

### Frontend

```bash
cd wealthsimple-operator/frontend
npm run lint
npm run build
```

## Environment Variables

### Backend (`backend/.env`)

- `PROVIDER` = `mock` or `gemini`
- `GEMINI_API_KEY` = required only for Gemini
- `UVICORN_HOST` = bind host (example: `0.0.0.0`)
- `UVICORN_PORT` = API port (example: `8001`)
- `UVICORN_RELOAD` = `1` to enable autoreload

### Frontend (`frontend/.env.local`)

- `NEXT_PUBLIC_API_BASE_URL=/api`
- `OPERATOR_BACKEND_ORIGIN=http://127.0.0.1:8001` (used by rewrites)

## Security Notes

- Do not commit `.env`, database files, or real client data.
- Use `PROVIDER=mock` for deterministic local demos.

## GitHub Photo Placeholder Notes

If images do not appear on GitHub yet, that is expected until you add files at the paths above.
You can also create a subfolder like `docs/images/v1/` and update the markdown links later.
