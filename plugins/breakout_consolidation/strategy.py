from __future__ import annotations
from datetime import datetime
from typing import Any
from app.models.schemas import MarketRegime, StrategySignal
from app.strategies.engine import BaseStrategy

class BreakoutStrategy(BaseStrategy):
    """
    Identifies breakouts from recent high/low with volume confirmation.
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
        lookback = params.get("lookback_period", 20)
        vol_factor = params.get("volume_factor", 1.5)

        for symbol in self.config.symbols:
            symbol_data = market_data.get(symbol, {})
            if not symbol_data:
                continue

            high_20 = indicators.get(f"{symbol}_high_{lookback}")
            low_20 = indicators.get(f"{symbol}_low_{lookback}")
            avg_vol = indicators.get(f"{symbol}_avg_volume_{lookback}")
            curr_vol = symbol_data.get("volume", 0)
            close = symbol_data.get("close", 0)

            if not all([high_20, low_20, avg_vol]):
                continue

            action = "HOLD"
            confidence = 0.0

            if close > high_20 and curr_vol > avg_vol * vol_factor:
                action = "BUY"
                confidence = 0.8
            elif close < low_20 and curr_vol > avg_vol * vol_factor:
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
                            "high": high_20,
                            "low": low_20,
                            "volume": curr_vol,
                            "avg_volume": avg_vol,
                            "rr": "1:4"
                        },
                        timestamp=datetime.utcnow(),
                    )
                )

        return signals
