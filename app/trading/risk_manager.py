"""
Hard risk controls — every order must pass ALL checks before execution.
Enforces:
  - max loss per day
  - max order size
  - max open positions
  - allowed trading hours (IST)
  - symbol whitelist
  - cooldown between trades
  - mandatory stop loss
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from loguru import logger

from app.config import settings
from app.models.schemas import OrderRequest, Position, RiskCheckResult

# IST offset
IST = timezone(timedelta(hours=5, minutes=30))


class RiskManager:
    """Stateful risk gate — tracks daily P&L and cooldown timestamps."""

    def __init__(self) -> None:
        self._daily_realized_pnl: float = 0.0
        self._daily_date: str = ""
        self._last_trade_time: Optional[datetime] = None
        self._open_position_count: int = 0

    # ── Main entry point ───────────────────────────────────────────────────

    def check(
        self,
        order: OrderRequest,
        current_positions: list[Position] | None = None,
        daily_pnl: float = 0.0,
    ) -> RiskCheckResult:
        """
        Run all risk checks against a proposed order.
        Returns a RiskCheckResult with pass/fail and any violations.
        """
        violations: list[str] = []
        checks: list[str] = []
        now_ist = datetime.now(IST)

        # Reset daily tracking at midnight
        today = now_ist.strftime("%Y-%m-%d")
        if today != self._daily_date:
            self._daily_realized_pnl = 0.0
            self._daily_date = today

        self._daily_realized_pnl = daily_pnl
        self._open_position_count = len(current_positions) if current_positions else 0

        # ── 1. Max loss per day ────────────────────────────────────────
        checks.append("max_loss_per_day")
        if self._daily_realized_pnl < -settings.max_loss_per_day:
            violations.append(
                f"Daily loss limit breached: ₹{self._daily_realized_pnl:.2f} "
                f"exceeds max ₹{settings.max_loss_per_day:.2f}"
            )

        # ── 2. Max order size ──────────────────────────────────────────
        checks.append("max_order_size")
        order_value = order.quantity * (order.price if order.price > 0 else 1)
        if order_value > settings.max_order_size:
            violations.append(
                f"Order value ₹{order_value:.2f} exceeds max ₹{settings.max_order_size:.2f}"
            )

        # ── 3. Max open positions ──────────────────────────────────────
        checks.append("max_open_positions")
        if self._open_position_count >= settings.max_open_positions:
            violations.append(
                f"Open positions ({self._open_position_count}) at max limit "
                f"({settings.max_open_positions})"
            )

        # ── 4. Allowed trading hours ───────────────────────────────────
        checks.append("allowed_trading_hours")
        start_parts = settings.allowed_trading_start.split(":")
        end_parts = settings.allowed_trading_end.split(":")
        market_open = now_ist.replace(
            hour=int(start_parts[0]),
            minute=int(start_parts[1]),
            second=0,
            microsecond=0,
        )
        market_close = now_ist.replace(
            hour=int(end_parts[0]),
            minute=int(end_parts[1]),
            second=0,
            microsecond=0,
        )
        if not (market_open <= now_ist <= market_close):
            violations.append(
                f"Outside trading hours: {settings.allowed_trading_start} - "
                f"{settings.allowed_trading_end} IST (current: {now_ist.strftime('%H:%M')})"
            )

        # ── 5. Weekend check ──────────────────────────────────────────
        checks.append("weekday_check")
        if now_ist.weekday() >= 5:  # Saturday=5, Sunday=6
            violations.append("Markets closed on weekends")

        # ── 6. Symbol whitelist ────────────────────────────────────────
        checks.append("symbol_whitelist")
        whitelist = settings.whitelisted_symbols
        if whitelist and order.trading_symbol.upper() not in whitelist:
            violations.append(
                f"Symbol '{order.trading_symbol}' not in whitelist: {whitelist}"
            )

        # ── 7. Cooldown between trades ─────────────────────────────────
        checks.append("cooldown_between_trades")
        if self._last_trade_time is not None:
            elapsed = (now_ist - self._last_trade_time).total_seconds()
            if elapsed < settings.cooldown_between_trades_seconds:
                remaining = settings.cooldown_between_trades_seconds - elapsed
                violations.append(
                    f"Cooldown active: {remaining:.0f}s remaining "
                    f"(min {settings.cooldown_between_trades_seconds}s between trades)"
                )

        # ── 8. Mandatory stop loss ─────────────────────────────────────
        checks.append("mandatory_stop_loss")
        if order.order_side.value == "BUY" and order.stoploss_price is None:
            violations.append(
                f"Stop loss is mandatory (min {settings.mandatory_stop_loss_percent}% "
                f"from entry). Set stoploss_price on the order."
            )
        elif (
            order.order_side.value == "BUY"
            and order.stoploss_price is not None
            and order.price > 0
        ):
            sl_pct = ((order.price - order.stoploss_price) / order.price) * 100
            if sl_pct < settings.mandatory_stop_loss_percent:
                violations.append(
                    f"Stop loss too tight: {sl_pct:.2f}% < mandatory "
                    f"{settings.mandatory_stop_loss_percent}%"
                )

        passed = len(violations) == 0
        if not passed:
            logger.warning(f"Risk check FAILED: {violations}")
        else:
            logger.info("Risk check PASSED")

        return RiskCheckResult(
            passed=passed,
            violations=violations,
            checks_performed=checks,
        )

    def record_trade(self) -> None:
        """Update last trade time after a successful order placement."""
        self._last_trade_time = datetime.now(IST)

    def update_daily_pnl(self, pnl: float) -> None:
        """Externally update daily realized P&L."""
        self._daily_realized_pnl = pnl


# ── Singleton ──────────────────────────────────────────────────────────────────

_risk_mgr: RiskManager | None = None


def get_risk_manager() -> RiskManager:
    global _risk_mgr
    if _risk_mgr is None:
        _risk_mgr = RiskManager()
    return _risk_mgr
