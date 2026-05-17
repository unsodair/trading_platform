"""
Mock broker adapter — used for paper trading when no broker credentials are provided.
"""

from __future__ import annotations

import uuid
import asyncio
from datetime import datetime, timezone
from typing import Any
from loguru import logger

from app.brokers.base import BaseBroker
from app.models.schemas import (
    BrokerStatus,
    FundData,
    Holding,
    ModifyOrderRequest,
    OrderDetail,
    OrderRequest,
    OrderResponse,
    OrderStatus,
    Position,
)


class MockBroker(BaseBroker):
    """A mock broker that fakes responses for paper trading without an account."""

    async def connect(self) -> BrokerStatus:
        return BrokerStatus(
            connected=True,
            broker_name="MockBroker (Paper)",
            client_id="paper_user",
            last_checked=datetime.now(timezone.utc),
        )

    async def get_holdings(self) -> list[Holding]:
        return []

    async def get_positions(self) -> list[Position]:
        return []

    async def get_funds(self) -> FundData:
        return FundData(
            available_balance=1000000.0,
            utilized_amount=0.0,
            blocked_amount=0.0,
            total_balance=1000000.0,
        )

    async def get_orders(self) -> list[OrderDetail]:
        return []

    async def place_order(self, order: OrderRequest) -> OrderResponse:
        return OrderResponse(
            order_id=f"MOCK-{uuid.uuid4().hex[:8].upper()}",
            status=OrderStatus.FILLED,
            message="Mock order placed",
        )

    async def modify_order(self, req: ModifyOrderRequest) -> OrderResponse:
        return OrderResponse(
            order_id=req.order_id,
            status=OrderStatus.FILLED,
            message="Mock order modified",
        )

    async def cancel_order(self, order_id: str) -> OrderResponse:
        return OrderResponse(
            order_id=order_id,
            status=OrderStatus.CANCELLED,
            message="Mock order cancelled",
        )

    async def get_ltp(self, security_id: str, exchange_segment: str) -> float:
        """Fetch live price using public APIs based on the exchange segment."""
        try:
            if exchange_segment == "CRYPTO":
                import ccxt
                # Example: security_id="BTC/USDT"
                # Using binance as a generic source for crypto prices
                exchange = ccxt.binance()
                loop = asyncio.get_event_loop()
                ticker = await loop.run_in_executor(None, exchange.fetch_ticker, security_id.upper())
                return float(ticker['last'])
            
            elif exchange_segment == "US_EQ":
                import yfinance as yf
                # Example: security_id="AAPL"
                loop = asyncio.get_event_loop()
                ticker = yf.Ticker(security_id.upper())
                # Use fast_info to get the last price quickly
                info = await loop.run_in_executor(None, getattr, ticker, 'fast_info')
                return float(info.last_price)
            
            else:
                # For Indian Stocks (NSE/BSE), we can also use yfinance (e.g. RELIANCE.NS)
                import yfinance as yf
                symbol = security_id.upper()
                if not symbol.endswith(".NS") and not symbol.endswith(".BO"):
                    symbol = f"{symbol}.NS"
                loop = asyncio.get_event_loop()
                ticker = yf.Ticker(symbol)
                info = await loop.run_in_executor(None, getattr, ticker, 'fast_info')
                return float(info.last_price)
                
        except Exception as exc:
            logger.error(f"MockBroker LTP fetch failed for {security_id}: {exc}")
            return 100.0  # Fallback dummy price

    async def get_market_data(
        self, security_id: str, exchange_segment: str
    ) -> dict[str, Any]:
        ltp = await self.get_ltp(security_id, exchange_segment)
        return {"ltp": ltp}

