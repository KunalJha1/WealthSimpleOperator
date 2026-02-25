from __future__ import annotations

import os
from typing import Dict, Protocol

from models import AIOutput


class AIProvider(Protocol):
    """Abstraction over AI providers used by the operator engine."""

    name: str

    def score_portfolio(self, metrics: Dict, context: Dict) -> AIOutput:
        ...


def _env_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def get_provider() -> AIProvider:
    """Return the configured AI provider instance.

    Logic:
    - If GEMINI_API_KEY is missing/empty or PROVIDER=mock -> Mock provider.
    - Otherwise try Gemini provider, falling back to Mock on import/config issues.
    """

    from .mock_provider import MockAIProvider  # local import to avoid cycles

    provider_env = os.getenv("PROVIDER", "mock").lower()
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()

    use_mock = provider_env == "mock" or not gemini_key

    if use_mock:
        return MockAIProvider()

    try:
        from .gemini_provider import GeminiAIProvider

        return GeminiAIProvider(api_key=gemini_key)
    except Exception:
        # In any failure scenario, prefer resilience and default to mock.
        return MockAIProvider()

