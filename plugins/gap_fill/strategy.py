from __future__ import annotations
from datetime import datetime
from typing import Any
from app.models.schemas import MarketRegime, StrategySignal
from app.strategies.engine import BaseStrategy

class GapFillStrategy(BaseStrategy):
    """
    Strategy that looks for gap fills.
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

            prev_close = indicators.get(f"{symbol}_prev_close")
            open_price = symbol_data.get("open", 0)
            close = symbol_data.get("close", 0)

            if not prev_close or not open_price:
                continue

            action = "HOLD"
            confidence = 0.0

            # Gap Up: Open > Prev Close
            if open_price > prev_close * 1.005:
                # If price starts moving down towards prev_close
                if close < open_price:
                    action = "SELL"
                    confidence = 0.7
            # Gap Down: Open < Prev Close
            elif open_price < prev_close * 0.995:
                # If price starts moving up towards prev_close
                if close > open_price:
                    action = "BUY"
                    confidence = 0.7

            if action != "HOLD":
                signals.append(
                    StrategySignal(
                        strategy_name=self.name,
                        symbol=symbol,
                        action=action,
                        confidence=round(confidence, 3),
                        metadata={
                            "prev_close": prev_close,
                            "open": open_price,
                            "target": prev_close
                        },
                        timestamp=datetime.utcnow(),
                    )
                )

        return signals
