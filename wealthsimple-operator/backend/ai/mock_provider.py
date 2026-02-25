from __future__ import annotations

from typing import Dict, List

from models import (
    AIOutput,
    ChangeDetectionItem,
    DecisionTraceStep,
    Priority,
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

        confidence = int(
            max(50.0, min(99.0, round(base_confidence + trend_adjustment)))
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

