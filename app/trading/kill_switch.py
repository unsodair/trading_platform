"""
Kill Switch Infrastructure — Global emergency controls for the trading platform.

Provides instant ability to:
  - Halt ALL new order placement globally
  - Freeze individual strategies
  - Block specific symbols from trading
  - Disable broker routing entirely
  - Auto-trigger on drawdown breach or repeated failures

This is the MOST CRITICAL safety system in the platform.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from loguru import logger
from pydantic import BaseModel, Field


# ── Models ─────────────────────────────────────────────────────────────────────

class KillSwitchReason(str, Enum):
    MANUAL = "manual"
    DRAWDOWN_BREACH = "drawdown_breach"
    REPEATED_FAILURES = "repeated_failures"
    API_INSTABILITY = "api_instability"
    ABNORMAL_VOLATILITY = "abnormal_volatility"


class KillSwitchEvent(BaseModel):
    """Immutable record of a kill switch state change."""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    action: str  # "activated" | "deactivated" | "symbol_blocked" | ...
    reason: str = ""
    triggered_by: str = "system"  # "admin" | "system" | "auto"
    details: str = ""


class KillSwitchStatus(BaseModel):
    """Current state snapshot of the kill switch."""
    global_halt: bool = False
    broker_disabled: bool = False
    blocked_symbols: list[str] = Field(default_factory=list)
    frozen_strategies: list[str] = Field(default_factory=list)
    consecutive_failures: int = 0
    last_activated_at: Optional[datetime] = None
    last_deactivated_at: Optional[datetime] = None
    event_log: list[KillSwitchEvent] = Field(default_factory=list)


# ── Kill Switch Engine ─────────────────────────────────────────────────────────

class KillSwitch:
    """
    Global emergency control singleton.

    All order placement paths MUST check `is_order_allowed()` before executing.
    """

    def __init__(
        self,
        max_drawdown_trigger: float = 10_000.0,
        failure_count_trigger: int = 5,
        max_event_log_size: int = 200,
    ) -> None:
        self._global_halt: bool = False
        self._broker_disabled: bool = False
        self._blocked_symbols: set[str] = set()
        self._frozen_strategies: set[str] = set()

        # Auto-trigger thresholds
        self._max_drawdown_trigger = max_drawdown_trigger
        self._failure_count_trigger = failure_count_trigger

        # Tracking state
        self._consecutive_failures: int = 0
        self._last_activated_at: datetime | None = None
        self._last_deactivated_at: datetime | None = None

        # Immutable event audit trail
        self._event_log: list[KillSwitchEvent] = []
        self._max_event_log_size = max_event_log_size

    # ── Core Checks (called by execution engines) ──────────────────────────

    def is_order_allowed(
        self,
        symbol: str = "",
        strategy_name: str = "",
    ) -> tuple[bool, str]:
        """
        Check if an order is permitted under current kill switch state.

        Returns (allowed: bool, reason: str).
        Every execution path MUST call this before placing any order.
        """
        if self._global_halt:
            return False, "GLOBAL HALT is active — all trading suspended"

        if self._broker_disabled:
            return False, "Broker routing is DISABLED"

        if symbol and symbol.upper() in self._blocked_symbols:
            return False, f"Symbol '{symbol}' is BLOCKED by kill switch"

        if strategy_name and strategy_name in self._frozen_strategies:
            return False, f"Strategy '{strategy_name}' is FROZEN by kill switch"

        return True, "OK"

    # ── Auto-Trigger Hooks ─────────────────────────────────────────────────

    def check_drawdown(self, daily_pnl: float) -> bool:
        """
        Called after each trade. If daily drawdown exceeds threshold,
        automatically activates the global kill switch.

        Returns True if the kill switch was triggered.
        """
        if daily_pnl < -self._max_drawdown_trigger and not self._global_halt:
            self.activate_global_halt(
                reason=f"Drawdown breach: ₹{daily_pnl:.2f} exceeds "
                       f"max ₹{self._max_drawdown_trigger:.2f}",
                triggered_by="auto",
            )
            return True
        return False

    def record_failure(self) -> bool:
        """
        Called when an order placement fails. Increments failure counter.
        If consecutive failures exceed the threshold, activates global halt.

        Returns True if the kill switch was triggered.
        """
        self._consecutive_failures += 1
        logger.warning(
            f"Kill switch: failure #{self._consecutive_failures} "
            f"(trigger at {self._failure_count_trigger})"
        )

        if self._consecutive_failures >= self._failure_count_trigger and not self._global_halt:
            self.activate_global_halt(
                reason=f"Repeated failures: {self._consecutive_failures} "
                       f"consecutive order failures",
                triggered_by="auto",
            )
            return True
        return False

    def record_success(self) -> None:
        """Called when an order succeeds — resets the failure counter."""
        self._consecutive_failures = 0

    # ── Manual Controls ────────────────────────────────────────────────────

    def activate_global_halt(
        self, reason: str = "Manual activation", triggered_by: str = "admin"
    ) -> None:
        """IMMEDIATELY halt ALL new order placement."""
        self._global_halt = True
        self._last_activated_at = datetime.now(timezone.utc)
        self._log_event(
            action="global_halt_activated",
            reason=reason,
            triggered_by=triggered_by,
        )
        logger.critical(f"🚨 KILL SWITCH ACTIVATED — {reason}")

    def deactivate_global_halt(
        self, reason: str = "Manual deactivation", triggered_by: str = "admin"
    ) -> None:
        """Resume order placement after a global halt."""
        self._global_halt = False
        self._consecutive_failures = 0
        self._last_deactivated_at = datetime.now(timezone.utc)
        self._log_event(
            action="global_halt_deactivated",
            reason=reason,
            triggered_by=triggered_by,
        )
        logger.info(f"✅ KILL SWITCH DEACTIVATED — {reason}")

    def disable_broker(self, reason: str = "Manual") -> None:
        """Sever broker routing — orders will not reach the exchange."""
        self._broker_disabled = True
        self._log_event(action="broker_disabled", reason=reason)
        logger.warning(f"🔌 Broker routing DISABLED — {reason}")

    def enable_broker(self, reason: str = "Manual") -> None:
        """Re-enable broker routing."""
        self._broker_disabled = False
        self._log_event(action="broker_enabled", reason=reason)
        logger.info(f"🔌 Broker routing ENABLED — {reason}")

    def block_symbol(self, symbol: str, reason: str = "Manual") -> None:
        """Block a specific symbol from being traded."""
        self._blocked_symbols.add(symbol.upper())
        self._log_event(
            action="symbol_blocked",
            reason=reason,
            details=f"symbol={symbol.upper()}",
        )
        logger.warning(f"🚫 Symbol BLOCKED: {symbol.upper()} — {reason}")

    def unblock_symbol(self, symbol: str, reason: str = "Manual") -> None:
        """Remove a symbol from the blocked list."""
        self._blocked_symbols.discard(symbol.upper())
        self._log_event(
            action="symbol_unblocked",
            reason=reason,
            details=f"symbol={symbol.upper()}",
        )
        logger.info(f"✅ Symbol UNBLOCKED: {symbol.upper()} — {reason}")

    def freeze_strategy(self, strategy_name: str, reason: str = "Manual") -> None:
        """Freeze a specific strategy — its signals will be ignored."""
        self._frozen_strategies.add(strategy_name)
        self._log_event(
            action="strategy_frozen",
            reason=reason,
            details=f"strategy={strategy_name}",
        )
        logger.warning(f"❄️ Strategy FROZEN: {strategy_name} — {reason}")

    def unfreeze_strategy(self, strategy_name: str, reason: str = "Manual") -> None:
        """Unfreeze a specific strategy."""
        self._frozen_strategies.discard(strategy_name)
        self._log_event(
            action="strategy_unfrozen",
            reason=reason,
            details=f"strategy={strategy_name}",
        )
        logger.info(f"✅ Strategy UNFROZEN: {strategy_name} — {reason}")

    # ── Status & Audit ─────────────────────────────────────────────────────

    def get_status(self) -> KillSwitchStatus:
        """Return a full snapshot of current kill switch state."""
        return KillSwitchStatus(
            global_halt=self._global_halt,
            broker_disabled=self._broker_disabled,
            blocked_symbols=sorted(self._blocked_symbols),
            frozen_strategies=sorted(self._frozen_strategies),
            consecutive_failures=self._consecutive_failures,
            last_activated_at=self._last_activated_at,
            last_deactivated_at=self._last_deactivated_at,
            event_log=list(reversed(self._event_log[-50:])),  # Most recent first
        )

    def _log_event(
        self,
        action: str,
        reason: str = "",
        triggered_by: str = "admin",
        details: str = "",
    ) -> None:
        """Append an immutable event to the audit trail."""
        event = KillSwitchEvent(
            action=action,
            reason=reason,
            triggered_by=triggered_by,
            details=details,
        )
        self._event_log.append(event)

        # Trim to prevent unbounded memory growth
        if len(self._event_log) > self._max_event_log_size:
            self._event_log = self._event_log[-self._max_event_log_size:]


# ── Singleton ──────────────────────────────────────────────────────────────────

_kill_switch: KillSwitch | None = None


def get_kill_switch() -> KillSwitch:
    global _kill_switch
    if _kill_switch is None:
        _kill_switch = KillSwitch()
    return _kill_switch
