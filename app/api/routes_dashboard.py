"""
Dashboard API routes — serves the web dashboard and its data endpoint.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.brokers.dhan_adapter import get_dhan_adapter
from app.config import settings
from app.database import get_db
from app.discovery.github_scanner import get_github_scanner
from app.models.schemas import (
    BrokerStatus,
    DashboardState,
    FundData,
    MarketRegime,
    TradingMode,
)
from app.strategies.engine import get_strategy_engine
from app.trading.paper_engine import get_paper_engine

from app.utils.paths import get_templates_path

templates = Jinja2Templates(directory=str(get_templates_path()))
# Workaround for Python 3.14 Jinja2 bug: disable template caching
templates.env.cache = None

router = APIRouter(tags=["Dashboard"])


@router.get("/", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    """Serve the main dashboard HTML page."""
    return templates.TemplateResponse(request, "index.html", {})


@router.get("/api/dashboard/state")
async def dashboard_state(db: AsyncSession = Depends(get_db)):
    """Return the full dashboard state as JSON."""
    broker = get_dhan_adapter()

    # Broker status
    try:
        broker_status = await broker.connect()
    except Exception:
        broker_status = BrokerStatus(connected=False, client_id=settings.dhan_client_id)

    # Positions
    if settings.trading_mode == TradingMode.PAPER:
        positions = await get_paper_engine().get_positions(db)
        orders = await get_paper_engine().get_orders(db)
        daily_pnl = await get_paper_engine().get_daily_pnl(db)
    else:
        positions = await broker.get_positions()
        orders = await broker.get_orders()
        daily_pnl = 0.0

    # Funds
    try:
        funds = await broker.get_funds()
    except Exception:
        funds = FundData()

    # Strategies
    engine = get_strategy_engine()
    engine.discover_plugins()
    active_strategies = engine.get_active_strategies()
    all_strategies = engine.get_loaded_strategies()

    # Discovered candidates
    scanner = get_github_scanner()
    try:
        candidates = await scanner.get_all_candidates(db)
    except Exception:
        candidates = []

    return DashboardState(
        broker_status=broker_status,
        trading_mode=TradingMode(settings.trading_mode.value),
        market_regime=MarketRegime.RANGE_BOUND,
        positions=positions,
        active_strategies=all_strategies,
        candidate_strategies=candidates[:20],
        todays_pnl=daily_pnl,
        funds=funds,
        recent_orders=orders[:20] if orders else [],
    ).model_dump()


@router.get("/api/dashboard/regime")
async def get_regime():
    """Get current market regime (placeholder — requires OHLCV data feed)."""
    return {
        "regime": MarketRegime.RANGE_BOUND.value,
        "note": "Connect market data feed for live regime detection",
    }
