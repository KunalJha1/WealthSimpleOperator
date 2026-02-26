# Repository Guidelines

## Project Structure & Module Organization
- Primary application code lives in `wealthsimple-operator/`.
- `wealthsimple-operator/backend/`: FastAPI + SQLAlchemy service (`main.py`, `routes/`, `operator_engine.py`, `ai/`).
- `wealthsimple-operator/frontend/`: Next.js App Router UI (`app/`, `components/`, `lib/`).
- `wealthsimple-operator/data/`: generated artifacts like `seed_output.json` and `client_insights.json`.
- Runtime files (`operator.db`, WAL/journal files, `.env`) should stay local and out of commits.

## Build, Test, and Development Commands
- Backend setup:
  - `cd wealthsimple-operator/backend`
  - `python -m venv venv; .\\venv\\Scripts\\activate`
  - `pip install -r requirements.txt`
- Backend run:
  - `python seed.py` (initialize demo data)
  - `python main.py` (API at `http://localhost:8000`)
- Frontend setup/run:
  - `cd wealthsimple-operator/frontend && npm install`
  - `npm run dev` (UI at `http://localhost:3000`)
  - `npm run build` (production build)
  - `npm run lint` (ESLint via Next.js)

## Coding Style & Naming Conventions
- Python: PEP 8, 4-space indentation, `snake_case` for functions/variables, `PascalCase` for classes.
- TypeScript/React: strongly typed props/models, `PascalCase` component files (e.g., `PriorityQueue.tsx`), `camelCase` for functions/hooks.
- Keep frontend API types aligned with backend payloads (`frontend/lib/types.ts` and backend route schemas).

## Testing Guidelines
- No committed automated test suite yet; use a minimum smoke-check baseline:
  - `npm run lint` in `frontend/`
  - `python -m py_compile *.py ai\\*.py routes\\*.py` in `backend/`
  - Manual flow: run operator, open `/operator`, `/alerts/[id]`, and `/audit-log`.
- For new tests, use `test_*.py` (backend) and `*.test.ts(x)` (frontend).

## Commit & Pull Request Guidelines
- Existing history favors short, imperative messages (for example: `first batch`, `Made the gitignore ignore env files`).
- Recommended format going forward: `<area>: <imperative summary>` (example: `frontend: tighten alert detail loading state`).
- PRs should include: summary, changed paths/endpoints, verification steps, and screenshots for UI updates.

## Security & Configuration Tips
- Never commit secrets, `.env` files, or real client data.
- Backend provider config belongs in `wealthsimple-operator/backend/.env` (`PROVIDER`, `GEMINI_API_KEY`).
- Use `PROVIDER=mock` for deterministic local development.
