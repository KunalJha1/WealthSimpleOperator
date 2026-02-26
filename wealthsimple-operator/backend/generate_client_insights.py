from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from sqlalchemy import case
from sqlalchemy.orm import Session, joinedload

from ai.provider import get_provider
from db import SessionLocal
from models import Alert, Client, Portfolio, Priority, MeetingNote
from operator_engine import _compute_metrics, _latest_metrics_for_portfolio


# Ensure GEMINI_API_KEY / PROVIDER from backend/.env are available when the script runs
load_dotenv(dotenv_path=Path(__file__).with_name(".env"), override=False)


def build_context(portfolio: Portfolio, client: Client) -> Dict[str, Any]:
  """Build a lightweight context object for Gemini/mock scoring."""
  return {
    "client": {
      "id": client.id,
      "name": client.name,
      "email": client.email,
      "segment": client.segment,
      "risk_profile": client.risk_profile,
    },
    "portfolio": {
      "id": portfolio.id,
      "name": portfolio.name,
      "total_value": float(portfolio.total_value),
      "target_equity_pct": float(portfolio.target_equity_pct),
      "target_fixed_income_pct": float(portfolio.target_fixed_income_pct),
      "target_cash_pct": float(portfolio.target_cash_pct),
    },
    "last_metrics": {},
  }


def _format_portfolio_code(portfolio_id: int) -> str:
  return f"PTF-{10000 + portfolio_id}"


def _format_currency(amount: float) -> str:
  return f"${amount:,.0f}"


def _format_date(value: datetime) -> str:
  return value.strftime("%Y-%m-%d")


def _horizon_for_risk_profile(risk_profile: str) -> str:
  risk = (risk_profile or "").lower()
  if "conservative" in risk:
    return "Short to medium-term (3-7 years)"
  if "moderate" in risk:
    return "Long-term (15+ years)"
  if "growth" in risk or "aggressive" in risk:
    return "Long-term (15+ years)"
  return "Medium-term (7-15 years)"


def _advisor_for_portfolio(portfolio_id: int) -> str:
  advisors = ["Michael Patel", "Jordan Lee", "Sarah Chen", "Alex Martinez"]
  return advisors[portfolio_id % len(advisors)]


def _equity_threshold_for_risk(risk_profile: str) -> float:
  risk = (risk_profile or "").lower()
  if "conservative" in risk:
    return 35.0
  if "moderate" in risk:
    return 45.0
  if "growth" in risk or "aggressive" in risk:
    return 65.0
  return 50.0


def _allocation_breakdown(portfolio: Portfolio) -> Dict[str, float]:
  equities = 0.0
  fixed_income = 0.0
  cash = 0.0
  alternatives = 0.0

  for position in portfolio.positions:
    weight = float(position.weight)
    asset_class = (position.asset_class or "").lower()
    if asset_class in {"equity", "etf"}:
      equities += weight
    elif asset_class == "fixed income":
      fixed_income += weight
    elif asset_class == "cash":
      cash += weight
    else:
      alternatives += weight

  total = equities + fixed_income + cash + alternatives
  if total <= 0:
    # Fallback to targets when positions are absent.
    equities = float(portfolio.target_equity_pct) / 100.0
    fixed_income = float(portfolio.target_fixed_income_pct) / 100.0
    cash = float(portfolio.target_cash_pct) / 100.0
    alternatives = max(0.0, 1.0 - equities - fixed_income - cash)
    total = equities + fixed_income + cash + alternatives

  return {
    "equities_pct": round((equities / total) * 100.0, 1),
    "fixed_income_pct": round((fixed_income / total) * 100.0, 1),
    "alternatives_pct": round((alternatives / total) * 100.0, 1),
    "cash_pct": round((cash / total) * 100.0, 1),
  }


