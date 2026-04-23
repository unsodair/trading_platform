"""
Abstract LLM interface — every LLM adapter must return a strict-JSON
LLMDecision object.
"""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod

from loguru import logger

from app.models.schemas import LLMDecision, LLMQuery

# ── System prompt shared by all adapters ───────────────────────────────────────

TRADING_SYSTEM_PROMPT = """You are a professional Indian stock market trading assistant.
You MUST respond ONLY with valid JSON matching this exact schema — no markdown, no commentary:

{
  "action": "BUY | SELL | HOLD | CLOSE | NO_ACTION",
  "symbol": "<trading symbol>",
  "confidence": <0.0 to 1.0>,
  "reasoning": "<brief reasoning>",
  "stop_loss": <price or null>,
  "target_price": <price or null>,
  "quantity": <integer or null>,
  "order_type": "MARKET | LIMIT | SL | SL_MARKET",
  "urgency": "low | medium | high"
}

Rules:
- Only recommend actions you are confident about.
- Always consider risk management.
- Indian markets trade on NSE/BSE, hours 09:15-15:30 IST.
- Be conservative; default to NO_ACTION when uncertain.
- Always suggest a stop_loss for BUY/SELL actions.
"""


def _build_user_prompt(query: LLMQuery) -> str:
    """Convert a structured query into a text prompt."""
    parts = [
        f"Strategy: {query.strategy_name}",
        f"Market Regime: {query.market_regime.value}",
    ]
    if query.current_positions:
        parts.append(
            f"Current Positions: {json.dumps([p.model_dump() for p in query.current_positions], default=str)}"
        )
    if query.holdings:
        parts.append(
            f"Holdings: {json.dumps([h.model_dump() for h in query.holdings], default=str)}"
        )
    if query.market_data:
        parts.append(f"Market Data: {json.dumps(query.market_data, default=str)}")
    if query.indicators:
        parts.append(f"Indicators: {json.dumps(query.indicators, default=str)}")
    if query.news_context:
        parts.append(f"News Context: {query.news_context}")
    if query.custom_prompt:
        parts.append(f"Additional Instructions: {query.custom_prompt}")
    parts.append("\nProvide your trading decision as strict JSON.")
    return "\n\n".join(parts)


def _parse_llm_response(raw: str) -> LLMDecision:
    """Extract JSON from LLM text and parse into LLMDecision."""
    # Try direct parse first
    try:
        data = json.loads(raw)
        return LLMDecision(**data, raw_output=raw)
    except (json.JSONDecodeError, Exception):
        pass

    # Try extracting JSON from markdown code blocks
    json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
    if json_match:
        try:
            data = json.loads(json_match.group(1))
            return LLMDecision(**data, raw_output=raw)
        except (json.JSONDecodeError, Exception):
            pass

    # Try extracting any JSON object
    json_match = re.search(r"\{[\s\S]*\}", raw)
    if json_match:
        try:
            data = json.loads(json_match.group(0))
            return LLMDecision(**data, raw_output=raw)
        except (json.JSONDecodeError, Exception):
            pass

    # Fallback — return NO_ACTION
    logger.warning(f"Could not parse LLM response, returning NO_ACTION. Raw: {raw[:200]}")
    return LLMDecision(
        action="NO_ACTION",
        reasoning="Failed to parse LLM output",
        raw_output=raw,
    )


class BaseLLM(ABC):
    """Contract for all LLM adapters."""

    @abstractmethod
    async def generate(self, query: LLMQuery) -> LLMDecision:
        """Send structured query to the LLM and return a parsed decision."""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Verify the LLM service is reachable."""
        ...
