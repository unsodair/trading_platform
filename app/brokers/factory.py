"""
Broker factory — provides the correct broker adapter based on settings.
"""

from __future__ import annotations

from app.brokers.base import BaseBroker
from app.config import settings, TradingMode

_broker_instance: BaseBroker | None = None

def get_broker() -> BaseBroker:
    """Return a broker adapter instance (Dhan or Mock)."""
    global _broker_instance
    if _broker_instance is not None:
        return _broker_instance

    # Use MockBroker if we are in PAPER mode AND no broker credentials are provided
    if (
        settings.trading_mode == TradingMode.PAPER
        and not settings.dhan_client_id
        and not settings.dhan_access_token
    ):
        from app.brokers.mock_broker import MockBroker
        _broker_instance = MockBroker()
    else:
        from app.brokers.dhan_adapter import get_dhan_adapter
        _broker_instance = get_dhan_adapter()

    return _broker_instance
