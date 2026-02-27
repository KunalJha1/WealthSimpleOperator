from __future__ import annotations

import json
import logging
import os
import random
import time
from typing import Dict

from google import genai
from google.genai import types
from google.genai import errors as genai_errors

from models import AIOutput, FollowUpDraftContent, TranscriptSummary
from ai.mock_provider import MockAIProvider
from ai.prompt_builder import build_prompt

logger = logging.getLogger(__name__)


def generate_with_retry(call_fn, max_retries=8):
    """Retry with exponential backoff and jitter for rate limit errors.

    Uses longer starting delay (8s) and random jitter to avoid overwhelming
    the API quota and to spread requests over time, similar to build_ai_summary.py.
    """
    delay = 8.0
    for attempt in range(max_retries):
        try:
            return call_fn()
        except genai_errors.ClientError as e:
            msg = str(e)
            logger.warning("API error on attempt %d/%d: %s", attempt + 1, max_retries, msg)
            if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
                jittered_delay = delay + random.random()
                logger.warning("Rate limited. Retrying in %.1fs...", jittered_delay)
                time.sleep(jittered_delay)
                delay = min(delay * 2, 20)
                continue
            raise


class GeminiAIProvider:
    """Google Gemini-backed provider.

    On any error (API issues, parsing problems, schema mismatch), this provider
    falls back to the deterministic MockAIProvider to keep the system resilient.
    """

    name = "gemini"

    def __init__(self, api_key: str) -> None:
        self._mock_fallback = MockAIProvider()
        self._strict_mode = os.getenv("GEMINI_STRICT", "").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        self._client = genai.Client(api_key=api_key)
        # Allow model override via env for reliability/cost tuning.
        model_name = os.getenv("GEMINI_MODEL", "gemini-2.0-flash").strip() or "gemini-2.0-flash"
        self._model_name = model_name
        logger.info(
            "Gemini provider initialized with model=%s strict=%s",
            model_name,
            self._strict_mode,
        )

    def score_portfolio(self, metrics: Dict, context: Dict, unique_mode: bool = False) -> AIOutput:
        last_metrics = context.get("last_metrics") or {}

        prompt = build_prompt(metrics=metrics, last_metrics=last_metrics, context=context, unique_mode=unique_mode)

        try:
            response = self._generate_content_with_retry(prompt, temperature=0.8 if unique_mode else 0.6)
            raw_text = response.text or ""
            parsed = self._parse_json(raw_text)
            return AIOutput.model_validate(parsed)
        except Exception as exc:
            logger.warning("Gemini generation failed, using mock fallback: %s", exc, exc_info=True)
            if self._strict_mode:
                raise
            # Any issue: degrade gracefully to deterministic mock.
            return self._mock_fallback.score_portfolio(metrics=metrics, context=context)

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
            response = self._generate_content_with_retry(prompt)
            raw_text = response.text or ""
            parsed = self._parse_json(raw_text)
            return FollowUpDraftContent.model_validate(parsed)
        except Exception as exc:
            logger.warning("Gemini follow-up draft failed, using mock fallback: %s", exc, exc_info=True)
            if self._strict_mode:
                raise
            return self._mock_fallback.generate_follow_up_draft(alert_context=alert_context)

    def summarize_transcript(self, transcript: str, context: Dict) -> TranscriptSummary:
        client_name = str(context.get("client_name", "Client")).strip()
        risk_profile = str(context.get("risk_profile", "balanced")).strip()

        # Trim transcript to 4000 chars to avoid token overload
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
            response = self._generate_content_with_retry(prompt)
            raw_text = response.text or ""
            parsed = self._parse_json(raw_text)
            return TranscriptSummary.model_validate(parsed)
        except Exception as exc:
            logger.warning("Gemini transcript summary failed, using mock fallback: %s", exc, exc_info=True)
            if self._strict_mode:
                raise
            return self._mock_fallback.summarize_transcript(transcript=transcript, context=context)

    def _parse_json(self, text: str) -> Dict:
        """Best-effort JSON parsing, stripping stray markdown if necessary."""
        text = text.strip()
        # If the model ignored response_mime_type and wrapped JSON in markdown,
        # try to strip fence lines.
        if text.startswith("```"):
            lines = [line for line in text.splitlines() if not line.strip().startswith("```")]
            text = "\n".join(lines).strip()
        return json.loads(text)

    def _generate_content_with_retry(self, prompt: str, temperature: float = 0.6):
        generation_config = types.GenerateContentConfig(
            temperature=temperature,
            response_mime_type="application/json",
        )
        resp = generate_with_retry(
            lambda: self._client.models.generate_content(
                model=self._model_name,
                contents=[prompt],
                config=generation_config,
            )
        )
        return resp

