from __future__ import annotations
from datetime import datetime
from typing import Any
from app.models.schemas import MarketRegime, StrategySignal
from app.strategies.engine import BaseStrategy

class EMAScalpingStrategy(BaseStrategy):
    """
    Scalping strategy based on 9 and 15 EMA crossover.
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
        ema_fast_p = params.get("ema_fast", 9)
        ema_slow_p = params.get("ema_slow", 15)
        min_conf = params.get("min_confidence", 0.5)

        for symbol in self.config.symbols:
            symbol_data = market_data.get(symbol, {})
            if not symbol_data:
                continue

            ema_fast = indicators.get(f"{symbol}_ema_{ema_fast_p}")
            ema_slow = indicators.get(f"{symbol}_ema_{ema_slow_p}")
            prev_ema_fast = symbol_data.get(f"prev_ema_{ema_fast_p}") or indicators.get(f"{symbol}_prev_ema_{ema_fast_p}")
            prev_ema_slow = symbol_data.get(f"prev_ema_{ema_slow_p}") or indicators.get(f"{symbol}_prev_ema_{ema_slow_p}")

            if not all([ema_fast, ema_slow, prev_ema_fast, prev_ema_slow]):
                continue

            action = "HOLD"
            confidence = 0.0

            # Crossover check
            if ema_fast > ema_slow and prev_ema_fast <= prev_ema_slow:
                action = "BUY"
                confidence = 0.7
            elif ema_fast < ema_slow and prev_ema_fast >= prev_ema_slow:
                action = "SELL"
                confidence = 0.7

            # Scalping is best in trending markets
            if regime in [MarketRegime.TRENDING_UP, MarketRegime.TRENDING_DOWN]:
                confidence = min(confidence * 1.1, 0.95)

            if action != "HOLD" and confidence >= min_conf:
                signals.append(
                    StrategySignal(
                        strategy_name=self.name,
                        symbol=symbol,
                        action=action,
                        confidence=round(confidence, 3),
                        metadata={
                            "ema_9": ema_fast,
                            "ema_15": ema_slow,
                            "regime": regime.value,
                            "target": params.get("target_points"),
                            "stop_loss": params.get("stop_loss_points")
                        },
                        timestamp=datetime.utcnow(),
                    )
                )

        return signals
