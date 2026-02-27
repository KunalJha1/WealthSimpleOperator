from __future__ import annotations

import os
from typing import Dict, Protocol

from models import AIOutput, FollowUpDraftContent, TranscriptSummary


class AIProvider(Protocol):
    """Abstraction over AI providers used by the operator engine."""

    name: str

    def score_portfolio(self, metrics: Dict, context: Dict) -> AIOutput:
        ...

    def generate_follow_up_draft(self, alert_context: Dict) -> FollowUpDraftContent:
        ...

    def summarize_transcript(self, transcript: str, context: Dict) -> TranscriptSummary:
        ...


def _env_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def get_provider() -> AIProvider:
    """Return the configured AI provider instance.

    Logic:
    - PROVIDER=gemma_with_groq_fallback -> Gemma (primary) + Groq (fallback)
    - PROVIDER=gemini -> Gemini only
    - PROVIDER=groq -> Groq only
    - PROVIDER=mock -> Mock provider (default)
    """

    from .mock_provider import MockAIProvider  # local import to avoid cycles

    provider_env = os.getenv("PROVIDER", "mock").lower().strip()
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    groq_key = os.getenv("GROQ_API_KEY", "").strip()

    # Gemma + Groq fallback (recommended for production demo)
    if provider_env == "gemma_with_groq_fallback":
        if not gemini_key or not groq_key:
            print(
                "[WARNING] gemma_with_groq_fallback requires both GEMINI_API_KEY and GROQ_API_KEY. "
                "Falling back to mock provider."
            )
            return MockAIProvider()
        try:
            from .gemma_groq_provider import GemmaGroqFallbackProvider

            return GemmaGroqFallbackProvider(gemma_api_key=gemini_key, groq_api_key=groq_key)
        except Exception as e:
            print(f"[WARNING] GemmaGroqFallback initialization failed: {e}. Using mock provider.")
            return MockAIProvider()

    # Gemini only
    if provider_env == "gemini":
        if not gemini_key:
            print("[WARNING] PROVIDER=gemini requires GEMINI_API_KEY. Falling back to mock provider.")
            return MockAIProvider()
        try:
            from .gemini_provider import GeminiAIProvider

            return GeminiAIProvider(api_key=gemini_key)
        except Exception as e:
            print(f"[WARNING] Gemini initialization failed: {e}. Using mock provider.")
            return MockAIProvider()

    # Groq only
    if provider_env == "groq":
        if not groq_key:
            print("[WARNING] PROVIDER=groq requires GROQ_API_KEY. Falling back to mock provider.")
            return MockAIProvider()
        try:
            from .groq_provider import GroqAIProvider

            return GroqAIProvider(api_key=groq_key)
        except Exception as e:
            print(f"[WARNING] Groq initialization failed: {e}. Using mock provider.")
            return MockAIProvider()

    # Default: mock
    return MockAIProvider()

