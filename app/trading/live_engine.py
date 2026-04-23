"""
Live trading execution engine — wraps the real broker adapter with full
risk checks, validation, and audit logging.

Live trading is DISABLED by default; requires TRADING_MODE=live in .env.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.logger import get_audit_logger
from app.brokers.base import BaseBroker
from app.config import TradingMode, settings
from app.models.schemas import (
    LLMDecision,
    MarketRegime,
    ModifyOrderRequest,
    OrderRequest,
    OrderResponse,
    OrderStatus,
    Position,
    RiskCheckResult,
)
from app.trading.risk_manager import get_risk_manager


class LiveTradingEngine:
    """
    Production execution engine — enforces:
      1. Mode must be LIVE
      2. All risk checks must pass
      3. LLM decision must be validated
      4. Everything is audit-logged
    """

    def __init__(self, broker: BaseBroker) -> None:
        self._broker = broker
        self._risk = get_risk_manager()
        self._audit = get_audit_logger()

    # ── Execute Order ──────────────────────────────────────────────────────

    async def execute_order(
        self,
        order: OrderRequest,
        decision: LLMDecision | None,
        strategy_name: str,
        regime: MarketRegime,
        positions: list[Position] | None = None,
        daily_pnl: float = 0.0,
        db: AsyncSession | None = None,
    ) -> OrderResponse:
        """
        Execute a live order through the broker, after all safeguards.

        Parameters
        ----------
        order : OrderRequest
        decision : LLMDecision | None — the LLM decision that triggered this order
        strategy_name : str
        regime : MarketRegime
        positions : list[Position] | None — current open positions
        daily_pnl : float — today's realized P&L
        db : AsyncSession | None — for audit logging
        """
        # ── Gate 1: Mode check ─────────────────────────────────────────
        if settings.trading_mode != TradingMode.LIVE:
            msg = "Live trading is DISABLED. Set TRADING_MODE=live in .env"
            logger.warning(msg)
            return OrderResponse(
                status=OrderStatus.REJECTED,
                message=msg,
            )

        # ── Gate 2: Risk checks ────────────────────────────────────────
        risk_result: RiskCheckResult = self._risk.check(
            order=order,
            current_positions=positions,
            daily_pnl=daily_pnl,
        )

        if not risk_result.passed:
            logger.warning(
                f"🚫 Order REJECTED by risk manager: {risk_result.violations}"
            )
            # Audit the rejection
            if db:
                await self._audit.log(
                    raw_llm_output=decision.raw_output if decision else "",
                    parsed_decision=decision.model_dump() if decision else {},
                    strategy_used=strategy_name,
                    market_regime=regime.value,
                    order_request=order.model_dump(),
                    broker_response={"rejected_by": "risk_manager"},
                    risk_check=risk_result.model_dump(),
                    trading_mode="live",
                    notes=f"Risk violations: {risk_result.violations}",
                    db=db,
                )
            return OrderResponse(
                status=OrderStatus.REJECTED,
                message=f"Risk check failed: {risk_result.violations}",
            )

        # ── Gate 3: LLM decision validation ───────────────────────────
        if decision and decision.confidence < 0.3:
            msg = f"LLM confidence too low ({decision.confidence:.2f}), order blocked"
            logger.warning(msg)
            return OrderResponse(
                status=OrderStatus.REJECTED,
                message=msg,
            )

        # ── Gate 4: Execute via broker ─────────────────────────────────
        try:
            logger.info(
                f"🔴 LIVE ORDER: {order.order_side.value} {order.quantity} x "
                f"{order.trading_symbol} @ ₹{order.price:.2f}"
            )
            response = await self._broker.place_order(order)

            # Record trade time for cooldown
            if response.status != OrderStatus.REJECTED:
                self._risk.record_trade()

            # Audit the execution
            if db:
                await self._audit.log(
                    raw_llm_output=decision.raw_output if decision else "",
                    parsed_decision=decision.model_dump() if decision else {},
                    strategy_used=strategy_name,
                    market_regime=regime.value,
                    order_request=order.model_dump(),
                    broker_response=response.model_dump(),
                    risk_check=risk_result.model_dump(),
                    trading_mode="live",
                    notes="Live order executed",
                    db=db,
                )

            return response

        except Exception as exc:
            logger.error(f"Live order execution failed: {exc}")
            return OrderResponse(
                status=OrderStatus.REJECTED,
                message=f"Execution error: {exc}",
            )

    # ── Modify / Cancel ────────────────────────────────────────────────────

    async def modify_order(self, req: ModifyOrderRequest) -> OrderResponse:
        if settings.trading_mode != TradingMode.LIVE:
            return OrderResponse(
                status=OrderStatus.REJECTED,
                message="Live trading is DISABLED",
            )
        return await self._broker.modify_order(req)

    async def cancel_order(self, order_id: str) -> OrderResponse:
        if settings.trading_mode != TradingMode.LIVE:
            return OrderResponse(
                status=OrderStatus.REJECTED,
                message="Live trading is DISABLED",
            )
        return await self._broker.cancel_order(order_id)

    # ── Pass-through to broker ─────────────────────────────────────────────

    async def get_positions(self) -> list[Position]:
        return await self._broker.get_positions()

    async def get_orders(self):
        return await self._broker.get_orders()
