"""
Backtest harness for the SMA Crossover strategy.

Usage:
    python -m plugins.sample_sma_crossover.backtest

Requires a CSV with columns: date, open, high, low, close, volume
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pandas as pd

from app.models.schemas import MarketRegime
from plugins.sample_sma_crossover.strategy import SMACrossoverStrategy
from app.strategies.engine import BaseStrategy
from app.models.schemas import StrategyConfig


async def run_backtest(
    csv_path: str = "data/sample_nifty.csv",
    sma_short: int = 20,
    sma_long: int = 50,
    initial_capital: float = 100_000.0,
) -> dict:
    """
    Run a simple backtest over historical data.

    Returns dict with performance metrics.
    """
    # Load data
    data_file = Path(csv_path)
    if not data_file.exists():
        print(f"Data file not found: {csv_path}")
        print("Create a CSV with columns: date, open, high, low, close, volume")
        return {"error": "Data file not found"}

    df = pd.read_csv(csv_path, parse_dates=["date"])
    df = df.sort_values("date").reset_index(drop=True)

    # Compute SMAs
    df["sma_short"] = df["close"].rolling(sma_short).mean()
    df["sma_long"] = df["close"].rolling(sma_long).mean()
    df["prev_sma_short"] = df["sma_short"].shift(1)
    df["prev_sma_long"] = df["sma_long"].shift(1)

    # Initialize strategy
    strategy = SMACrossoverStrategy()
    strategy.name = "SMA Crossover Backtest"
    strategy.config = StrategyConfig(
        enabled=True,
        symbols=["BACKTEST"],
        parameters={"sma_short": sma_short, "sma_long": sma_long, "min_confidence": 0.3},
    )

    # Simulate
    capital = initial_capital
    position = 0
    entry_price = 0.0
    trades: list[dict] = []

    for i in range(sma_long + 1, len(df)):
        row = df.iloc[i]
        market_data = {
            "BACKTEST": {
                "close": row["close"],
                "sma_short": row["sma_short"],
                "sma_long": row["sma_long"],
                "prev_sma_short": row["prev_sma_short"],
                "prev_sma_long": row["prev_sma_long"],
            }
        }

        signals = await strategy.evaluate(
            market_data=market_data,
            indicators={},
            regime=MarketRegime.RANGE_BOUND,
        )

        for sig in signals:
            if sig.action == "BUY" and position == 0:
                qty = int(capital * 0.95 / row["close"])
                if qty > 0:
                    position = qty
                    entry_price = row["close"]
                    capital -= qty * row["close"]
                    trades.append({
                        "date": str(row["date"]),
                        "action": "BUY",
                        "price": row["close"],
                        "qty": qty,
                    })
            elif sig.action == "SELL" and position > 0:
                capital += position * row["close"]
                pnl = (row["close"] - entry_price) * position
                trades.append({
                    "date": str(row["date"]),
                    "action": "SELL",
                    "price": row["close"],
                    "qty": position,
                    "pnl": round(pnl, 2),
                })
                position = 0

    # Final value
    final_value = capital + position * df.iloc[-1]["close"]
    total_return = ((final_value - initial_capital) / initial_capital) * 100

    results = {
        "initial_capital": initial_capital,
        "final_value": round(final_value, 2),
        "total_return_pct": round(total_return, 2),
        "total_trades": len(trades),
        "trades": trades[-10:],  # last 10 trades
    }

    print(f"\n{'='*50}")
    print(f"SMA Crossover Backtest Results")
    print(f"{'='*50}")
    print(f"Initial Capital:  ₹{initial_capital:,.2f}")
    print(f"Final Value:      ₹{final_value:,.2f}")
    print(f"Total Return:     {total_return:+.2f}%")
    print(f"Total Trades:     {len(trades)}")
    print(f"{'='*50}\n")

    return results


if __name__ == "__main__":
    asyncio.run(run_backtest())
