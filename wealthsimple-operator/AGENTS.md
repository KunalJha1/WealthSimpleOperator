# Repository Guidelines

## Project Structure & Module Organization
- `backend/`: FastAPI + SQLAlchemy service (`main.py`, `routes/`, `models.py`, `operator_engine.py`, `ai/`).
- `frontend/`: Next.js App Router UI (`app/`, `components/`, `lib/`).
- `data/`: generated artifacts (for example `seed_output.json`, `client_insights.json`).
- Root files: `.env.example`, `README.md`.
- Runtime SQLite database: `backend/operator.db`.

## Build, Test, and Development Commands
- Backend setup/run:
  - `cd backend`
  - `python -m venv venv && .\\venv\\Scripts\\activate`
  - `pip install -r requirements.txt`
  - `python seed.py` (reset + seed local DB)
  - `python main.py` (API at `http://localhost:8000`)
- Background backfill (optional):
  - `python background_backfill.py --runs 5 --insights-limit 50`
- Frontend setup/run:
  - `cd frontend && npm install`
  - `npm run dev` (UI at `http://localhost:3000`)
  - `npm run build` (production build)
  - `npm run lint` (Next.js ESLint)

## Coding Style & Naming Conventions
- Python: PEP 8, 4-space indentation, `snake_case` for functions/variables, `PascalCase` for classes.
- TypeScript/React: strict typing, `PascalCase` components, `camelCase` functions/hooks.
- Keep API response shapes aligned with `frontend/lib/types.ts`.
- Prefer small, focused modules; place route handlers in `backend/routes/`.

## Testing Guidelines
- No dedicated test suite is committed yet.
- Minimum validation before PR:
  - `npm run lint` in `frontend/`
  - `python -m py_compile backend/*.py` for touched backend files
  - Manual smoke test: run backend + frontend, execute one operator run, verify `/operator` and `/audit-log`.
- When adding tests, use `test_*.py` (backend) and colocated `*.test.ts(x)` (frontend).

## Commit & Pull Request Guidelines
- Current history uses short, imperative commit messages (for example `first batch`, `Made the gitignore ignore env files`).
- Recommended going forward: `<area>: <imperative summary>` (example: `backend: align insights ordering with alert queue`).
- PRs should include:
  - clear problem/solution summary,
  - impacted paths/endpoints,
  - verification steps,
  - screenshots for UI changes.

## Security & Configuration Tips
- Do not commit `.env` files or API keys.
- Use `backend/.env` for `PROVIDER` and `GEMINI_API_KEY`.
- Use `PROVIDER=mock` for local development when Gemini quota is limited.
