"""
Tests for LLM adapters and response parsing.
"""

import json
import pytest

from app.llms.base import _parse_llm_response
from app.models.schemas import LLMDecision, LLMQuery, MarketRegime


class TestLLMResponseParsing:
    """Test the shared JSON response parser."""

    def test_parse_valid_json(self):
        raw = json.dumps({
            "action": "BUY",
            "symbol": "RELIANCE",
            "confidence": 0.85,
            "reasoning": "Strong uptrend",
            "stop_loss": 2400.0,
            "target_price": 2700.0,
            "quantity": 10,
            "order_type": "MARKET",
            "urgency": "medium",
        })
        decision = _parse_llm_response(raw)
        assert decision.action == "BUY"
        assert decision.symbol == "RELIANCE"
        assert decision.confidence == 0.85
        assert decision.stop_loss == 2400.0

    def test_parse_json_in_markdown(self):
        raw = '```json\n{"action":"SELL","symbol":"TCS","confidence":0.7,"reasoning":"test","order_type":"LIMIT","urgency":"high"}\n```'
        decision = _parse_llm_response(raw)
        assert decision.action == "SELL"
        assert decision.symbol == "TCS"

    def test_parse_json_with_text_around(self):
        raw = 'Here is my analysis:\n{"action":"HOLD","symbol":"INFY","confidence":0.3,"reasoning":"sideways","order_type":"MARKET","urgency":"low"}\nEnd of analysis.'
        decision = _parse_llm_response(raw)
        assert decision.action == "HOLD"

    def test_parse_gibberish_returns_no_action(self):
        raw = "This is not valid JSON at all"
        decision = _parse_llm_response(raw)
        assert decision.action == "NO_ACTION"
        assert "Failed" in decision.reasoning

    def test_llm_query_construction(self):
        query = LLMQuery(
            strategy_name="SMA Crossover",
            market_regime=MarketRegime.TRENDING_UP,
            market_data={"RELIANCE": {"close": 2500}},
        )
        assert query.strategy_name == "SMA Crossover"
        assert query.market_regime == MarketRegime.TRENDING_UP

    def test_llm_decision_confidence_bounds(self):
        """Confidence must be between 0 and 1."""
        with pytest.raises(Exception):
            LLMDecision(action="BUY", confidence=1.5)

    def test_llm_decision_defaults(self):
        d = LLMDecision(action="NO_ACTION")
        assert d.confidence == 0.0
        assert d.urgency == "low"
        assert d.order_type == "MARKET"
