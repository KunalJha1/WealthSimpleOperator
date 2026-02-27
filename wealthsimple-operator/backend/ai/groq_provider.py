from __future__ import annotations

import json
import logging
import os
from typing import Dict

from groq import Groq

from models import AIOutput, FollowUpDraftContent, TranscriptSummary
from ai.prompt_builder import build_prompt

logger = logging.getLogger(__name__)


class GroqAIProvider:
    """Groq-backed provider using Llama 3.3 70B.

    Free tier with generous limits (14,400 requests/day).
    Used as fallback when Gemini quota is exhausted.
    """

    name = "groq"

    def __init__(self, api_key: str) -> None:
        self._client = Groq(api_key=api_key)
        model_name = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile").strip() or "llama-3.3-70b-versatile"
        self._model_name = model_name
        logger.info("Groq provider initialized with model=%s", model_name)

    def score_portfolio(self, metrics: Dict, context: Dict, unique_mode: bool = False) -> AIOutput:
        prompt = build_prompt(metrics=metrics, last_metrics=context.get("last_metrics"), context=context, unique_mode=unique_mode)

        try:
            response = self._client.chat.completions.create(
                model=self._model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.8 if unique_mode else 0.6,
                response_format={"type": "json_object"},
            )
            raw_text = response.choices[0].message.content or ""
            parsed = json.loads(raw_text)
            return AIOutput.model_validate(parsed)
        except Exception as exc:
            logger.error("Groq generation failed: %s", exc, exc_info=True)
            raise

    def generate_follow_up_draft(self, alert_context: Dict) -> FollowUpDraftContent:
        client_name = str(alert_context.get("client_name", "Client")).strip()
        event_title = str(alert_context.get("event_title", "portfolio update")).strip()
        summary = str(alert_context.get("summary", "")).strip()
        suggested_next_step = str(alert_context.get("suggested_next_step", "")).strip()

        prompt = (
            "You are drafting an advisor follow-up email.\n"
            "Return strict JSON with exactly keys: subject, body.\n"
            "No markdown. No extra keys.\n\n"
            f"Client name: {client_name}\n"
            f"Event title: {event_title}\n"
            f"Summary: {summary}\n"
            f"Suggested next step: {suggested_next_step}\n\n"
            "Constraints:\n"
            "- Professional, concise tone.\n"
            "- Do not include direct investment execution instructions.\n"
            "- Invite client to review with advisor.\n"
        )

        try:
            response = self._client.chat.completions.create(
                model=self._model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.6,
                response_format={"type": "json_object"},
            )
            raw_text = response.choices[0].message.content or ""
            parsed = json.loads(raw_text)
            return FollowUpDraftContent.model_validate(parsed)
        except Exception as exc:
            logger.error("Groq follow-up draft failed: %s", exc, exc_info=True)
            raise

    def summarize_transcript(self, transcript: str, context: Dict) -> TranscriptSummary:
        client_name = str(context.get("client_name", "Client")).strip()
        risk_profile = str(context.get("risk_profile", "balanced")).strip()

        trimmed_transcript = transcript[:4000]

        prompt = (
            "You are analyzing a financial advisor-client call transcript.\n"
            "Return strict JSON with exactly these keys: summary_paragraph, action_items.\n"
            "action_items must be a list of strings (max 4 items).\n"
            "No markdown. No extra keys.\n\n"
            f"Client name: {client_name}\n"
            f"Risk profile: {risk_profile}\n\n"
            f"Transcript:\n{trimmed_transcript}\n\n"
            "Constraints:\n"
            "- Summary should be 2-3 sentences capturing key topics discussed.\n"
            "- Action items must be operational and advisor-facing.\n"
            "- DO NOT include any direct trade recommendations (buy/sell).\n"
            "- Focus on follow-up tasks, planning reviews, and client coordination.\n"
        )

        try:
            response = self._client.chat.completions.create(
                model=self._model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.6,
                response_format={"type": "json_object"},
            )
            raw_text = response.choices[0].message.content or ""
            parsed = json.loads(raw_text)
            return TranscriptSummary.model_validate(parsed)
        except Exception as exc:
            logger.error("Groq transcript summary failed: %s", exc, exc_info=True)
            raise
