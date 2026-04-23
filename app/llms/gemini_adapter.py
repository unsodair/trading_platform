"""
Google Gemini adapter — uses the google-generativeai SDK.
"""

from __future__ import annotations

import google.generativeai as genai
from loguru import logger

from app.config import settings
from app.llms.base import (
    TRADING_SYSTEM_PROMPT,
    BaseLLM,
    _build_user_prompt,
    _parse_llm_response,
)
from app.models.schemas import LLMDecision, LLMQuery


class GeminiAdapter(BaseLLM):
    """Google Gemini adapter."""

    def __init__(self) -> None:
        genai.configure(api_key=settings.gemini_api_key)
        self._model = genai.GenerativeModel(
            model_name=settings.gemini_model,
            system_instruction=TRADING_SYSTEM_PROMPT,
            generation_config=genai.GenerationConfig(
                temperature=0.2,
                max_output_tokens=1024,
                response_mime_type="application/json",
            ),
        )

    async def generate(self, query: LLMQuery) -> LLMDecision:
        try:
            user_prompt = _build_user_prompt(query)
            response = await self._model.generate_content_async(user_prompt)
            raw = response.text or ""
            return _parse_llm_response(raw)
        except Exception as exc:
            logger.error(f"Gemini generation failed: {exc}")
            return LLMDecision(
                action="NO_ACTION",
                reasoning=f"Gemini error: {exc}",
                raw_output=str(exc),
            )

    async def health_check(self) -> bool:
        try:
            response = await self._model.generate_content_async("ping")
            return bool(response.text)
        except Exception:
            return False
