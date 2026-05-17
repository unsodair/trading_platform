"""
Market Scanner API routes — endpoints to get top gainers, losers, and preset watchlists.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.scanner.market_scanner import get_market_scanner

router = APIRouter(prefix="/api/scanner", tags=["Scanner"])


@router.get("/movers")
async def get_market_movers(index: str = "NIFTY 50", count: int = 10):
    """Get the top gainers and losers from the live market."""
    scanner = get_market_scanner()
    result = await scanner.scan_market(index=index, count=count)
    return result.model_dump()


@router.get("/presets")
async def get_preset_categories():
    """Get all preset category metadata."""
    scanner = get_market_scanner()
    return scanner.get_preset_categories()


@router.get("/presets/{category}")
async def get_preset_stocks(category: str):
    """Get stock symbols for a specific preset category."""
    scanner = get_market_scanner()
    return {"category": category, "symbols": scanner.get_preset_stocks(category)}
