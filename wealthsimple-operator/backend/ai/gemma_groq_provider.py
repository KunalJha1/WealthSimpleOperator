from __future__ import annotations

import logging
from typing import Dict

from models import AIOutput, FollowUpDraftContent, TranscriptSummary

logger = logging.getLogger(__name__)


class GemmaGroqFallbackProvider:
    """Dual-provider: Groq Llama 3.3 70B primary, Gemini fallback.

    Both free tier with no quota issues:
    - Groq: Free tier, 14,400 requests/day (PRIMARY - faster, more generous)
    - Gemini: Free via Google AI Studio (FALLBACK)

    Tries Groq first; on any error, falls back to Gemini.
    """

    name = "gemma_with_groq_fallback"

    def __init__(self, gemma_api_key: str, groq_api_key: str) -> None:
        from ai.gemini_provider import GeminiAIProvider
        from ai.groq_provider import GroqAIProvider

        self._gemini = GeminiAIProvider(api_key=gemma_api_key)
        self._groq = GroqAIProvider(api_key=groq_api_key)
        logger.info("GemmaGroqFallback provider initialized (primary: Groq, fallback: Gemini)")

    def score_portfolio(self, metrics: Dict, context: Dict, unique_mode: bool = False) -> AIOutput:
        try:
            logger.debug("Attempting Groq for portfolio scoring...")
            return self._groq.score_portfolio(metrics=metrics, context=context, unique_mode=unique_mode)
        except Exception as e:
            logger.warning("Groq failed, falling back to Gemini: %s", str(e)[:100])
            try:
                return self._gemini.score_portfolio(metrics=metrics, context=context, unique_mode=unique_mode)
            except Exception as e2:
                logger.error("Both Groq and Gemini failed: %s", e2, exc_info=True)
                raise

    def generate_follow_up_draft(self, alert_context: Dict) -> FollowUpDraftContent:
        try:
            logger.debug("Attempting Groq for follow-up draft...")
            return self._groq.generate_follow_up_draft(alert_context=alert_context)
        except Exception as e:
            logger.warning("Groq failed, falling back to Gemini: %s", str(e)[:100])
            try:
                return self._gemini.generate_follow_up_draft(alert_context=alert_context)
            except Exception as e2:
                logger.error("Both Groq and Gemini failed: %s", e2, exc_info=True)
                raise

    def summarize_transcript(self, transcript: str, context: Dict) -> TranscriptSummary:
        try:
            logger.debug("Attempting Groq for transcript summary...")
            return self._groq.summarize_transcript(transcript=transcript, context=context)
        except Exception as e:
            logger.warning("Groq failed, falling back to Gemini: %s", str(e)[:100])
            try:
                return self._gemini.summarize_transcript(transcript=transcript, context=context)
            except Exception as e2:
                logger.error("Both Groq and Gemini failed: %s", e2, exc_info=True)
                raise
