"""
SMA Crossover strategy plugin — a classic trend-following strategy.
Generates BUY when short SMA crosses above long SMA, SELL on the reverse.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.models.schemas import MarketRegime, StrategySignal
from app.strategies.engine import BaseStrategy


class SMACrossoverStrategy(BaseStrategy):
    """
    Simple Moving Average crossover.

    Parameters (from config.yaml):
        sma_short  — short SMA period (default 20)
        sma_long   — long SMA period (default 50)
        min_confidence — minimum confidence threshold
    """

    async def evaluate(
        self,
        market_data: dict[str, Any],
        indicators: dict[str, Any],
        regime: MarketRegime,
        positions: list[Any] | None = None,
    ) -> list[StrategySignal]:
        signals: list[StrategySignal] = []

        if not self.config or not self.config.enabled:
            return signals

        params = self.config.parameters
        sma_short_period = params.get("sma_short", 20)
        sma_long_period = params.get("sma_long", 50)
        min_confidence = params.get("min_confidence", 0.6)

        # Iterate over each configured symbol
        for symbol in self.config.symbols:
            symbol_data = market_data.get(symbol, {})
            if not symbol_data:
                continue

            sma_short = symbol_data.get("sma_short") or indicators.get(f"{symbol}_sma_{sma_short_period}")
            sma_long = symbol_data.get("sma_long") or indicators.get(f"{symbol}_sma_{sma_long_period}")
            close = symbol_data.get("close", 0)
            prev_sma_short = symbol_data.get("prev_sma_short", 0)
            prev_sma_long = symbol_data.get("prev_sma_long", 0)

            if not all([sma_short, sma_long, close]):
                continue

            # ── Crossover detection ────────────────────────────────────
            action = "HOLD"
            confidence = 0.0

            # Golden cross — short SMA crosses above long SMA
            if sma_short > sma_long and prev_sma_short <= prev_sma_long:
                action = "BUY"
                confidence = min(0.5 + (sma_short - sma_long) / sma_long, 0.95)

            # Death cross — short SMA crosses below long SMA
            elif sma_short < sma_long and prev_sma_short >= prev_sma_long:
                action = "SELL"
                confidence = min(0.5 + (sma_long - sma_short) / sma_long, 0.95)

            # Regime adjustment
            if regime == MarketRegime.TRENDING_UP and action == "BUY":
                confidence = min(confidence * 1.2, 0.95)
            elif regime == MarketRegime.TRENDING_DOWN and action == "SELL":
                confidence = min(confidence * 1.2, 0.95)
            elif regime == MarketRegime.HIGH_VOLATILITY:
                confidence *= 0.7  # Reduce confidence in volatile markets

            if action != "HOLD" and confidence >= min_confidence:
                signals.append(
                    StrategySignal(
                        strategy_name=self.name,
                        symbol=symbol,
                        action=action,
                        confidence=round(confidence, 3),
                        metadata={
                            "sma_short": sma_short,
                            "sma_long": sma_long,
                            "close": close,
                            "regime": regime.value,
                        },
                        timestamp=datetime.utcnow(),
                    )
                )

        return signals
