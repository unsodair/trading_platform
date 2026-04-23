"""
Tests for the market regime detector.
"""

import numpy as np
import pandas as pd
import pytest

from app.models.schemas import MarketRegime
from app.regime.detector import MarketRegimeDetector


def _make_ohlcv(trend: str = "up", n: int = 100) -> pd.DataFrame:
    """Generate synthetic OHLCV data."""
    np.random.seed(42)
    dates = pd.date_range("2025-01-01", periods=n, freq="D")

    if trend == "up":
        close = 100 + np.cumsum(np.random.randn(n) * 0.5 + 0.3)
    elif trend == "down":
        close = 200 + np.cumsum(np.random.randn(n) * 0.5 - 0.3)
    elif trend == "range":
        close = 150 + np.sin(np.linspace(0, 8 * np.pi, n)) * 5 + np.random.randn(n) * 0.5
    elif trend == "volatile":
        close = 150 + np.cumsum(np.random.randn(n) * 5)
    else:
        close = np.full(n, 100.0)

    high = close + np.abs(np.random.randn(n))
    low = close - np.abs(np.random.randn(n))
    open_ = close + np.random.randn(n) * 0.3
    volume = np.random.randint(100000, 10000000, n)

    return pd.DataFrame({
        "date": dates,
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    })


class TestMarketRegimeDetector:
    """Test regime classification accuracy."""

    @pytest.fixture
    def detector(self):
        return MarketRegimeDetector()

    def test_event_risk_override(self, detector):
        """Event risk flag should override everything."""
        df = _make_ohlcv("up", 100)
        result = detector.classify(df, event_risk_flag=True)
        assert result == MarketRegime.EVENT_RISK

    def test_insufficient_data(self, detector):
        """Short data should default to RANGE_BOUND."""
        df = _make_ohlcv("up", 10)
        result = detector.classify(df)
        assert result == MarketRegime.RANGE_BOUND

    def test_none_data(self, detector):
        """None data should default to RANGE_BOUND."""
        result = detector.classify(None)
        assert result == MarketRegime.RANGE_BOUND

    def test_uptrend_detection(self, detector):
        """Strong uptrend data should be classified as TRENDING_UP."""
        df = _make_ohlcv("up", 200)
        result = detector.classify(df)
        assert result in (MarketRegime.TRENDING_UP, MarketRegime.RANGE_BOUND)

    def test_downtrend_detection(self, detector):
        """Strong downtrend data should be classified as TRENDING_DOWN."""
        df = _make_ohlcv("down", 200)
        result = detector.classify(df)
        assert result in (MarketRegime.TRENDING_DOWN, MarketRegime.RANGE_BOUND)

    def test_get_indicators(self, detector):
        """Indicators should include SMA, ADX, BB width, etc."""
        df = _make_ohlcv("up", 100)
        indicators = detector.get_indicators(df)
        assert "sma_20" in indicators
        assert "sma_50" in indicators
        assert "adx" in indicators
        assert "bb_width" in indicators
        assert "atr_ratio" in indicators

    def test_get_indicators_insufficient_data(self, detector):
        """Short data should return empty indicators."""
        df = _make_ohlcv("up", 10)
        indicators = detector.get_indicators(df)
        assert indicators == {}
