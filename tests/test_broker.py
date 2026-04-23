"""
Tests for broker adapters.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.schemas import (
    ExchangeSegment,
    OrderRequest,
    OrderSide,
    OrderType,
    ProductType,
)


class TestDhanAdapterUnit:
    """Unit tests for the Dhan adapter (mocked SDK)."""

    @pytest.fixture
    def adapter(self):
        from app.brokers.dhan_adapter import DhanAdapter
        return DhanAdapter()

    @pytest.mark.asyncio
    async def test_connect_returns_broker_status(self, adapter):
        """connect() should return a BrokerStatus object."""
        with patch.object(adapter, "_ensure_client") as mock_client:
            mock_dhan = MagicMock()
            mock_dhan.get_fund_limits.return_value = {"status": "success", "data": {}}
            mock_client.return_value = mock_dhan

            status = await adapter.connect()
            assert status.broker_name == "Dhan"

    @pytest.mark.asyncio
    async def test_get_holdings_empty(self, adapter):
        """get_holdings() with empty response returns empty list."""
        with patch.object(adapter, "_ensure_client") as mock_client:
            mock_dhan = MagicMock()
            mock_dhan.get_holdings.return_value = {"data": []}
            mock_client.return_value = mock_dhan

            holdings = await adapter.get_holdings()
            assert isinstance(holdings, list)
            assert len(holdings) == 0

    @pytest.mark.asyncio
    async def test_get_positions_empty(self, adapter):
        with patch.object(adapter, "_ensure_client") as mock_client:
            mock_dhan = MagicMock()
            mock_dhan.get_positions.return_value = {"data": []}
            mock_client.return_value = mock_dhan

            positions = await adapter.get_positions()
            assert isinstance(positions, list)

    @pytest.mark.asyncio
    async def test_get_funds(self, adapter):
        with patch.object(adapter, "_ensure_client") as mock_client:
            mock_dhan = MagicMock()
            mock_dhan.get_fund_limits.return_value = {
                "data": {
                    "availabelBalance": 50000.0,
                    "utilizedAmount": 10000.0,
                    "blockedPayoutAmount": 0,
                    "sodLimit": 60000.0,
                }
            }
            mock_client.return_value = mock_dhan

            funds = await adapter.get_funds()
            assert funds.available_balance == 50000.0
            assert funds.total_balance == 60000.0

    def test_order_request_schema(self):
        """Verify OrderRequest schema works correctly."""
        req = OrderRequest(
            trading_symbol="RELIANCE",
            exchange_segment=ExchangeSegment.NSE_EQ,
            security_id="2885",
            order_side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            product_type=ProductType.INTRADAY,
            quantity=10,
            price=0,
        )
        assert req.trading_symbol == "RELIANCE"
        assert req.order_side == OrderSide.BUY
