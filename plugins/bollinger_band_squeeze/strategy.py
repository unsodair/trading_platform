from __future__ import annotations
from datetime import datetime
from typing import Any
from app.models.schemas import MarketRegime, StrategySignal
from app.strategies.engine import BaseStrategy

class BollingerBandSqueezeStrategy(BaseStrategy):
    """
    Volatility breakout: Entry when BB expands after a squeeze.
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
        threshold = params.get("squeeze_threshold", 0.05)

        for symbol in self.config.symbols:
            symbol_data = market_data.get(symbol, {})
            if not symbol_data:
                continue

            upper = indicators.get(f"{symbol}_bb_upper")
            lower = indicators.get(f"{symbol}_bb_lower")
            middle = indicators.get(f"{symbol}_bb_middle")
            prev_upper = indicators.get(f"{symbol}_prev_bb_upper")
            prev_lower = indicators.get(f"{symbol}_prev_bb_lower")
            close = symbol_data.get("close", 0)

            if not all([upper, lower, middle, prev_upper, prev_lower]):
                continue

            bandwidth = (upper - lower) / middle
            prev_bandwidth = (prev_upper - prev_lower) / middle

            action = "HOLD"
            confidence = 0.0

            # Squeeze: Bandwidth < Threshold
            # Breakout: Current Bandwidth > Prev Bandwidth and Price breaks Upper/Lower
            if prev_bandwidth < threshold:
                if close > upper and bandwidth > prev_bandwidth:
                    action = "BUY"
                    confidence = 0.8
                elif close < lower and bandwidth > prev_bandwidth:
                    action = "SELL"
                    confidence = 0.8

            if action != "HOLD":
                signals.append(
                    StrategySignal(
                        strategy_name=self.name,
                        symbol=symbol,
                        action=action,
                        confidence=round(confidence, 3),
                        metadata={
                            "bandwidth": round(bandwidth, 4),
                            "prev_bandwidth": round(prev_bandwidth, 4),
                            "rr": "1:4"
                        },
                        timestamp=datetime.utcnow(),
                    )
                )

        return signals
