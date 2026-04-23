"""
Market-regime detector — classifies the current market into one of:
  trending_up | trending_down | range_bound | high_volatility | event_risk

Uses technical indicators (SMA, ADX, Bollinger Band width, ATR) computed
via the `ta` library on a pandas DataFrame.
"""

from __future__ import annotations

from typing import Any, Optional

import numpy as np
import pandas as pd
from loguru import logger

try:
    import ta
except ImportError:
    ta = None  # type: ignore[assignment]

from app.models.schemas import MarketRegime


class MarketRegimeDetector:
    """
    Stateless detector — takes OHLCV data and returns a regime classification.
    """

    def __init__(
        self,
        sma_short: int = 20,
        sma_long: int = 50,
        adx_period: int = 14,
        adx_trend_threshold: float = 25.0,
        bb_width_threshold: float = 0.08,
        atr_spike_factor: float = 1.5,
        lookback: int = 60,
    ) -> None:
        self.sma_short = sma_short
        self.sma_long = sma_long
        self.adx_period = adx_period
        self.adx_trend_threshold = adx_trend_threshold
        self.bb_width_threshold = bb_width_threshold
        self.atr_spike_factor = atr_spike_factor
        self.lookback = lookback

    def classify(
        self,
        df: pd.DataFrame,
        event_risk_flag: bool = False,
    ) -> MarketRegime:
        """
        Classify market regime from an OHLCV DataFrame.

        Parameters
        ----------
        df : pd.DataFrame
            Must have columns: open, high, low, close, volume
            At least ``lookback`` rows required.
        event_risk_flag : bool
            External signal (e.g. budget day, RBI policy) — overrides to EVENT_RISK.

        Returns
        -------
        MarketRegime
        """
        if event_risk_flag:
            return MarketRegime.EVENT_RISK

        if df is None or len(df) < self.lookback:
            logger.warning("Insufficient data for regime detection; defaulting to RANGE_BOUND")
            return MarketRegime.RANGE_BOUND

        try:
            close = df["close"].astype(float)
            high = df["high"].astype(float)
            low = df["low"].astype(float)

            # ── Indicators ─────────────────────────────────────────────
            sma_s = close.rolling(self.sma_short).mean()
            sma_l = close.rolling(self.sma_long).mean()

            adx_val = self._compute_adx(high, low, close)
            bb_width = self._compute_bb_width(close)
            atr_ratio = self._compute_atr_ratio(high, low, close)

            latest_close = close.iloc[-1]
            latest_sma_s = sma_s.iloc[-1]
            latest_sma_l = sma_l.iloc[-1]

            # ── Classification logic ───────────────────────────────────
            # 1) High volatility — ATR spike
            if atr_ratio > self.atr_spike_factor:
                return MarketRegime.HIGH_VOLATILITY

            # 2) Trending — strong ADX + SMA alignment
            if adx_val > self.adx_trend_threshold:
                if latest_sma_s > latest_sma_l and latest_close > latest_sma_s:
                    return MarketRegime.TRENDING_UP
                elif latest_sma_s < latest_sma_l and latest_close < latest_sma_s:
                    return MarketRegime.TRENDING_DOWN

            # 3) Range-bound — low ADX and narrow BB
            if adx_val < self.adx_trend_threshold and bb_width < self.bb_width_threshold:
                return MarketRegime.RANGE_BOUND

            # 4) Fallback — mild trend or mixed signals
            if latest_close > latest_sma_l:
                return MarketRegime.TRENDING_UP
            elif latest_close < latest_sma_l:
                return MarketRegime.TRENDING_DOWN

            return MarketRegime.RANGE_BOUND

        except Exception as exc:
            logger.error(f"Regime detection error: {exc}")
            return MarketRegime.RANGE_BOUND

    # ── Technical helpers ──────────────────────────────────────────────────

    def _compute_adx(
        self, high: pd.Series, low: pd.Series, close: pd.Series
    ) -> float:
        if ta is not None:
            try:
                adx_indicator = ta.trend.ADXIndicator(
                    high=high, low=low, close=close, window=self.adx_period
                )
                adx_series = adx_indicator.adx()
                return float(adx_series.dropna().iloc[-1]) if not adx_series.dropna().empty else 0.0
            except Exception:
                pass
        return 0.0

    def _compute_bb_width(self, close: pd.Series) -> float:
        if ta is not None:
            try:
                bb = ta.volatility.BollingerBands(close=close, window=20)
                upper = bb.bollinger_hband().iloc[-1]
                lower = bb.bollinger_lband().iloc[-1]
                mid = bb.bollinger_mavg().iloc[-1]
                if mid > 0:
                    return float((upper - lower) / mid)
            except Exception:
                pass
        return 0.05

    def _compute_atr_ratio(
        self, high: pd.Series, low: pd.Series, close: pd.Series
    ) -> float:
        """ATR ratio = latest ATR / average ATR over lookback."""
        if ta is not None:
            try:
                atr = ta.volatility.AverageTrueRange(
                    high=high, low=low, close=close, window=14
                )
                atr_series = atr.average_true_range().dropna()
                if len(atr_series) > 10:
                    latest = atr_series.iloc[-1]
                    avg = atr_series.iloc[-self.lookback :].mean()
                    return float(latest / avg) if avg > 0 else 1.0
            except Exception:
                pass
        return 1.0

    def get_indicators(self, df: pd.DataFrame) -> dict[str, Any]:
        """Return a dict of computed indicators for downstream consumption."""
        if df is None or len(df) < self.lookback:
            return {}
        try:
            close = df["close"].astype(float)
            high = df["high"].astype(float)
            low = df["low"].astype(float)
            return {
                "sma_20": float(close.rolling(20).mean().iloc[-1]),
                "sma_50": float(close.rolling(50).mean().iloc[-1]),
                "adx": self._compute_adx(high, low, close),
                "bb_width": self._compute_bb_width(close),
                "atr_ratio": self._compute_atr_ratio(high, low, close),
                "latest_close": float(close.iloc[-1]),
                "latest_high": float(high.iloc[-1]),
                "latest_low": float(low.iloc[-1]),
                "volume_avg_20": float(df["volume"].rolling(20).mean().iloc[-1])
                if "volume" in df.columns
                else 0.0,
            }
        except Exception as exc:
            logger.error(f"Indicator computation error: {exc}")
            return {}


# ── Singleton ──────────────────────────────────────────────────────────────────

_detector: MarketRegimeDetector | None = None


def get_regime_detector() -> MarketRegimeDetector:
    global _detector
    if _detector is None:
        _detector = MarketRegimeDetector()
    return _detector
