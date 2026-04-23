from __future__ import annotations
from datetime import datetime
from typing import Any
from app.models.schemas import MarketRegime, StrategySignal
from app.strategies.engine import BaseStrategy

class SupertrendStrategy(BaseStrategy):
    """
    Supertrend trend following strategy.
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
        period = params.get("period", 10)
        mult = params.get("multiplier", 3.0)

        for symbol in self.config.symbols:
            symbol_data = market_data.get(symbol, {})
            if not symbol_data:
                continue

            st = indicators.get(f"{symbol}_supertrend_{period}_{mult}")
            st_direction = indicators.get(f"{symbol}_supertrend_direction_{period}_{mult}")
            prev_st_direction = indicators.get(f"{symbol}_prev_supertrend_direction_{period}_{mult}")
            close = symbol_data.get("close", 0)

            if st is None or st_direction is None:
                continue

            action = "HOLD"
            confidence = 0.0

            if st_direction == "up" and prev_st_direction == "down":
                action = "BUY"
                confidence = 0.85
            elif st_direction == "down" and prev_st_direction == "up":
                action = "SELL"
                confidence = 0.85

            if action != "HOLD":
                signals.append(
                    StrategySignal(
                        strategy_name=self.name,
                        symbol=symbol,
                        action=action,
                        confidence=round(confidence, 3),
                        metadata={
                            "supertrend": st,
                            "direction": st_direction,
                            "regime": regime.value,
                            "target": "Trailing SL"
                        },
                        timestamp=datetime.utcnow(),
                    )
                )

        return signals
