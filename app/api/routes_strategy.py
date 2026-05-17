"""
Strategy API routes — list, load, run strategies.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from pydantic import BaseModel

from app.models.schemas import MarketRegime, StrategyMetadata, StrategySignal
from app.strategies.engine import get_strategy_engine
from app.scanner.market_scanner import get_market_scanner
from app.utils.paths import get_plugins_path
import yaml

router = APIRouter(prefix="/api/strategies", tags=["Strategies"])

class UpdateSymbolsRequest(BaseModel):
    symbols: list[str] | None = None
    preset: str | None = None
    scan_market: str | None = None  # "gainers" or "losers"
    scan_count: int = 5


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


@router.post("/{plugin_name}/symbols")
async def update_strategy_symbols(plugin_name: str, req: UpdateSymbolsRequest):
    """Update the target stocks for a strategy (custom, presets, or top gainers/losers)."""
    engine = get_strategy_engine()
    instance = engine.get_strategy(plugin_name)
    if not instance:
        return {"status": "error", "message": f"Strategy {plugin_name} not loaded or active."}

    new_symbols = []
    
    if req.scan_market:
        scanner = get_market_scanner()
        scan_result = await scanner.scan_market(count=req.scan_count)
        if req.scan_market == "gainers":
            new_symbols = [s.symbol for s in scan_result.gainers]
        elif req.scan_market == "losers":
            new_symbols = [s.symbol for s in scan_result.losers]
            
    elif req.preset:
        scanner = get_market_scanner()
        new_symbols = scanner.get_preset_stocks(req.preset)
        
    elif req.symbols is not None:
        new_symbols = [s.upper().strip() for s in req.symbols if s.strip()]

    if not new_symbols:
        return {"status": "error", "message": "No valid symbols generated from request."}

    # Update the config.yaml file
    config_file = get_plugins_path() / plugin_name / "config.yaml"
    if config_file.exists():
        with open(config_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            
        data["symbols"] = new_symbols
        
        with open(config_file, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
            
    # Reload the plugin in memory
    engine.load_plugin(plugin_name)
    
    return {
        "status": "success", 
        "message": f"Updated {plugin_name} to trade {len(new_symbols)} symbols.",
        "symbols": new_symbols
    }
