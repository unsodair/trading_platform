"""
Strategy API routes — list, load, run strategies.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.models.schemas import MarketRegime, StrategyMetadata, StrategySignal
from app.strategies.engine import get_strategy_engine

router = APIRouter(prefix="/api/strategies", tags=["Strategies"])


@router.get("/", response_model=list[StrategyMetadata])
async def list_strategies():
    """List all discovered strategy plugins and their metadata."""
    engine = get_strategy_engine()
    engine.discover_plugins()
    return engine.get_loaded_strategies()


@router.post("/load")
async def load_all_strategies():
    """Load all approved strategy plugins."""
    engine = get_strategy_engine()
    count = engine.load_all()
    return {"loaded": count, "strategies": [m.name for m in engine.get_loaded_strategies()]}


@router.post("/load/{plugin_name}")
async def load_strategy(plugin_name: str):
    """Load a specific strategy plugin."""
    engine = get_strategy_engine()
    instance = engine.load_plugin(plugin_name)
    if instance is None:
        return {"status": "error", "message": f"Failed to load '{plugin_name}'"}
    return {"status": "ok", "loaded": instance.name}


@router.get("/active", response_model=list[StrategyMetadata])
async def get_active_strategies():
    """Get currently active strategies."""
    engine = get_strategy_engine()
    return engine.get_active_strategies()


@router.post("/run/{plugin_name}")
async def run_strategy(
    plugin_name: str,
    regime: MarketRegime = MarketRegime.RANGE_BOUND,
    market_data: dict[str, Any] | None = None,
    indicators: dict[str, Any] | None = None,
):
    """Run a specific strategy and return its signals."""
    engine = get_strategy_engine()
    signals = await engine.run_strategy(
        plugin_name=plugin_name,
        market_data=market_data or {},
        indicators=indicators or {},
        regime=regime,
    )
    return {"strategy": plugin_name, "signals": [s.model_dump() for s in signals]}


@router.post("/run-all")
async def run_all_strategies(
    regime: MarketRegime = MarketRegime.RANGE_BOUND,
    market_data: dict[str, Any] | None = None,
    indicators: dict[str, Any] | None = None,
):
    """Run all loaded strategies and collect signals."""
    engine = get_strategy_engine()
    results = await engine.run_all(
        market_data=market_data or {},
        indicators=indicators or {},
        regime=regime,
    )
    return {
        name: [s.model_dump() for s in signals]
        for name, signals in results.items()
    }
