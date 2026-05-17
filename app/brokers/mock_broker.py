"""
Mock broker adapter — used for paper trading when no broker credentials are provided.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

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
        # Provide a dummy price for paper trading
        return 100.0

    async def get_market_data(
        self, security_id: str, exchange_segment: str
    ) -> dict[str, Any]:
        return {"ltp": 100.0}

