"""
Ollama (local LLM) adapter — uses the ollama Python SDK.
"""

from __future__ import annotations

import ollama as ollama_sdk
from loguru import logger

from app.config import settings
from app.llms.base import (
    TRADING_SYSTEM_PROMPT,
    BaseLLM,
    _build_user_prompt,
    _parse_llm_response,
)
from app.models.schemas import LLMDecision, LLMQuery


class OllamaAdapter(BaseLLM):
    """Local Ollama adapter for privacy-focused deployments."""

    def __init__(self) -> None:
        self._client = ollama_sdk.AsyncClient(host=settings.ollama_host)
        self._model = settings.ollama_model

    async def generate(self, query: LLMQuery) -> LLMDecision:
        try:
            user_prompt = _build_user_prompt(query)
            response = await self._client.chat(
                model=self._model,
                messages=[
                    {"role": "system", "content": TRADING_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                format="json",
                options={"temperature": 0.2},
            )
            raw = response["message"]["content"]
            return _parse_llm_response(raw)
        except Exception as exc:
            logger.error(f"Ollama generation failed: {exc}")
            return LLMDecision(
                action="NO_ACTION",
                reasoning=f"Ollama error: {exc}",
                raw_output=str(exc),
            )

    async def health_check(self) -> bool:
        try:
            models = await self._client.list()
            return True
        except Exception:
            return False
