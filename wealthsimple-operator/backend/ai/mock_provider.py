from __future__ import annotations

from typing import Dict, List

from models import (
    AIOutput,
    ChangeDetectionItem,
    DecisionTraceStep,
    FollowUpDraftContent,
    Priority,
    TranscriptSummary,
)


class MockAIProvider:
    """Deterministic mock provider used when Gemini is not configured.

    The outputs are a pure function of the numeric risk metrics plus their
    movement over time so that confidence and priority are explainable and
    stable from run to run without any external dependency.
    """

    name = "mock"

    def score_portfolio(self, metrics: Dict, context: Dict) -> AIOutput:
        concentration = float(metrics.get("concentration_score", 0.0))
        drift = float(metrics.get("drift_score", 0.0))
        volatility = float(metrics.get("volatility_proxy", 0.0))
        risk_score = float(metrics.get("risk_score", 0.0))

        # Priority heuristic: emphasize concentration and drift first.
        if risk_score >= 7 or concentration >= 8 or drift >= 8:
            priority = Priority.HIGH
        elif risk_score >= 4 or concentration >= 5 or drift >= 5:
            priority = Priority.MEDIUM
        else:
            priority = Priority.LOW

        # Confidence pipeline: numeric function of risk level and trend in metrics
        last_metrics = context.get("last_metrics") or {}
        previous_risk = float(last_metrics.get("risk_score", risk_score))
        delta_risk = risk_score - previous_risk

        # Base confidence comes from absolute risk (0-10 -> ~55-90%)
        base_confidence = 55.0 + risk_score * 3.5

        # Nudge based on trend: rising risk increases confidence, falling lowers it
        trend_adjustment = 0.0
        if delta_risk > 0.5:
            trend_adjustment = 6.0
        elif delta_risk > 0.0:
            trend_adjustment = 3.0
        elif delta_risk < -0.5:
            trend_adjustment = -4.0

        # Priority band adjustment: HIGH a bit higher, LOW a bit lower
        if priority == Priority.HIGH:
            base_confidence += 4.0
        elif priority == Priority.LOW:
            base_confidence -= 4.0

        # Add pseudo-random variation based on portfolio ID for realistic variance
        portfolio_id = context.get("portfolio", {}).get("id", 0)
        variation = ((portfolio_id * 37 + 17) % 41 - 20) / 10.0  # ±2% variation

        confidence = int(
            max(50.0, min(99.0, round(base_confidence + trend_adjustment + variation)))
        )

        human_review_required = priority != Priority.LOW or drift >= 3 or concentration >= 3

        client = context.get("client", {})
        portfolio = context.get("portfolio", {})

        client_name = client.get("name", "client")
        portfolio_name = portfolio.get("name", "portfolio")

        event_title = self._build_event_title(priority, drift, concentration, volatility)
        summary = self._build_summary(
            client_name=client_name,
            portfolio_name=portfolio_name,
            priority=priority,
            risk_score=risk_score,
        )
        reasoning_bullets = self._build_reasoning_bullets(
            concentration=concentration,
            drift=drift,
            volatility=volatility,
            risk_score=risk_score,
        )

        decision_trace_steps = self._build_decision_trace(
            concentration=concentration,
            drift=drift,
            volatility=volatility,
            risk_score=risk_score,
            priority=priority,
        )

        change_detection = self._build_change_detection(metrics, context.get("last_metrics") or {})

        suggested_next_step = (
            "Review alignment with client plan and risk profile given the detected risk signals."
            if human_review_required
            else "Confirm that the portfolio remains within the agreed risk parameters."
        )

        return AIOutput(
            priority=priority,
            confidence=confidence,
            event_title=event_title,
            summary=summary,
            reasoning_bullets=reasoning_bullets,
            human_review_required=human_review_required,
            suggested_next_step=suggested_next_step,
            decision_trace_steps=decision_trace_steps,
            change_detection=change_detection,
        )

    def generate_follow_up_draft(self, alert_context: Dict) -> FollowUpDraftContent:
        client_name = str(alert_context.get("client_name", "Client")).strip()
        advisor_name = str(alert_context.get("advisor_name", "Your advisor team")).strip()
        event_title = str(alert_context.get("event_title", "recent portfolio signal")).strip()
        summary = str(alert_context.get("summary", "We detected a portfolio change worth reviewing.")).strip()
        suggested_next_step = str(
            alert_context.get(
                "suggested_next_step",
                "Review alignment with your risk profile and planned allocation."
            )
        ).strip()

        subject = f"Quick follow-up: {event_title}"
        body = (
            f"Hi {client_name},\n\n"
            f"We wanted to follow up regarding {event_title.lower()} in your portfolio.\n\n"
            f"{summary}\n\n"
            f"Recommended next step: {suggested_next_step}\n\n"
            "If helpful, we can schedule a quick review call to walk through this together.\n\n"
            f"Best,\n{advisor_name}"
        )
        return FollowUpDraftContent(subject=subject, body=body)

    def summarize_transcript(self, transcript: str, context: Dict) -> TranscriptSummary:
        """Deterministically summarize a call transcript based on keyword detection.

        Scans for key topics (RRSP/retirement, home/mortgage, tax, estate, schedule/follow)
        and builds a summary with relevant action items.
        """
        client_name = context.get("client_name", "client")
        risk_profile = context.get("risk_profile", "balanced")

        transcript_lower = transcript.lower()

        # Topic detection
        topics = []
        action_items_pool = []

        if any(word in transcript_lower for word in ["rrsp", "retirement", "rsps", "tfsa"]):
            topics.append("retirement planning")
            action_items_pool.append("Send RRSP contribution room confirmation")
            action_items_pool.append("Schedule dedicated retirement planning call")

        if any(word in transcript_lower for word in ["home", "mortgage", "purchase", "down payment"]):
            topics.append("home purchase timeline")
            action_items_pool.append("Review liquidity needs for planned purchase")
            action_items_pool.append("Discuss impact of withdrawal on long-term plan")

        if any(word in transcript_lower for word in ["tax", "deduction", "taxable", "capital gains"]):
            topics.append("tax optimization")
            action_items_pool.append("Review tax-efficient withdrawal strategy")
            action_items_pool.append("Coordinate with client's accountant on year-end planning")

        if any(word in transcript_lower for word in ["estate", "will", "beneficiary", "legacy"]):
            topics.append("estate planning")
            action_items_pool.append("Refer to estate planning specialist for legal review")
            action_items_pool.append("Confirm beneficiary designations are current")

        if any(word in transcript_lower for word in ["schedule", "follow", "call", "meeting", "review"]):
            topics.append("follow-up engagement")
            action_items_pool.append("Schedule follow-up review call in 30 days")

        # Build summary
        if topics:
            topics_str = ", ".join(topics)
            summary = (
                f"During this call with {client_name}, we discussed {topics_str} in the context of "
                f"their {risk_profile} portfolio. The discussion covered key planning priorities and "
                f"next steps to ensure the portfolio remains aligned with their financial goals."
            )
        else:
            summary = (
                f"Conducted a general portfolio review with {client_name}. Reviewed overall portfolio "
                f"performance and alignment with their {risk_profile} risk profile and stated objectives."
            )

        # Select up to 4 action items
        selected_actions = action_items_pool[:4] if action_items_pool else [
            "Schedule follow-up review",
            "Send portfolio summary",
            "Confirm client satisfaction"
        ]

        return TranscriptSummary(
            summary_paragraph=summary,
            action_items=selected_actions
        )

    def _build_event_title(
        self,
        priority: Priority,
        drift: float,
        concentration: float,
        volatility: float,
    ) -> str:
        if priority == Priority.HIGH:
            if drift >= concentration and drift >= volatility:
                return "Significant allocation drift detected"
            if concentration >= drift and concentration >= volatility:
                return "High concentration in single position"
            return "Heightened risk deviation detected"
        if priority == Priority.MEDIUM:
            if drift >= concentration:
                return "Moderate allocation drift observed"
            return "Elevated position concentration observed"
        return "Routine monitoring signal"

    def _build_summary(
        self,
        client_name: str,
        portfolio_name: str,
        priority: Priority,
        risk_score: float,
    ) -> str:
        if priority == Priority.HIGH:
            return (
                f"{portfolio_name} for {client_name} shows materially elevated risk indicators "
                f"relative to target, warranting prompt advisor awareness."
            )
        if priority == Priority.MEDIUM:
            return (
                f"{portfolio_name} for {client_name} shows moderate deviations from the target "
                f"profile that merit review at the next touchpoint."
            )
        return (
            f"{portfolio_name} for {client_name} remains broadly aligned with the target profile, "
            f"with risk signals suitable for routine monitoring (score {risk_score:.1f}/10)."
        )

    def _build_reasoning_bullets(
        self,
        concentration: float,
        drift: float,
        volatility: float,
        risk_score: float,
    ) -> List[str]:
        bullets: List[str] = []

        bullets.append(
            f"Combined risk score is {risk_score:.1f}/10 based on concentration, drift, and volatility signals."
        )

        bullets.append(
            f"Maximum single-position weight scores {concentration:.1f}/10 on the concentration scale, "
            "indicating the degree of reliance on a single holding."
        )

        bullets.append(
            f"Allocation drift relative to target scores {drift:.1f}/10, reflecting how far the current mix "
            "has moved from the intended profile."
        )

        bullets.append(
            f"Volatility proxy scores {volatility:.1f}/10, serving as a simple stand-in for recent return variability."
        )

        if risk_score >= 7:
            bullets.append(
                "Taken together, these signals suggest a level of risk that is meaningfully above the baseline plan "
                "and should be reviewed by an advisor."
            )
        elif risk_score >= 4:
            bullets.append(
                "Signals indicate some deviation from the baseline plan that should be monitored and revisited with "
                "the client as part of regular reviews."
            )
        else:
            bullets.append(
                "Signals remain within a range consistent with the stated risk expectations, supporting continued "
                "routine monitoring."
            )

        return bullets

    def _build_decision_trace(
        self,
        concentration: float,
        drift: float,
        volatility: float,
        risk_score: float,
        priority: Priority,
    ) -> List[DecisionTraceStep]:
        steps: List[DecisionTraceStep] = [
            DecisionTraceStep(
                step="Ingest metrics",
                detail=(
                    f"Received concentration_score={concentration:.1f}, "
                    f"drift_score={drift:.1f}, volatility_proxy={volatility:.1f}."
                ),
            ),
            DecisionTraceStep(
                step="Compute aggregate risk",
                detail=f"Calculated combined risk_score as the average of the three metrics: {risk_score:.1f}/10.",
            ),
            DecisionTraceStep(
                step="Assign priority band",
                detail=(
                    "Mapped the risk_score and individual signals into HIGH/MEDIUM/LOW priority "
                    f"bands using deterministic thresholds; result={priority.value}."
                ),
            ),
            DecisionTraceStep(
                step="Determine human review requirement",
                detail=(
                    "Flagged human_review_required when risk or drift signals move meaningfully away from "
                    "the baseline profile, preferring advisor review over automated resolution."
                ),
            ),
        ]
        return steps

    def _build_change_detection(
        self,
        metrics: Dict,
        last_metrics: Dict,
    ) -> List[ChangeDetectionItem]:
        items: List[ChangeDetectionItem] = []

        for key in ("concentration_score", "drift_score", "volatility_proxy", "risk_score"):
            current = metrics.get(key)
            previous = last_metrics.get(key)
            if previous is None or current is None:
                continue
            if float(current) == float(previous):
                continue
            items.append(
                ChangeDetectionItem(
                    metric=key,
                    from_value=f"{float(previous):.1f}",
                    to_value=f"{float(current):.1f}",
                )
            )

        return items

