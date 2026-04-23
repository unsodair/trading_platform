from __future__ import annotations
from datetime import datetime
from typing import Any
from app.models.schemas import MarketRegime, StrategySignal
from app.strategies.engine import BaseStrategy

class PivotPointsStrategy(BaseStrategy):
    """
    Pivot Points strategy: Buy at S1/S2 bounce, Sell at R1/R2 bounce.
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

            p = indicators.get(f"{symbol}_pivot")
            s1 = indicators.get(f"{symbol}_s1")
            r1 = indicators.get(f"{symbol}_r1")
            close = symbol_data.get("close", 0)
            low = symbol_data.get("low", 0)
            high = symbol_data.get("high", 0)

            if not all([p, s1, r1]):
                continue

            action = "HOLD"
            confidence = 0.0

            # Bounce from S1
            if low <= s1 * 1.001 and close > s1:
                action = "BUY"
                confidence = 0.7
            # Bounce from R1
            elif high >= r1 * 0.999 and close < r1:
                action = "SELL"
                confidence = 0.7

            if action != "HOLD":
                signals.append(
                    StrategySignal(
                        strategy_name=self.name,
                        symbol=symbol,
                        action=action,
                        confidence=round(confidence, 3),
                        metadata={
                            "pivot": p,
                            "s1": s1,
                            "r1": r1,
                            "target": "Next Pivot Level"
                        },
                        timestamp=datetime.utcnow(),
                    )
                )

        return signals
