"""
Tests for the LLM Safety Layer.
"""

import pytest
from app.llms.safety import LLMSafetyGuard, LLMSafetyConfig
from app.models.schemas import LLMDecision


class TestLLMSafetyGuard:
    """Test all safety checks on LLM decisions."""

    @pytest.fixture
    def guard(self):
        return LLMSafetyGuard(config=LLMSafetyConfig(
            min_confidence_threshold=0.3,
            max_signals_per_minute=5,
            max_recommended_quantity=100,
        ))

    def _make_decision(self, **kwargs) -> LLMDecision:
        defaults = dict(
            action="BUY",
            symbol="RELIANCE",
            confidence=0.75,
            reasoning="Test decision",
            stop_loss=2400.0,
            target_price=2600.0,
            quantity=10,
            order_type="MARKET",
            urgency="medium",
            raw_output="{}",
        )
        defaults.update(kwargs)
        return LLMDecision(**defaults)

    # ── Valid Decisions ────────────────────────────────────────────────

    def test_valid_decision_passes(self, guard):
        """A well-formed decision with good confidence should pass."""
        decision = self._make_decision()
        result = guard.validate(decision)
        assert result.passed is True
        assert result.blocked_reason is None

    def test_hold_always_passes(self, guard):
        """HOLD should always pass regardless of confidence."""
        decision = self._make_decision(action="HOLD", confidence=0.1)
        result = guard.validate(decision)
        assert result.passed is True

    def test_no_action_always_passes(self, guard):
        """NO_ACTION should always pass."""
        decision = self._make_decision(action="NO_ACTION", confidence=0.0)
        result = guard.validate(decision)
        assert result.passed is True

    # ── Confidence Floor ───────────────────────────────────────────────

    def test_low_confidence_blocks_buy(self, guard):
        """BUY with confidence below threshold should be blocked."""
        decision = self._make_decision(action="BUY", confidence=0.1)
        result = guard.validate(decision)
        assert result.passed is False
        assert "Confidence" in result.blocked_reason

    def test_low_confidence_blocks_sell(self, guard):
        """SELL with confidence below threshold should be blocked."""
        decision = self._make_decision(action="SELL", confidence=0.2)
        result = guard.validate(decision)
        assert result.passed is False

    # ── Action Whitelist ───────────────────────────────────────────────

    def test_invalid_action_blocked(self, guard):
        """Unknown action should be blocked."""
        decision = self._make_decision(action="YOLO")
        result = guard.validate(decision)
        assert result.passed is False
        assert "not in allowed list" in result.blocked_reason

    def test_blocked_action_list(self):
        """Explicitly blocked actions should be rejected."""
        config = LLMSafetyConfig(blocked_actions=["SELL"])
        guard = LLMSafetyGuard(config=config)
        decision = self._make_decision(action="SELL")
        result = guard.validate(decision)
        assert result.passed is False
        assert "explicitly blocked" in result.blocked_reason

    # ── Quantity Cap ───────────────────────────────────────────────────

    def test_quantity_capped(self, guard):
        """Excessive quantity should be capped to the maximum."""
        decision = self._make_decision(quantity=500)
        result = guard.validate(decision)
        assert result.passed is True
        assert result.filtered_decision.quantity == 100
        assert any("capped" in w.lower() for w in result.warnings)

    def test_normal_quantity_unchanged(self, guard):
        """Quantity within limit should remain unchanged."""
        decision = self._make_decision(quantity=50)
        result = guard.validate(decision)
        assert result.filtered_decision.quantity == 50

    # ── Confidence Cap ─────────────────────────────────────────────────

    def test_overconfidence_capped(self, guard):
        """Confidence above 0.95 should be capped (AI over-confidence)."""
        decision = self._make_decision(confidence=0.99)
        result = guard.validate(decision)
        assert result.passed is True
        assert result.filtered_decision.confidence == 0.95
        assert any("over-confidence" in w.lower() for w in result.warnings)

    # ── Rate Limiting ──────────────────────────────────────────────────

    def test_rate_limiting(self, guard):
        """Exceeding max signals per minute should block."""
        for _ in range(5):
            decision = self._make_decision()
            result = guard.validate(decision)
            assert result.passed is True

        # 6th signal should be blocked
        decision = self._make_decision()
        result = guard.validate(decision)
        assert result.passed is False
        assert "Rate limit" in result.blocked_reason

    # ── Stop Loss Warning ──────────────────────────────────────────────

    def test_missing_stop_loss_warning(self, guard):
        """BUY without stop_loss should generate a warning."""
        decision = self._make_decision(stop_loss=None)
        result = guard.validate(decision)
        assert result.passed is True  # Warning, not a block
        assert any("stop_loss" in w for w in result.warnings)

    # ── Urgency Sanitization ───────────────────────────────────────────

    def test_invalid_urgency_sanitized(self, guard):
        """Invalid urgency should default to 'low'."""
        decision = self._make_decision(urgency="ASAP")
        result = guard.validate(decision)
        assert result.filtered_decision.urgency == "low"

    # ── Stats ──────────────────────────────────────────────────────────

    def test_stats_tracking(self, guard):
        """Stats should track checked/blocked/modified counts."""
        guard.validate(self._make_decision())
        guard.validate(self._make_decision(confidence=0.1))
        stats = guard.get_stats()
        assert stats["total_checked"] == 2
        assert stats["total_blocked"] == 1

    # ── Force NO_ACTION ────────────────────────────────────────────────

    def test_blocked_decision_becomes_no_action(self, guard):
        """Blocked decisions should be converted to NO_ACTION."""
        decision = self._make_decision(action="BUY", confidence=0.05)
        result = guard.validate(decision)
        assert result.filtered_decision.action == "NO_ACTION"
        assert result.filtered_decision.confidence == 0.0
        assert "BLOCKED" in result.filtered_decision.reasoning