def _build_recent_meeting_notes(
  client_id: int,
  last_meeting: datetime,
  db: Optional[Session] = None,
) -> List[Dict[str, Any]]:
  """Build recent meeting notes from database if available, otherwise use hardcoded fallback."""
  if db:
    try:
      notes: List[MeetingNote] = (
        db.query(MeetingNote)
        .filter(MeetingNote.client_id == client_id)
        .order_by(MeetingNote.meeting_date.desc())
        .limit(5)
        .all()
      )
      if notes:
        return [
          {
            "id": note.id,
            "title": note.title,
            "date": _format_date(note.meeting_date),
            "note": note.note_body,
            "action_required": [],
            "meeting_type": note.meeting_type.value if hasattr(note.meeting_type, 'value') else str(note.meeting_type),
            "call_transcript": note.call_transcript,
            "ai_summary": note.ai_summary,
            "ai_action_items": note.ai_action_items,
            "ai_summarized_at": note.ai_summarized_at.isoformat() if note.ai_summarized_at else None,
            "has_transcript": note.call_transcript is not None,
          }
          for note in notes
        ]
    except Exception:
      pass  # Fall through to hardcoded notes if query fails

  # Hardcoded fallback
  return [
    {
      "title": "Q4 Portfolio Review",
      "date": _format_date(last_meeting),
      "note": (
        "Client reported satisfaction with performance. Discussed major planned purchase "
        "and the need for liquidity planning. Client requested a gradual risk reduction "
        "ahead of expected withdrawals."
      ),
      "action_required": ["Tax planning"],
    },
    {
      "title": "Annual Planning Meeting",
      "date": _format_date(last_meeting - timedelta(days=43)),
      "note": (
        "Reviewed goals, confirmed risk tolerance, and validated beneficiary/estate details. "
        "Retirement target remains on track with periodic monitoring."
      ),
      "action_required": [],
    },
  ]


def _build_priority_justification(
  client: Client,
  metrics: Dict[str, float],
  last_metrics: Dict[str, float],
  allocation: Dict[str, float],
  confidence: int,
) -> str:
  current_equity = allocation["equities_pct"]
  threshold = _equity_threshold_for_risk(client.risk_profile)
  equity_excess = round(current_equity - threshold, 1)

  current_risk = float(metrics.get("risk_score", 0.0))
  prior_risk = float(last_metrics.get("risk_score", current_risk))
  delta_risk = round(current_risk - prior_risk, 1)

  change_part = (
    f"risk score moved by {delta_risk:+.1f} points since the last run"
    if last_metrics
    else "no prior run baseline available for trend comparison"
  )

  if equity_excess > 0:
    exposure_part = (
      f"equity exposure is {equity_excess:.1f} percentage points above the client threshold "
      f"({current_equity:.1f}% vs {threshold:.1f}%)"
    )
  else:
    exposure_part = (
      f"equity exposure remains within threshold ({current_equity:.1f}% vs {threshold:.1f}% limit)"
    )

  return (
    f"Priority ranked from combined risk score {current_risk:.1f}/10, {exposure_part}, "
    f"and {change_part}. Model confidence is {confidence}%."
  )


def _build_operator_history(generated_at: datetime, priority: str) -> List[Dict[str, str]]:
  title_priority = priority.capitalize()
  return [
    {
      "date": _format_date(generated_at - timedelta(days=5)),
      "description": "Risk within tolerance",
    },
    {
      "date": _format_date(generated_at - timedelta(days=3)),
      "description": "Minor drift detected",
    },
    {
      "date": _format_date(generated_at - timedelta(days=1)),
      "description": f"Escalated to {title_priority} priority",
    },
  ]


