import pytest
from app.strategies.engine import get_strategy_engine

@pytest.mark.asyncio
async def test_all_strategies_load():
    engine = get_strategy_engine()
    loaded_count = engine.load_all()
    
    # We expect 11 strategies (10 new + 1 sample)
    assert loaded_count >= 11
    
    loaded_strategies = engine.get_loaded_strategies()
    strategy_names = [m.name for m in loaded_strategies]
    
    expected_strategies = [
        "Mean Reversion (RSI)",
        "EMA Scalping (9/15)",
        "Breakout Strategy",
        "Supertrend Follower",
        "VWAP+EMA9 Scalper",
        "Gap Fill Strategy",
        "Pivot Points S/R",
        "Golden Cross",
        "Candlestick Patterns",
        "Bollinger Band Squeeze"
    ]
    
    for name in expected_strategies:
        assert any(name in s_name for s_name in strategy_names), f"Strategy {name} not found"

@pytest.mark.asyncio
async def test_strategies_evaluation_boilerplate():
    engine = get_strategy_engine()
    engine.load_all()
    
    # Mock data
    market_data = {
        "NSE_EQ|INE002A01018": {"close": 100, "open": 100, "high": 105, "low": 95, "volume": 1000}
    }
    indicators = {
        "NSE_EQ|INE002A01018_rsi_14": 50,
        "NSE_EQ|INE002A01018_ema_9": 100,
        "NSE_EQ|INE002A01018_ema_15": 99,
        "NSE_EQ|INE002A01018_vwap": 100
    }
    from app.models.schemas import MarketRegime
    regime = MarketRegime.RANGE_BOUND
    
    # Run all
    results = await engine.run_all(market_data, indicators, regime)
    assert isinstance(results, dict)
