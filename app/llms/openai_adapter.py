"""
OpenAI / ChatGPT adapter — uses the official openai SDK.
"""

from __future__ import annotations

from loguru import logger
from openai import AsyncOpenAI

from app.config import settings
from app.llms.base import (
    TRADING_SYSTEM_PROMPT,
    BaseLLM,
    _build_user_prompt,
    _parse_llm_response,
)
from app.models.schemas import LLMDecision, LLMQuery


class OpenAIAdapter(BaseLLM):
    """OpenAI ChatGPT adapter."""

    def __init__(self) -> None:
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)
        self._model = settings.openai_model

    async def generate(self, query: LLMQuery) -> LLMDecision:
        try:
            user_prompt = _build_user_prompt(query)
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": TRADING_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
                max_tokens=1024,
                response_format={"type": "json_object"},
            )
            raw = response.choices[0].message.content or ""
            return _parse_llm_response(raw)
        except Exception as exc:
            logger.error(f"OpenAI generation failed: {exc}")
            return LLMDecision(
                action="NO_ACTION",
                reasoning=f"OpenAI error: {exc}",
                raw_output=str(exc),
            )

    async def health_check(self) -> bool:
        try:
            resp = await self._client.models.list()
            return True
        except Exception:
            return False
