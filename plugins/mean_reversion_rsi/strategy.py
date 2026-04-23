from __future__ import annotations
from datetime import datetime
from typing import Any
from app.models.schemas import MarketRegime, StrategySignal
from app.strategies.engine import BaseStrategy

class MeanReversionRSIStrategy(BaseStrategy):
    """
    Mean Reversion strategy using RSI.
    Buy when RSI < 30 (oversold), Sell when RSI > 70 (overbought).
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
        rsi_period = params.get("rsi_period", 14)
        rsi_oversold = params.get("rsi_oversold", 30)
        rsi_overbought = params.get("rsi_overbought", 70)
        min_confidence = params.get("min_confidence", 0.6)

        for symbol in self.config.symbols:
            symbol_data = market_data.get(symbol, {})
            if not symbol_data:
                continue

            rsi = indicators.get(f"{symbol}_rsi_{rsi_period}")
            close = symbol_data.get("close", 0)

            if rsi is None:
                continue

            action = "HOLD"
            confidence = 0.0

            if rsi < rsi_oversold:
                action = "BUY"
                confidence = min(0.5 + (rsi_oversold - rsi) / rsi_oversold, 0.95)
            elif rsi > rsi_overbought:
                action = "SELL"
                confidence = min(0.5 + (rsi - rsi_overbought) / (100 - rsi_overbought), 0.95)

            # Regime filters
            if regime == MarketRegime.RANGING:
                confidence = min(confidence * 1.2, 0.95)
            elif regime in [MarketRegime.TRENDING_UP, MarketRegime.TRENDING_DOWN]:
                confidence *= 0.8  # Less effective in strong trends

            if action != "HOLD" and confidence >= min_confidence:
                signals.append(
                    StrategySignal(
                        strategy_name=self.name,
                        symbol=symbol,
                        action=action,
                        confidence=round(confidence, 3),
                        metadata={
                            "rsi": round(rsi, 2),
                            "close": close,
                            "regime": regime.value,
                            "target": "1:3 RR"
                        },
                        timestamp=datetime.utcnow(),
                    )
                )

        return signals