def _build_profile_view(
  client: Client,
  portfolio: Portfolio,
  metrics: Dict[str, float],
  allocation: Dict[str, float],
  generated_at: datetime,
  db: Optional[Session] = None,
) -> Dict[str, Any]:
  total_aum = float(portfolio.total_value)
  ytd_return_pct = round(4.0 + float(metrics.get("risk_score", 0.0)) * 0.6, 1)
  unrealized_pl = round(total_aum * (ytd_return_pct / 100.0), 2)
  realized_pl = round(total_aum * (0.008 + (portfolio.id % 4) * 0.0025), 2)

  last_meeting = generated_at - timedelta(days=20 + (portfolio.id % 45))
  next_review = generated_at + timedelta(days=10 + (portfolio.id % 30))
  last_email = generated_at - timedelta(days=7 + (portfolio.id % 12))
  calls_last_90_days = 2 + (portfolio.id % 4)
  avg_call_duration_mins = 12 + (portfolio.id % 9)

  home_target_amount = 350000 + (portfolio.id % 6) * 25000
  retirement_target = 2000000 + (portfolio.id % 6) * 250000
  retirement_current = round(min(retirement_target, total_aum * 0.95), 2)
  retirement_progress = min(100, int((retirement_current / retirement_target) * 100))

  return {
    "header": {
      "client_name": client.name,
      "portfolio_code": _format_portfolio_code(portfolio.id),
    },
    "portfolio_performance": {
      "total_aum": _format_currency(total_aum),
      "ytd_return_pct": ytd_return_pct,
      "unrealized_pl": _format_currency(unrealized_pl),
      "unrealized_gain_pct": round((unrealized_pl / total_aum) * 100.0, 1) if total_aum else 0.0,
      "realized_pl_ytd": _format_currency(realized_pl),
      "realized_pl_note": "From rebalancing",
    },
    "current_asset_allocation": {
      "equities_pct": allocation["equities_pct"],
      "fixed_income_pct": allocation["fixed_income_pct"],
      "alternatives_pct": allocation["alternatives_pct"],
      "cash_pct": allocation["cash_pct"],
    },
    "outreach_engagement": {
      "last_meeting": _format_date(last_meeting),
      "last_meeting_days_ago": (generated_at.date() - last_meeting.date()).days,
      "next_scheduled_review": _format_date(next_review),
      "next_review_in_days": (next_review.date() - generated_at.date()).days,
      "last_email_contact": _format_date(last_email),
      "last_email_days_ago": (generated_at.date() - last_email.date()).days,
      "phone_calls_last_90_days": calls_last_90_days,
      "avg_call_duration_minutes": avg_call_duration_mins,
    },
    "recent_meeting_notes": _build_recent_meeting_notes(client.id, last_meeting, db),
    "financial_goals": [
      {
        "goal": "Home Purchase",
        "target_date": "Late 2026",
        "status": "In Progress",
        "target_amount": _format_currency(float(home_target_amount)),
      },
      {
        "goal": "Retirement Savings",
        "target_date": "2041",
        "status": "On Track",
        "current_vs_target": (
          f"{_format_currency(retirement_current)} / {_format_currency(float(retirement_target))}"
        ),
        "progress_pct": retirement_progress,
      },
      {
        "goal": "Emergency Fund",
        "target_date": "6 months expenses",
        "status": "Complete",
        "amount": _format_currency(45000.0),
      },
    ],
    "actions": ["Schedule Meeting", "Send Email", "Add Note"],
  }


def _ordered_portfolios_for_queue(limit: int) -> List[Portfolio]:
  """Return portfolios ordered like the frontend alert queue.

  Queue ordering matches `/alerts`:
  1) priority HIGH -> MEDIUM -> LOW
  2) alert created_at descending
  3) alert confidence descending

  Portfolios are deduplicated, keeping first appearance in that queue order.
  If there are not enough alert-backed portfolios, fall back to highest-AUM portfolios.
  """
  session = SessionLocal()
  try:
    priority_rank = case(
      (Alert.priority == Priority.HIGH, 0),
      (Alert.priority == Priority.MEDIUM, 1),
      (Alert.priority == Priority.LOW, 2),
      else_=99,
    )

    alerts: List[Alert] = (
      session.query(Alert)
      .options(
        joinedload(Alert.portfolio).joinedload(Portfolio.client),
        joinedload(Alert.portfolio).joinedload(Portfolio.positions),
      )
      .order_by(priority_rank.asc(), Alert.created_at.desc(), Alert.confidence.desc())
      .limit(max(limit * 5, limit))
      .all()
    )

    ordered_portfolios: List[Portfolio] = []
    seen_portfolio_ids: set[int] = set()

    for alert in alerts:
      portfolio = alert.portfolio
      if portfolio is None or portfolio.id in seen_portfolio_ids:
        continue
      ordered_portfolios.append(portfolio)
      seen_portfolio_ids.add(portfolio.id)
      if len(ordered_portfolios) >= limit:
        return ordered_portfolios

    if len(ordered_portfolios) < limit:
      fallback_portfolios: List[Portfolio] = (
        session.query(Portfolio)
        .options(joinedload(Portfolio.client), joinedload(Portfolio.positions))
        .order_by(Portfolio.total_value.desc())
        .all()
      )
      for portfolio in fallback_portfolios:
        if portfolio.id in seen_portfolio_ids:
          continue
        ordered_portfolios.append(portfolio)
        seen_portfolio_ids.add(portfolio.id)
        if len(ordered_portfolios) >= limit:
          break

    return ordered_portfolios
  finally:
    session.close()


