from __future__ import annotations

from typing import Dict, List

from models import (
    AIOutput,
    CallScriptContent,
    ChangeDetectionItem,
    DecisionTraceStep,
    EmailDraftContent,
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

    def score_portfolio(self, metrics: Dict, context: Dict, unique_mode: bool = False) -> AIOutput:
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

        # Wealthsimple footer consistent with frontend
        wealthsimple_footer = (
            "Wealthsimple Private Wealth\n"
            "80 Spadina Ave, Toronto, ON M5V 2J4\n"
            "wealthsimple.com | 1-855-255-9038\n\n"
            "Confidentiality Notice: This message may contain confidential information and is intended only for the named recipient."
        )

        body = (
            f"Hi {client_name},\n\n"
            f"We wanted to follow up regarding {event_title.lower()} in your portfolio.\n\n"
            f"{summary}\n\n"
            f"Recommended next step: {suggested_next_step}\n\n"
            "If helpful, we can schedule a quick review call to walk through this together.\n\n"
            "Warm regards,\n\n"
            f"{advisor_name}\n\n"
            "———————————————————————————\n\n"
            f"{wealthsimple_footer}"
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

    def generate_pre_call_brief(self, brief_data: Dict) -> Dict:
        """Assemble pre-call brief from provided data.

        No external API call needed - purely assembles context.
        """
        return {
            "client_name": brief_data.get("client_name", ""),
            "risk_profile": brief_data.get("risk_profile", ""),
            "aum": brief_data.get("aum", 0.0),
            "open_alert_count": brief_data.get("open_alert_count", 0),
            "highest_priority": brief_data.get("highest_priority"),
            "last_note_title": brief_data.get("last_note_title"),
            "last_note_date": brief_data.get("last_note_date"),
            "last_note_summary": brief_data.get("last_note_summary"),
            "outstanding_action_items": brief_data.get("outstanding_action_items", []),
        }

    def generate_call_script(self, call_context: Dict) -> CallScriptContent:
        """Generate a deterministic call script from context.

        Uses client name, segment, risk profile, AUM, and alert details
        to build a professional, empathetic call script.
        """
        client_name = str(call_context.get("client_name", "Client")).strip()
        segment = str(call_context.get("segment", "")).strip()
        risk_profile = str(call_context.get("risk_profile", "balanced")).strip()
        aum = float(call_context.get("aum", 0.0))
        days_since_contact = int(call_context.get("days_since_contact", 30))

        alert_summaries = call_context.get("alert_summaries", [])
        alert_context = "\n".join([f"- {s}" for s in alert_summaries[:3]]) if alert_summaries else "routine quarterly check-in"

        key_talking_points = [
            f"Portfolio performance and {risk_profile} allocation alignment",
            "Current market environment and positioning strategy",
            "Review of any changes in financial situation or goals",
        ]
        if alert_summaries:
            key_talking_points.insert(0, "Recent portfolio analysis findings")

        script = f"""CALL OPENING (Friendly, Professional):
"Hi {client_name}, thanks so much for taking my call. I'm reaching out because we've completed our latest portfolio review, and I wanted to walk through some important observations with you. Do you have about 20 minutes to chat?"

[Wait for confirmation]

BRIDGE TO AGENDA:
"Great! Here's what I'd like to cover today: First, I'll walk through what our analysis revealed, then we can discuss what it means for your portfolio, and finally we'll explore if any adjustments make sense for your situation."

KEY FINDINGS:
{alert_context}

RISK PROFILE & GOALS:
Your {risk_profile} risk profile with approximately ${aum:,.0f} in assets is designed to achieve balanced growth while managing volatility. Let's discuss if this still matches your comfort level.

ENGAGEMENT HISTORY:
We last connected about {days_since_contact} days ago. Any significant changes since then in your financial situation, income, or goals?

QUESTIONS TO ASK:
1. "Have there been any significant changes in your financial situation or goals since we last spoke?"
2. "How are you feeling about the current market environment?"
3. "Is your portfolio still aligned with how you wanted to be invested?"
4. "What are your thoughts on the observations I've outlined?"

DISCUSSION FLOW:
1. Present the portfolio findings in context
2. Connect findings to client's stated goals and risk tolerance
3. Discuss potential solutions (explore together, don't push)
4. Confirm next steps and timeline
5. Set expectations for follow-up

HANDLING OBJECTIONS:
• If concerned about market timing: "That's a valid point. What we focus on is keeping your portfolio aligned with your goals, not predicting market moves."
• If wants to wait: "I understand. Let's schedule a follow-up to revisit this in 2-3 weeks."
• If asks about costs: "Good question. Let's discuss the potential benefit versus the cost of any adjustments."

CLOSING:
"Thanks so much for discussing this with me. I'll send you a detailed summary of our conversation. Take a few days to review it, and then we can reconnect to finalize any decisions. Does that work for you?"

[Confirm timing and set next meeting]"""

        return CallScriptContent(
            script=script,
            key_talking_points=key_talking_points
        )

    def generate_email_draft(self, email_context: Dict) -> EmailDraftContent:
        """Generate a deterministic email draft from context.

        Uses client name, segment, risk profile, days since contact,
        and alert details to build a professional outreach email.
        """
        client_name = str(email_context.get("client_name", "Client")).strip()
        segment = str(email_context.get("segment", "")).strip()
        risk_profile = str(email_context.get("risk_profile", "balanced")).strip()
        days_since_contact = int(email_context.get("days_since_contact", 30))

        alert_summaries = email_context.get("alert_summaries", [])

        if alert_summaries:
            subject = "Important Portfolio Review"
            alert_details = "\n".join([f"• {s}" for s in alert_summaries[:3]])

            body = f"""Hi {client_name},

I hope you're doing well. I wanted to reach out because our recent portfolio analysis has identified some important items that would benefit from our discussion.

**Your Portfolio & Current Positioning:**

Based on our comprehensive review of your holdings and allocation, we've identified the following considerations:

{alert_details}

**Why This Matters:**

Your portfolio's current composition is an important factor in your long-term financial success. Market conditions, your life circumstances, and your financial goals can all influence whether adjustments might be beneficial. Our role is to ensure your portfolio remains optimized for your situation.

**What I'd Like to Discuss:**

During a brief call, I'd like to walk through:
1. A detailed analysis of what's driving these observations
2. How your current allocation aligns with your long-term objectives
3. Potential adjustments that could better position your portfolio
4. Any tax-efficient strategies we should consider
5. A timeline and action plan moving forward

**Next Steps:**

I'd value the opportunity to connect with you soon. Could you share a few times that work best for you this week or early next week? A 30-minute call should give us plenty of time to cover everything.

I look forward to connecting with you.

Best regards,
Your Wealth Advisor"""

            key_points = [
                f"{s.split(':')[0].strip()}" if ':' in s else s
                for s in alert_summaries[:3]
            ]
        else:
            subject = "Quarterly Portfolio Check-in"

            body = f"""Hi {client_name},

I hope this message finds you well. As part of our ongoing commitment to managing your wealth effectively, I wanted to reach out for a brief check-in on your {risk_profile} portfolio.

It's been about {days_since_contact} days since we last connected, and I think it's a good time to ensure your investment strategy continues to align with your objectives and the current market environment.

**What We'll Cover:**

• Your portfolio performance and current positioning
• Any changes in your financial situation, income, or goals
• Alignment of your allocation with your risk tolerance
• Market outlook and positioning strategy
• Opportunities for optimization

**Why This Matters:**

Regular portfolio reviews help ensure your investments remain aligned with your long-term goals. Changes in the market environment or your personal situation may suggest adjustments that could improve your financial outcomes.

**Let's Connect:**

I'd welcome the chance to schedule a brief call at your convenience. Please let me know what times work best for you this week or next. Even a 20-30 minute conversation can be very valuable.

Best regards,
Your Wealth Advisor"""

            key_points = [
                "Routine portfolio review",
                "Goal alignment verification",
                "Market positioning check"
            ]

        return EmailDraftContent(
            subject=subject,
            body=body,
            key_points=key_points
        )
