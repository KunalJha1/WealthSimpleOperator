from __future__ import annotations

from textwrap import dedent
from typing import Dict


def build_prompt(metrics: Dict, last_metrics: Dict | None, context: Dict) -> str:
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
          "summary": string,
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

        {schema_description}

        Use the following structured input as the basis for your decision. You must
        base your reasoning on these metrics and context only:

        INPUT:
        {metrics_block}

        Remember: respond with STRICT JSON only, matching the schema exactly.
        """
    ).strip()

