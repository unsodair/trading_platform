"""
Anthropic Claude adapter — uses the official anthropic SDK.
"""

from __future__ import annotations

from anthropic import AsyncAnthropic
from loguru import logger

from app.config import settings
from app.llms.base import (
    TRADING_SYSTEM_PROMPT,
    BaseLLM,
    _build_user_prompt,
    _parse_llm_response,
)
from app.models.schemas import LLMDecision, LLMQuery


class AnthropicAdapter(BaseLLM):
    """Anthropic Claude adapter."""

    def __init__(self) -> None:
        self._client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        self._model = settings.anthropic_model

    async def generate(self, query: LLMQuery) -> LLMDecision:
        try:
            user_prompt = _build_user_prompt(query)
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=1024,
                system=TRADING_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
                temperature=0.2,
            )
            raw = response.content[0].text if response.content else ""
            return _parse_llm_response(raw)
        except Exception as exc:
            logger.error(f"Anthropic generation failed: {exc}")
            return LLMDecision(
                action="NO_ACTION",
                reasoning=f"Anthropic error: {exc}",
                raw_output=str(exc),
            )

    async def health_check(self) -> bool:
        try:
            resp = await self._client.messages.create(
                model=self._model,
                max_tokens=16,
                messages=[{"role": "user", "content": "ping"}],
            )
            return bool(resp.content)
        except Exception:
            return False
