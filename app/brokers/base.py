"""
Abstract broker interface — every broker adapter must implement this.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.models.schemas import (
    BrokerStatus,
    FundData,
    Holding,
    ModifyOrderRequest,
    OrderDetail,
    OrderRequest,
    OrderResponse,
    Position,
)


class BaseBroker(ABC):
    """Contract that all broker adapters must fulfil."""

    @abstractmethod
    async def connect(self) -> BrokerStatus:
        """Authenticate and verify connectivity."""
        ...

    @abstractmethod
    async def get_holdings(self) -> list[Holding]:
        ...

    @abstractmethod
    async def get_positions(self) -> list[Position]:
        ...

    @abstractmethod
    async def get_funds(self) -> FundData:
        ...

    @abstractmethod
    async def get_orders(self) -> list[OrderDetail]:
        ...

    @abstractmethod
    async def place_order(self, order: OrderRequest) -> OrderResponse:
        ...

    @abstractmethod
    async def modify_order(self, req: ModifyOrderRequest) -> OrderResponse:
        ...

    @abstractmethod
    async def cancel_order(self, order_id: str) -> OrderResponse:
        ...

    @abstractmethod
    async def get_ltp(self, security_id: str, exchange_segment: str) -> float:
        """Fetch last traded price for a security."""
        ...

    @abstractmethod
    async def get_market_data(
        self, security_id: str, exchange_segment: str
    ) -> dict[str, Any]:
        """Fetch extended market data (OHLCV, etc.)."""
        ...
