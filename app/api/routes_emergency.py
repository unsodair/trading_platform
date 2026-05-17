"""
Emergency API routes — admin-facing kill switch controls.

Provides endpoints to:
  - Activate / deactivate global halt
  - Block / unblock specific symbols
  - Freeze / unfreeze individual strategies
  - Enable / disable broker routing
  - View current kill switch status and event audit trail
"""

from __future__ import annotations

from pydantic import BaseModel
from typing import Optional

from fastapi import APIRouter

from loguru import logger

from app.trading.kill_switch import get_kill_switch

router = APIRouter(prefix="/api/emergency", tags=["Emergency"])


# ── Request Models ─────────────────────────────────────────────────────────────

class HaltRequest(BaseModel):
    reason: str = "Manual activation"


class SymbolRequest(BaseModel):
    symbol: str
    reason: str = "Manual"


class StrategyRequest(BaseModel):
    strategy_name: str
    reason: str = "Manual"


class ThresholdRequest(BaseModel):
    max_drawdown_trigger: Optional[float] = None
    failure_count_trigger: Optional[int] = None


# ── Status ─────────────────────────────────────────────────────────────────────

@router.get("/status")
async def get_kill_switch_status():
    """Get the full current state of the kill switch, including event log."""
    ks = get_kill_switch()
    status = ks.get_status()
    return status.model_dump()


# ── Global Halt ────────────────────────────────────────────────────────────────

@router.post("/halt/activate")
async def activate_global_halt(req: HaltRequest):
    """🚨 IMMEDIATELY halt ALL new order placement across the entire platform."""
    ks = get_kill_switch()
    ks.activate_global_halt(reason=req.reason, triggered_by="admin")
    return {
        "status": "activated",
        "global_halt": True,
        "message": f"🚨 GLOBAL HALT ACTIVATED — {req.reason}",
    }


@router.post("/halt/deactivate")
async def deactivate_global_halt(req: HaltRequest):
    """Resume order placement after a global halt."""
    ks = get_kill_switch()
    ks.deactivate_global_halt(reason=req.reason, triggered_by="admin")
    return {
        "status": "deactivated",
        "global_halt": False,
        "message": f"✅ GLOBAL HALT DEACTIVATED — {req.reason}",
    }


# ── Broker Routing ─────────────────────────────────────────────────────────────

@router.post("/broker/disable")
async def disable_broker(req: HaltRequest):
    """Sever broker routing — no orders will reach the exchange."""
    ks = get_kill_switch()
    ks.disable_broker(reason=req.reason)
    return {"broker_disabled": True, "message": f"🔌 Broker routing DISABLED — {req.reason}"}


@router.post("/broker/enable")
async def enable_broker(req: HaltRequest):
    """Re-enable broker routing."""
    ks = get_kill_switch()
    ks.enable_broker(reason=req.reason)
    return {"broker_disabled": False, "message": f"🔌 Broker routing ENABLED — {req.reason}"}


# ── Symbol Blocking ───────────────────────────────────────────────────────────

@router.post("/symbols/block")
async def block_symbol(req: SymbolRequest):
    """Block a specific symbol from being traded."""
    ks = get_kill_switch()
    ks.block_symbol(req.symbol, reason=req.reason)
    return {"symbol": req.symbol.upper(), "blocked": True}


@router.post("/symbols/unblock")
async def unblock_symbol(req: SymbolRequest):
    """Remove a symbol from the blocked list."""
    ks = get_kill_switch()
    ks.unblock_symbol(req.symbol, reason=req.reason)
    return {"symbol": req.symbol.upper(), "blocked": False}


# ── Strategy Freezing ──────────────────────────────────────────────────────────

@router.post("/strategies/freeze")
async def freeze_strategy(req: StrategyRequest):
    """Freeze a specific strategy — its signals will be ignored."""
    ks = get_kill_switch()
    ks.freeze_strategy(req.strategy_name, reason=req.reason)
    return {"strategy": req.strategy_name, "frozen": True}


@router.post("/strategies/unfreeze")
async def unfreeze_strategy(req: StrategyRequest):
    """Unfreeze a specific strategy."""
    ks = get_kill_switch()
    ks.unfreeze_strategy(req.strategy_name, reason=req.reason)
    return {"strategy": req.strategy_name, "frozen": False}


# ── Auto-Trigger Thresholds ────────────────────────────────────────────────────

@router.post("/thresholds")
async def update_thresholds(req: ThresholdRequest):
    """Update auto-trigger thresholds at runtime."""
    ks = get_kill_switch()
    if req.max_drawdown_trigger is not None:
        ks._max_drawdown_trigger = req.max_drawdown_trigger
        logger.info(f"Kill switch drawdown trigger → ₹{req.max_drawdown_trigger:.2f}")
    if req.failure_count_trigger is not None:
        ks._failure_count_trigger = req.failure_count_trigger
        logger.info(f"Kill switch failure trigger → {req.failure_count_trigger} failures")

    return {
        "max_drawdown_trigger": ks._max_drawdown_trigger,
        "failure_count_trigger": ks._failure_count_trigger,
    }
