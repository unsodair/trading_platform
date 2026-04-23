from __future__ import annotations
from datetime import datetime
from typing import Any
from app.models.schemas import MarketRegime, StrategySignal
from app.strategies.engine import BaseStrategy

class CandlestickPatternsStrategy(BaseStrategy):
    """
    Identifies Hammer, Shooting Star, and Engulfing patterns.
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

        for symbol in self.config.symbols:
            symbol_data = market_data.get(symbol, {})
            if not symbol_data:
                continue

            pattern = indicators.get(f"{symbol}_pattern")
            close = symbol_data.get("close", 0)

            if not pattern:
                continue

            action = "HOLD"
            confidence = 0.0

            if pattern in ["HAMMER", "BULLISH_ENGULFING"]:
                action = "BUY"
                confidence = 0.75
            elif pattern in ["SHOOTING_STAR", "BEARISH_ENGULFING"]:
                action = "SELL"
                confidence = 0.75

            if action != "HOLD":
                signals.append(
                    StrategySignal(
                        strategy_name=self.name,
                        symbol=symbol,
                        action=action,
                        confidence=round(confidence, 3),
                        metadata={
                            "pattern": pattern,
                            "close": close,
                            "rr": "1:3"
                        },
                        timestamp=datetime.utcnow(),
                    )
                )

        return signals
