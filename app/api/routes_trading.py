"""
Trading API routes — paper and live order execution, positions, P&L.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.logger import get_audit_logger
from app.brokers.factory import get_broker
from app.config import TradingMode, settings
from app.database import get_db
from app.models.schemas import (
    LLMDecision,
    MarketRegime,
    OrderRequest,
    OrderResponse,
    OrderStatus,
    Position,
)
from app.trading.live_engine import LiveTradingEngine
from app.trading.paper_engine import get_paper_engine
from app.trading.risk_manager import get_risk_manager
from app.trading.kill_switch import get_kill_switch

router = APIRouter(prefix="/api/trading", tags=["Trading"])


@router.get("/mode")
async def get_trading_mode():
    """Get current trading mode."""
    return {"mode": settings.trading_mode.value}


@router.post("/mode/{mode}")
async def set_trading_mode(mode: str):
    """Switch between paper and live modes (runtime only, doesn't persist to .env)."""
    try:
        settings.trading_mode = TradingMode(mode)
        return {"mode": settings.trading_mode.value, "message": f"Switched to {mode} mode"}
    except ValueError:
        return {"error": f"Invalid mode '{mode}'. Use 'paper' or 'live'"}


@router.get("/market")
async def get_active_market():
    """Get current active market."""
    return {"market": settings.active_market}


@router.post("/market/{market}")
async def set_active_market(market: str):
    """Switch active market (runtime only)."""
    valid_markets = ["NSE_EQ", "CRYPTO", "US_EQ", "GLOBAL_EQ"]
    if market in valid_markets:
        settings.active_market = market
        return {"market": settings.active_market, "message": f"Switched to {market} market"}
    return {"error": f"Invalid market '{market}'. Use {valid_markets}"}


@router.post("/order", response_model=OrderResponse)
async def execute_order(
    order: OrderRequest,
    strategy_name: str = "manual",
    regime: MarketRegime = MarketRegime.RANGE_BOUND,
    db: AsyncSession = Depends(get_db),
):
    """
    Execute an order — routes to paper or live engine based on current mode.
    Kill switch is checked FIRST, before any risk checks or execution.
    """
    # ── Gate 0: Kill Switch (highest priority) ─────────────────────
    ks = get_kill_switch()
    allowed, ks_reason = ks.is_order_allowed(
        symbol=order.trading_symbol,
        strategy_name=strategy_name,
    )
    if not allowed:
        return OrderResponse(
            status=OrderStatus.REJECTED,
            message=f"Kill switch: {ks_reason}",
        )

    risk_mgr = get_risk_manager()

    if settings.trading_mode == TradingMode.PAPER:
        # Paper trading — risk check then simulate
        positions = await get_paper_engine().get_positions(db)
        daily_pnl = await get_paper_engine().get_daily_pnl(db)

        # Auto-trigger kill switch on drawdown breach
        ks.check_drawdown(daily_pnl)
        if ks._global_halt:
            return OrderResponse(
                status=OrderStatus.REJECTED,
                message="Kill switch auto-triggered: drawdown breach",
            )

        risk_result = risk_mgr.check(order, positions, daily_pnl)

        if not risk_result.passed:
            return OrderResponse(
                status=OrderStatus.REJECTED,
                message=f"Risk check failed: {risk_result.violations}",
            )

        response = await get_paper_engine().place_order(order, db)

        # Track success/failure for auto-trigger
        if response.status == OrderStatus.REJECTED:
            ks.record_failure()
        else:
            ks.record_success()

        # Audit
        await get_audit_logger().log(
            strategy_used=strategy_name,
            market_regime=regime.value,
            order_request=order.model_dump(),
            broker_response=response.model_dump(),
            risk_check=risk_result.model_dump(),
            trading_mode="paper",
            db=db,
        )
        risk_mgr.record_trade()
        return response

    else:
        # Live trading
        broker = get_broker()
        live_engine = LiveTradingEngine(broker)
        positions = await broker.get_positions()
        return await live_engine.execute_order(
            order=order,
            decision=None,
            strategy_name=strategy_name,
            regime=regime,
            positions=positions,
            db=db,
        )


@router.get("/positions", response_model=list[Position])
async def get_positions(db: AsyncSession = Depends(get_db)):
    """Get current positions (paper or live)."""
    if settings.trading_mode == TradingMode.PAPER:
        return await get_paper_engine().get_positions(db)
    else:
        broker = get_broker()
        return await broker.get_positions()


@router.get("/orders")
async def get_orders(db: AsyncSession = Depends(get_db)):
    """Get recent orders."""
    if settings.trading_mode == TradingMode.PAPER:
        return await get_paper_engine().get_orders(db)
    else:
        broker = get_broker()
        return await broker.get_orders()


@router.get("/pnl")
async def get_daily_pnl(db: AsyncSession = Depends(get_db)):
    """Get today's P&L."""
    if settings.trading_mode == TradingMode.PAPER:
        pnl = await get_paper_engine().get_daily_pnl(db)
        return {"mode": "paper", "daily_pnl": pnl}
    return {"mode": "live", "daily_pnl": 0.0}


@router.get("/risk-status")
async def get_risk_status():
    """Get current risk manager state."""
    mgr = get_risk_manager()
    return {
        "max_loss_per_day": settings.max_loss_per_day,
        "max_order_size": settings.max_order_size,
        "max_open_positions": settings.max_open_positions,
        "trading_hours": f"{settings.allowed_trading_start} - {settings.allowed_trading_end}",
        "cooldown_seconds": settings.cooldown_between_trades_seconds,
        "mandatory_sl_pct": settings.mandatory_stop_loss_percent,
    }


@router.get("/audit")
async def get_audit_log(limit: int = 50, db: AsyncSession = Depends(get_db)):
    """Get recent audit entries."""
    return await get_audit_logger().get_recent(db, limit)


@router.post("/paper/reset")
async def reset_paper(db: AsyncSession = Depends(get_db)):
    """Reset all paper trades and positions."""
    await get_paper_engine().reset(db)
    return {"message": "Paper trading engine reset"}
