"""
Tests for the Kill Switch infrastructure.
"""

import pytest
from app.trading.kill_switch import KillSwitch, KillSwitchStatus


class TestKillSwitch:
    """Test kill switch controls and auto-triggers."""

    @pytest.fixture
    def ks(self):
        return KillSwitch(
            max_drawdown_trigger=10_000.0,
            failure_count_trigger=3,
        )

    # ── Global Halt ────────────────────────────────────────────────────

    def test_order_allowed_by_default(self, ks):
        """Orders should be allowed when kill switch is inactive."""
        allowed, reason = ks.is_order_allowed("RELIANCE", "test_strategy")
        assert allowed is True
        assert reason == "OK"

    def test_global_halt_blocks_all_orders(self, ks):
        """Global halt should block every order."""
        ks.activate_global_halt(reason="test")
        allowed, reason = ks.is_order_allowed("RELIANCE", "test_strategy")
        assert allowed is False
        assert "GLOBAL HALT" in reason

    def test_global_halt_deactivation(self, ks):
        """Deactivating global halt should allow orders again."""
        ks.activate_global_halt(reason="test")
        ks.deactivate_global_halt(reason="all clear")
        allowed, _ = ks.is_order_allowed("RELIANCE", "test_strategy")
        assert allowed is True

    # ── Symbol Blocking ────────────────────────────────────────────────

    def test_block_symbol(self, ks):
        """Blocked symbol should be rejected."""
        ks.block_symbol("RELIANCE", reason="volatile")
        allowed, reason = ks.is_order_allowed("RELIANCE")
        assert allowed is False
        assert "BLOCKED" in reason

    def test_block_symbol_case_insensitive(self, ks):
        """Symbol blocking should be case-insensitive."""
        ks.block_symbol("reliance")
        allowed, _ = ks.is_order_allowed("RELIANCE")
        assert allowed is False

    def test_unblock_symbol(self, ks):
        """Unblocking a symbol should allow it again."""
        ks.block_symbol("RELIANCE")
        ks.unblock_symbol("RELIANCE")
        allowed, _ = ks.is_order_allowed("RELIANCE")
        assert allowed is True

    def test_other_symbols_unaffected(self, ks):
        """Blocking one symbol should not affect others."""
        ks.block_symbol("RELIANCE")
        allowed, _ = ks.is_order_allowed("TCS")
        assert allowed is True

    # ── Strategy Freezing ──────────────────────────────────────────────

    def test_freeze_strategy(self, ks):
        """Frozen strategy should be rejected."""
        ks.freeze_strategy("SMA Crossover")
        allowed, reason = ks.is_order_allowed(strategy_name="SMA Crossover")
        assert allowed is False
        assert "FROZEN" in reason

    def test_unfreeze_strategy(self, ks):
        """Unfreezing should allow the strategy again."""
        ks.freeze_strategy("SMA Crossover")
        ks.unfreeze_strategy("SMA Crossover")
        allowed, _ = ks.is_order_allowed(strategy_name="SMA Crossover")
        assert allowed is True

    # ── Broker Disabled ────────────────────────────────────────────────

    def test_broker_disabled(self, ks):
        """Disabling broker should reject all orders."""
        ks.disable_broker(reason="API down")
        allowed, reason = ks.is_order_allowed("RELIANCE")
        assert allowed is False
        assert "DISABLED" in reason

    def test_broker_re_enabled(self, ks):
        """Re-enabling broker should allow orders again."""
        ks.disable_broker()
        ks.enable_broker()
        allowed, _ = ks.is_order_allowed("RELIANCE")
        assert allowed is True

    # ── Auto-Trigger: Drawdown ─────────────────────────────────────────

    def test_drawdown_trigger(self, ks):
        """Exceeding drawdown threshold should auto-activate global halt."""
        triggered = ks.check_drawdown(-15_000.0)
        assert triggered is True
        assert ks._global_halt is True

    def test_drawdown_within_threshold(self, ks):
        """Drawdown within threshold should not trigger."""
        triggered = ks.check_drawdown(-5_000.0)
        assert triggered is False
        assert ks._global_halt is False

    def test_drawdown_does_not_double_trigger(self, ks):
        """Already-halted switch should not re-trigger on drawdown."""
        ks.activate_global_halt(reason="manual")
        triggered = ks.check_drawdown(-15_000.0)
        assert triggered is False  # Already halted

    # ── Auto-Trigger: Failures ─────────────────────────────────────────

    def test_failure_count_trigger(self, ks):
        """Consecutive failures should auto-activate global halt."""
        ks.record_failure()
        ks.record_failure()
        triggered = ks.record_failure()  # 3rd failure = threshold
        assert triggered is True
        assert ks._global_halt is True

    def test_success_resets_failure_count(self, ks):
        """A successful trade should reset the failure counter."""
        ks.record_failure()
        ks.record_failure()
        ks.record_success()  # Reset
        triggered = ks.record_failure()  # Only 1st failure after reset
        assert triggered is False
        assert ks._global_halt is False

    # ── Status & Audit Trail ───────────────────────────────────────────

    def test_status_snapshot(self, ks):
        """Status should reflect current state."""
        ks.block_symbol("INFY")
        ks.freeze_strategy("RSI Mean Reversion")
        status = ks.get_status()
        assert isinstance(status, KillSwitchStatus)
        assert "INFY" in status.blocked_symbols
        assert "RSI Mean Reversion" in status.frozen_strategies
        assert status.global_halt is False

    def test_event_log_records_actions(self, ks):
        """Events should be logged for audit trail."""
        ks.activate_global_halt(reason="test")
        ks.deactivate_global_halt(reason="cleared")
        ks.block_symbol("RELIANCE")
        status = ks.get_status()
        assert len(status.event_log) == 3

    def test_deactivation_resets_failure_count(self, ks):
        """Deactivating the halt should reset failure counter."""
        ks.record_failure()
        ks.record_failure()
        ks.record_failure()
        assert ks._consecutive_failures == 3
        ks.deactivate_global_halt()
        assert ks._consecutive_failures == 0
