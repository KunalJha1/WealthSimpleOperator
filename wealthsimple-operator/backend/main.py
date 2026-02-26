from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from dotenv import load_dotenv
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from ai.provider import get_provider
from db import Base, engine, get_db
from models import Run
from routes import alerts, audit, meeting_notes, operator, portfolios, simulations


# Load backend/.env so GEMINI_API_KEY and PROVIDER are available
load_dotenv(dotenv_path=Path(__file__).with_name(".env"), override=False)

app = FastAPI(title="Wealthsimple Operator Console Backend")

# Relaxed CORS for local development so the frontend can reach the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_dev_cors_headers(request, call_next):
    """Ensure CORS headers are present even on error responses during local dev."""
    response = await call_next(request)
    response.headers.setdefault("Access-Control-Allow-Origin", "*")
    response.headers.setdefault("Access-Control-Allow-Methods", "*")
    response.headers.setdefault("Access-Control-Allow-Headers", "*")
    return response


@app.on_event("startup")
def on_startup() -> None:
    # Ensure database schema is created.
    Base.metadata.create_all(bind=engine)


app.include_router(operator.router)
app.include_router(alerts.router)
app.include_router(audit.router)
app.include_router(portfolios.router)
app.include_router(simulations.router)
app.include_router(meeting_notes.router)


@app.get("/health")
def health(db: Session = Depends(get_db)) -> Dict[str, Any]:
    provider = get_provider()
    gemini_configured = bool(os.getenv("GEMINI_API_KEY", "").strip())

    db_ok = True
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_ok = False

    last_run_completed_at: datetime | None = db.query(Run.completed_at).order_by(
        Run.completed_at.desc()
    ).limit(1).scalar()

    return {
        "provider": "Gemini" if provider.name == "gemini" else "Mock",
        "raw_provider": provider.name,
        "gemini_configured": gemini_configured,
        "db_ok": db_ok,
        "last_run_completed_at": last_run_completed_at,
    }


@app.get("/")
def root() -> Dict[str, str]:
    return {
        "message": "Wealthsimple Operator Console backend is running.",
        "docs": "/docs",
    }


if __name__ == "__main__":
    import uvicorn

    # On Windows, forcing reload can cause repeated spawn/import cycles when
    # starting from `python main.py`. Keep reload opt-in via env var.
    reload_enabled = os.getenv("UVICORN_RELOAD", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=reload_enabled)

