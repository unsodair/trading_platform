from __future__ import annotations
from datetime import datetime
from typing import Any
from app.models.schemas import MarketRegime, StrategySignal
from app.strategies.engine import BaseStrategy

class GoldenCrossStrategy(BaseStrategy):
    """
    Golden Cross strategy (EMA 50 and 200).
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

            ema50 = indicators.get(f"{symbol}_ema_50")
            ema200 = indicators.get(f"{symbol}_ema_200")
            prev_ema50 = indicators.get(f"{symbol}_prev_ema_50")
            prev_ema200 = indicators.get(f"{symbol}_prev_ema_200")

            if not all([ema50, ema200, prev_ema50, prev_ema200]):
                continue

            action = "HOLD"
            confidence = 0.0

            if ema50 > ema200 and prev_ema50 <= prev_ema200:
                action = "BUY"
                confidence = 0.9
            elif ema50 < ema200 and prev_ema50 >= prev_ema200:
                action = "SELL"
                confidence = 0.9

            if action != "HOLD":
                signals.append(
                    StrategySignal(
                        strategy_name=self.name,
                        symbol=symbol,
                        action=action,
                        confidence=round(confidence, 3),
                        metadata={
                            "ema_50": round(ema50, 2),
                            "ema_200": round(ema200, 2),
                            "rr": "1:10"
                        },
                        timestamp=datetime.utcnow(),
                    )
                )

        return signals
