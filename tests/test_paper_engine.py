"""
Tests for the PaperTradingEngine realized P&L and position tracking.
"""

import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.models.db_models import Base, PaperPosition, PaperTrade
from app.trading.paper_engine import PaperTradingEngine
from app.models.schemas import (
    OrderRequest,
    OrderSide,
    OrderType,
    ProductType,
    ExchangeSegment,
)

@pytest.fixture
async def db_session():
    # Setup an in-memory SQLite database for database transaction tests
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    
    await engine.dispose()

@pytest.mark.asyncio
async def test_paper_engine_realized_pnl(db_session):
    engine = PaperTradingEngine()
    
    # 1. Buy INFY (open position)
    buy_order = OrderRequest(
        trading_symbol="INFY",
        exchange_segment=ExchangeSegment.NSE_EQ,
        security_id="1234",
        order_side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        product_type=ProductType.INTRADAY,
        quantity=10,
        price=1500.0,
    )
    
    resp = await engine.place_order(buy_order, db_session)
    assert resp.status.value == "FILLED"
    
    # Verify open position
    positions = await engine.get_positions(db_session)
    assert len(positions) == 1
    assert positions[0].trading_symbol == "INFY"
    assert positions[0].quantity == 10
    
    # Realized P&L should be 0.0 (increasing position)
    daily_pnl = await engine.get_daily_pnl(db_session)
    assert daily_pnl == 0.0
    
    # 2. Sell 4 shares of INFY @ 1550 (partially close position)
    sell_order = OrderRequest(
        trading_symbol="INFY",
        exchange_segment=ExchangeSegment.NSE_EQ,
        security_id="1234",
        order_side=OrderSide.SELL,
        order_type=OrderType.MARKET,
        product_type=ProductType.INTRADAY,
        quantity=4,
        price=1550.0,
    )
    
    resp_sell = await engine.place_order(sell_order, db_session)
    assert resp_sell.status.value == "FILLED"
    
    # Verify remaining position quantity
    positions = await engine.get_positions(db_session)
    assert len(positions) == 1
    assert positions[0].quantity == 6
    
    # Realized P&L should now be positive since we locked in profit
    daily_pnl = await engine.get_daily_pnl(db_session)
    assert daily_pnl > 0.0
    
    # 3. Buy 4 shares of INFY @ 1400 (should not realize P&L, only average down)
    buy_more = OrderRequest(
        trading_symbol="INFY",
        exchange_segment=ExchangeSegment.NSE_EQ,
        security_id="1234",
        order_side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        product_type=ProductType.INTRADAY,
        quantity=4,
        price=1400.0,
    )
    await engine.place_order(buy_more, db_session)
    
    # Check that realized P&L didn't change (still locked in profit only)
    new_daily_pnl = await engine.get_daily_pnl(db_session)
    assert new_daily_pnl == daily_pnl
