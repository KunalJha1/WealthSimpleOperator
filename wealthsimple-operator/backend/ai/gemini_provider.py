from __future__ import annotations

import json
from typing import Dict

import google.generativeai as genai

from models import AIOutput
from ai.mock_provider import MockAIProvider
from ai.prompt_builder import build_prompt


class GeminiAIProvider:
    """Google Gemini-backed provider.

    On any error (API issues, parsing problems, schema mismatch), this provider
    falls back to the deterministic MockAIProvider to keep the system resilient.
    """

    name = "gemini"

    def __init__(self, api_key: str) -> None:
        self._mock_fallback = MockAIProvider()
        genai.configure(api_key=api_key)
        # A reasonably capable general model; can be swapped if needed.
        self._model = genai.GenerativeModel("gemini-1.5-pro")

    def score_portfolio(self, metrics: Dict, context: Dict) -> AIOutput:
        last_metrics = context.get("last_metrics") or {}

        prompt = build_prompt(metrics=metrics, last_metrics=last_metrics, context=context)

        try:
            response = self._model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.2,
                    response_mime_type="application/json",
                ),
            )
            raw_text = response.text or ""
            parsed = self._parse_json(raw_text)
            return AIOutput.model_validate(parsed)
        except Exception:
            # Any issue: degrade gracefully to deterministic mock.
            return self._mock_fallback.score_portfolio(metrics=metrics, context=context)

    def _parse_json(self, text: str) -> Dict:
        """Best-effort JSON parsing, stripping stray markdown if necessary."""
        text = text.strip()
        # If the model ignored response_mime_type and wrapped JSON in markdown,
        # try to strip fence lines.
        if text.startswith("```"):
            lines = [line for line in text.splitlines() if not line.strip().startswith("```")]
            text = "\n".join(lines).strip()
        return json.loads(text)

