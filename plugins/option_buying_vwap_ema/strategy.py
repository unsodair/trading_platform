from __future__ import annotations
from datetime import datetime
from typing import Any
from app.models.schemas import MarketRegime, StrategySignal
from app.strategies.engine import BaseStrategy

class VWAPEMA9ScalperStrategy(BaseStrategy):
    """
    Scalping strategy for options: Price > VWAP and Price > 9 EMA for BUY.
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
        ema_p = params.get("ema_period", 9)

        for symbol in self.config.symbols:
            symbol_data = market_data.get(symbol, {})
            if not symbol_data:
                continue

            vwap = indicators.get(f"{symbol}_vwap")
            ema_9 = indicators.get(f"{symbol}_ema_{ema_p}")
            close = symbol_data.get("close", 0)

            if vwap is None or ema_9 is None:
                continue

            action = "HOLD"
            confidence = 0.0

            if close > vwap and close > ema_9:
                action = "BUY"
                confidence = 0.75
            elif close < vwap and close < ema_9:
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
                            "vwap": round(vwap, 2),
                            "ema_9": round(ema_9, 2),
                            "close": close,
                            "rr": "1:2"
                        },
                        timestamp=datetime.utcnow(),
                    )
                )

        return signals