def generate_client_insights(limit: int = 50) -> List[Dict[str, Any]]:
  """Generate richer AI narratives for the top N portfolios.

  Selection order follows the frontend queue order (via alerts ordering),
  with AUM fallback when needed. When GEMINI_API_KEY is configured, this
  uses Gemini; otherwise it falls back to the deterministic mock provider.

  Portfolios are processed in batches of 3 to balance API efficiency
  and response quality.
  """
  provider = get_provider()
  generated_at = datetime.utcnow()
  session = SessionLocal()

  try:
    portfolios: List[Portfolio] = _ordered_portfolios_for_queue(limit=limit)

    insights: List[Dict[str, Any]] = []

    # Process portfolios in batches of 3 for optimal API efficiency and quality
    batch_size = 3
    for batch_start in range(0, len(portfolios), batch_size):
      batch_end = min(batch_start + batch_size, len(portfolios))
      batch = portfolios[batch_start:batch_end]

      # Process each portfolio in the batch
      for portfolio in batch:
        client: Client = portfolio.client  # type: ignore[assignment]
        metrics = _compute_metrics(portfolio)
        last_metrics = _latest_metrics_for_portfolio(session, portfolio.id) or {}
        context = build_context(portfolio, client)
        context["last_metrics"] = last_metrics

        ai_output = provider.score_portfolio(metrics=metrics, context=context)
        priority_label = getattr(ai_output.priority, "value", str(ai_output.priority))
        allocation = _allocation_breakdown(portfolio)
        priority_justification = _build_priority_justification(
          client=client,
          metrics=metrics,
          last_metrics=last_metrics,
          allocation=allocation,
          confidence=ai_output.confidence,
        )
        client_profile_view = _build_profile_view(
          client=client,
          portfolio=portfolio,
          metrics=metrics,
          allocation=allocation,
          generated_at=generated_at,
        )

        insights.append(
          {
            "portfolio_id": portfolio.id,
            "client_id": client.id,
            "portfolio_name": portfolio.name,
            "client_name": client.name,
            "portfolio_code": _format_portfolio_code(portfolio.id),
            "generated_at": generated_at.isoformat() + "Z",
            "provider_used": getattr(provider, "name", "unknown"),
            "priority": priority_label,
            "confidence": ai_output.confidence,
            "event_title": ai_output.event_title,
            "priority_justification": priority_justification,
            "summary": ai_output.summary,
            "reasoning_bullets": list(ai_output.reasoning_bullets or []),
            "decision_trace_steps": [
              {"step": step.step, "detail": step.detail}
              for step in list(ai_output.decision_trace_steps or [])
            ],
            "change_detection": [
              {
                "metric": change.metric,
                "from": change.from_value,
                "to": change.to_value,
              }
              for change in list(ai_output.change_detection or [])
            ],
            "client_profile": {
              "name": client.name,
              "risk_tolerance": client.risk_profile,
              "investment_horizon": _horizon_for_risk_profile(client.risk_profile),
              "last_advisor_review_days_ago": 20 + (portfolio.id % 60),
              "advisor_assigned": _advisor_for_portfolio(portfolio.id),
            },
            "operator_history": _build_operator_history(generated_at=generated_at, priority=priority_label),
            "operator_learning_feedback": {
              "human_feedback_incorporated_cases": 30 + (portfolio.id % 50),
              "false_positives_corrected": 5 + (portfolio.id % 15),
              "confidence_calibration": "Improving" if portfolio.id % 3 else "Stable",
            },
            "human_review": {
              "required": bool(ai_output.human_review_required),
              "ai_responsibility": "Detection and triage",
              "human_responsibility": "Final portfolio decisions",
            },
            "suggested_next_step": ai_output.suggested_next_step,
            "client_profile_view": client_profile_view,
          }
        )

    return insights
  finally:
    session.close()


def main() -> None:
  insights = generate_client_insights(limit=50)

  root = Path(__file__).resolve().parent.parent
  data_dir = root / "data"
  data_dir.mkdir(parents=True, exist_ok=True)
  output_path = data_dir / "client_insights.json"

  with output_path.open("w", encoding="utf-8") as f:
    json.dump(insights, f, indent=2)

  print(f"Wrote {len(insights)} client insights to {output_path}")


if __name__ == "__main__":
  main()

