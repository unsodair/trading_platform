"""
Paper trading engine — simulates order fills against a virtual portfolio.
Stores all trades in the paper_trades / paper_positions tables.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from loguru import logger
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db_models import PaperPosition, PaperTrade
from app.models.schemas import (
    OrderRequest,
    OrderResponse,
    OrderStatus,
    Position,
    OrderDetail,
)


class PaperTradingEngine:
    """
    Virtual execution engine — simulates fills at the order price (or a small
    slippage) and maintains paper positions.
    """

    def __init__(self, slippage_bps: float = 5.0) -> None:
        """
        Parameters
        ----------
        slippage_bps : float
            Simulated slippage in basis points (default 5 = 0.05%).
        """
        self._slippage_bps = slippage_bps

    # ── Place ──────────────────────────────────────────────────────────────

    async def place_order(
        self, order: OrderRequest, db: AsyncSession
    ) -> OrderResponse:
        """Simulate placing an order. Immediately 'fills' at execution price."""
        order_id = f"PAPER-{uuid.uuid4().hex[:12].upper()}"
        fill_price = self._apply_slippage(order.price, order.order_side.value)

        # Record the trade
        trade = PaperTrade(
            order_id=order_id,
            timestamp=datetime.utcnow(),
            trading_symbol=order.trading_symbol,
            exchange=order.exchange_segment.value,
            side=order.order_side.value,
            order_type=order.order_type.value,
            product_type=order.product_type.value,
            quantity=order.quantity,
            price=fill_price,
            trigger_price=order.trigger_price,
            status="FILLED",
            strategy=order.tag,
        )
        db.add(trade)

        # Update paper position
        await self._update_position(order, fill_price, db)
        await db.commit()

        logger.info(
            f"📝 Paper order filled: {order.order_side.value} "
            f"{order.quantity} x {order.trading_symbol} @ ₹{fill_price:.2f} "
            f"[{order_id}]"
        )

        return OrderResponse(
            order_id=order_id,
            status=OrderStatus.FILLED,
            message=f"Paper trade filled at ₹{fill_price:.2f}",
            raw_response={"paper": True, "fill_price": fill_price},
        )

    # ── Positions ──────────────────────────────────────────────────────────

    async def get_positions(self, db: AsyncSession) -> list[Position]:
        """Return all current paper positions."""
        result = await db.execute(
            select(PaperPosition).where(PaperPosition.quantity != 0)
        )
        rows = result.scalars().all()
        return [
            Position(
                trading_symbol=r.trading_symbol,
                exchange=r.exchange,
                quantity=r.quantity,
                avg_price=r.avg_price,
                product_type="PAPER",
            )
            for r in rows
        ]

    # ── Orders ─────────────────────────────────────────────────────────────

    async def get_orders(self, db: AsyncSession, limit: int = 50) -> list[OrderDetail]:
        """Return recent paper trades."""
        result = await db.execute(
            select(PaperTrade)
            .order_by(PaperTrade.timestamp.desc())
            .limit(limit)
        )
        rows = result.scalars().all()
        return [
            OrderDetail(
                order_id=r.order_id,
                trading_symbol=r.trading_symbol,
                exchange=r.exchange,
                order_side=r.side,
                order_type=r.order_type,
                product_type=r.product_type,
                quantity=r.quantity,
                price=r.price,
                trigger_price=r.trigger_price,
                status=r.status,
                filled_qty=r.quantity,
                timestamp=r.timestamp,
            )
            for r in rows
        ]

    # ── P&L ────────────────────────────────────────────────────────────────

    async def get_daily_pnl(self, db: AsyncSession) -> float:
        """Compute today's realized P&L from paper trades."""
        today = datetime.utcnow().strftime("%Y-%m-%d")
        result = await db.execute(
            select(PaperTrade).where(
                PaperTrade.timestamp >= datetime.strptime(today, "%Y-%m-%d")
            )
        )
        trades = result.scalars().all()
        return sum(t.pnl for t in trades)

    # ── Internal helpers ───────────────────────────────────────────────────

    def _apply_slippage(self, price: float, side: str) -> float:
        """Apply slippage — worse fill for the trader."""
        if price <= 0:
            return price
        slip = price * (self._slippage_bps / 10_000)
        return price + slip if side == "BUY" else price - slip

    async def _update_position(
        self, order: OrderRequest, fill_price: float, db: AsyncSession
    ) -> None:
        """Update or create a paper position based on the filled order."""
        result = await db.execute(
            select(PaperPosition).where(
                PaperPosition.trading_symbol == order.trading_symbol
            )
        )
        pos = result.scalar_one_or_none()

        qty_delta = order.quantity if order.order_side.value == "BUY" else -order.quantity

        if pos is None:
            pos = PaperPosition(
                trading_symbol=order.trading_symbol,
                exchange=order.exchange_segment.value,
                quantity=qty_delta,
                avg_price=fill_price,
                side=order.order_side.value,
                strategy=order.tag,
            )
            db.add(pos)
        else:
            old_value = pos.quantity * pos.avg_price
            new_value = qty_delta * fill_price
            new_qty = pos.quantity + qty_delta

            if new_qty != 0:
                if (pos.quantity > 0 and qty_delta > 0) or (pos.quantity < 0 and qty_delta < 0):
                    # Adding to position — weighted average
                    pos.avg_price = (old_value + new_value) / new_qty
                pos.quantity = new_qty
            else:
                # Position closed
                pos.quantity = 0
                pos.avg_price = 0.0

            pos.updated_at = datetime.utcnow()

    # ── Reset ──────────────────────────────────────────────────────────────

    async def reset(self, db: AsyncSession) -> None:
        """Clear all paper trades and positions (dev/testing)."""
        await db.execute(delete(PaperTrade))
        await db.execute(delete(PaperPosition))
        await db.commit()
        logger.info("Paper trading engine reset")


# ── Singleton ──────────────────────────────────────────────────────────────────

_paper_engine: PaperTradingEngine | None = None


def get_paper_engine() -> PaperTradingEngine:
    global _paper_engine
    if _paper_engine is None:
        _paper_engine = PaperTradingEngine()
    return _paper_engine
