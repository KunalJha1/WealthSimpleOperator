from __future__ import annotations

from textwrap import dedent
from typing import Dict


def build_prompt(metrics: Dict, last_metrics: Dict | None, context: Dict, unique_mode: bool = False) -> str:
    """Builds a strict JSON-only instruction prompt for Gemini.

    The model is instructed to behave as an internal monitoring/triage assistant only,
    not to provide financial advice or trading instructions.
    """

    client = context.get("client", {})
    portfolio = context.get("portfolio", {})

    schema_description = dedent(
        """
        You must respond with STRICT JSON ONLY, no markdown, no prose before or after.
        The JSON MUST match this schema exactly:

        {
          "priority": "HIGH" | "MEDIUM" | "LOW",
          "confidence": number (0-100),
          "event_title": string,
          "summary": string (2-3 detailed sentences providing comprehensive analysis),
          "reasoning_bullets": string[],
          "human_review_required": boolean,
          "suggested_next_step": string,
          "decision_trace_steps": [
            {
              "step": string,
              "detail": string
            }
          ],
          "change_detection": [
            {
              "metric": string,
              "from": string,
              "to": string
            }
          ]
        }
        """
    ).strip()

    responsibility_clause = dedent(
        """
        AI responsibility: monitoring/triage only.
        Human responsibility: all investment decisions, client contact, escalation, and interpretations.

        You MUST NOT propose or imply:
        - buy or sell instructions,
        - target allocations such as specific percentages,
        - rebalancing instructions (e.g., "rebalance to X%").

        Use operational language only, such as:
        - "drift detected relative to target allocation",
        - "risk deviation relative to client profile",
        - "requires advisor awareness and review".
        """
    ).strip()

    if unique_mode:
        summary_guidance = dedent(
            """
            SUMMARY REQUIREMENTS (UNIQUE MODE - detailed, varied, analytical):
            - Write 3-4 complete, richly detailed sentences with nuanced analysis.
            - Include specific metric values, trends, and contextual observations unique to this portfolio.
            - Vary your language and phrasing - avoid generic templates; be portfolio-specific.
            - Explain the business/strategic context: why this situation matters for THIS client's specific profile, goals, and circumstances.
            - Connect metrics to human impact: discuss implications for the advisor's next steps with this client.
            - Provide deep analytical insights: explain the "why" behind the risk, not just the "what".
            Example of EXCELLENT summary: "Concentration risk has escalated to 8.2/10, driven primarily by an outsized 28% technology weighting that has grown from 22% over three months, creating significant exposure misalignment with Sarah's conservative risk profile and stated preference for broad market diversification. The widening 12 percentage-point drift from her 45% target equity allocation, combined with elevated volatility proxy scores, suggests portfolio drift beyond normal market fluctuations. For a conservative investor nearing retirement, this combination of sector concentration and strategic deviation warrants immediate advisor review to assess whether recent market gains have unintentionally skewed her allocations away from her original objectives."
            Example of MEDIOCRE summary: "Portfolio has concentration and drift risk."
            """
        ).strip()
    else:
        summary_guidance = dedent(
            """
            SUMMARY REQUIREMENTS (critical for quality output):
            - Write 2-3 complete, detailed sentences (not short phrases).
            - Include specific observations: mention the actual metric values, trends, or changes detected.
            - Explain the business/portfolio context: why this matters for this client's profile or goals.
            - Provide analytical depth: connect the metrics to the priority level and confidence score.
            Example of GOOD summary: "Concentration risk has elevated to 8.2/10 due to a 28% weighting in technology sector, creating exposure misalignment with this conservative client's stated objectives. Drift from the target equity allocation of 45% has widened to 12 percentage points, indicating portfolio drift that warrants advisor review. This combination of elevated sector concentration and strategic drift justifies HIGH priority triage for this account."
            Example of BAD summary: "Portfolio has high concentration risk and drift."
            """
        ).strip()

    metrics_block = {
        "metrics": metrics,
        "last_metrics": last_metrics or {},
        "client": client,
        "portfolio": portfolio,
    }

    return dedent(
        f"""
        You are an internal portfolio monitoring assistant for wealth advisors.
        Your role is to monitor portfolios, highlight where human review is warranted,
        and explain your reasoning in a way that can be audited later.

        {responsibility_clause}

        {summary_guidance}

        {schema_description}

        Use the following structured input as the basis for your decision. You must
        base your reasoning on these metrics and context only:

        INPUT:
        {metrics_block}

        Remember: respond with STRICT JSON only, matching the schema exactly.
        """
    ).strip()

