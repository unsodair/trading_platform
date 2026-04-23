"""
Dhan API broker adapter — wraps the dhanhq SDK + raw HTTP fallbacks.
Implements the full BaseBroker contract.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

import httpx
from dhanhq import dhanhq
from loguru import logger

from app.brokers.base import BaseBroker
from app.config import settings
from app.models.schemas import (
    BrokerStatus,
    ExchangeSegment,
    FundData,
    Holding,
    ModifyOrderRequest,
    OrderDetail,
    OrderRequest,
    OrderResponse,
    OrderSide,
    OrderStatus,
    OrderType,
    Position,
    ProductType,
)


# ── Mapping helpers ────────────────────────────────────────────────────────────

_EXCHANGE_MAP: dict[str, str] = {
    ExchangeSegment.NSE_EQ: dhanhq.NSE,
    ExchangeSegment.BSE_EQ: dhanhq.BSE,
    ExchangeSegment.NSE_FNO: dhanhq.NSE_FNO,
    ExchangeSegment.BSE_FNO: dhanhq.BSE_FNO,
    ExchangeSegment.MCX_COMM: dhanhq.MCX,
}

_ORDER_TYPE_MAP: dict[str, str] = {
    OrderType.MARKET: dhanhq.MARKET,
    OrderType.LIMIT: dhanhq.LIMIT,
    OrderType.SL: dhanhq.SL,
    OrderType.SL_MARKET: dhanhq.SLM,
}

_PRODUCT_MAP: dict[str, str] = {
    ProductType.INTRADAY: dhanhq.INTRA,
    ProductType.DELIVERY: dhanhq.CNC,
    ProductType.MTF: dhanhq.MARGIN,
}

_SIDE_MAP: dict[str, str] = {
    OrderSide.BUY: dhanhq.BUY,
    OrderSide.SELL: dhanhq.SELL,
}


def _run_sync(fn, *args, **kwargs):
    """Run a blocking SDK call in an executor."""
    loop = asyncio.get_event_loop()
    return loop.run_in_executor(None, lambda: fn(*args, **kwargs))


class DhanAdapter(BaseBroker):
    """Production adapter for the Dhan trading API."""

    def __init__(self) -> None:
        self._client: dhanhq | None = None
        self._http = httpx.AsyncClient(
            base_url="https://api.dhan.co/v2",
            headers={
                "access-token": settings.dhan_access_token,
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

    def _ensure_client(self) -> dhanhq:
        if self._client is None:
            self._client = dhanhq(settings.dhan_client_id, settings.dhan_access_token)
        return self._client

    # ── Connection ─────────────────────────────────────────────────────────

    async def connect(self) -> BrokerStatus:
        try:
            client = self._ensure_client()
            funds = await _run_sync(client.get_fund_limits)
            connected = funds.get("status", "") != "error"
            return BrokerStatus(
                connected=connected,
                client_id=settings.dhan_client_id,
                last_checked=datetime.utcnow(),
            )
        except Exception as exc:
            logger.error(f"Dhan connection failed: {exc}")
            return BrokerStatus(
                connected=False,
                client_id=settings.dhan_client_id,
            )

    # ── Holdings ───────────────────────────────────────────────────────────

    async def get_holdings(self) -> list[Holding]:
        try:
            client = self._ensure_client()
            resp = await _run_sync(client.get_holdings)
            data = resp.get("data", []) or []
            return [
                Holding(
                    trading_symbol=h.get("tradingSymbol", ""),
                    exchange=h.get("exchangeSegment", ""),
                    isin=h.get("isin", ""),
                    quantity=h.get("totalQty", 0),
                    avg_price=h.get("avgCostPrice", 0.0),
                    ltp=h.get("lastTradedPrice", 0.0),
                    pnl=h.get("unrealizedProfit", 0.0),
                    current_value=h.get("lastTradedPrice", 0.0) * h.get("totalQty", 0),
                )
                for h in data
            ]
        except Exception as exc:
            logger.error(f"Failed to fetch holdings: {exc}")
            return []

    # ── Positions ──────────────────────────────────────────────────────────

    async def get_positions(self) -> list[Position]:
        try:
            client = self._ensure_client()
            resp = await _run_sync(client.get_positions)
            data = resp.get("data", []) or []
            return [
                Position(
                    trading_symbol=p.get("tradingSymbol", ""),
                    exchange=p.get("exchangeSegment", ""),
                    security_id=str(p.get("securityId", "")),
                    product_type=p.get("productType", ""),
                    quantity=p.get("netQty", 0),
                    avg_price=p.get("costPrice", 0.0),
                    ltp=p.get("lastTradedPrice", 0.0),
                    pnl=p.get("realizedProfit", 0.0) + p.get("unrealizedProfit", 0.0),
                    buy_qty=p.get("buyQty", 0),
                    sell_qty=p.get("sellQty", 0),
                    buy_avg=p.get("dayBuyPrice", 0.0),
                    sell_avg=p.get("daySellPrice", 0.0),
                )
                for p in data
            ]
        except Exception as exc:
            logger.error(f"Failed to fetch positions: {exc}")
            return []

    # ── Funds ──────────────────────────────────────────────────────────────

    async def get_funds(self) -> FundData:
        try:
            client = self._ensure_client()
            resp = await _run_sync(client.get_fund_limits)
            data = resp.get("data", {}) or {}
            return FundData(
                available_balance=float(data.get("availabelBalance", 0)),
                utilized_amount=float(data.get("utilizedAmount", 0)),
                blocked_amount=float(data.get("blockedPayoutAmount", 0)),
                total_balance=float(data.get("sodLimit", 0)),
            )
        except Exception as exc:
            logger.error(f"Failed to fetch funds: {exc}")
            return FundData()

    # ── Orders ─────────────────────────────────────────────────────────────

    async def get_orders(self) -> list[OrderDetail]:
        try:
            client = self._ensure_client()
            resp = await _run_sync(client.get_order_list)
            data = resp.get("data", []) or []
            return [
                OrderDetail(
                    order_id=str(o.get("orderId", "")),
                    trading_symbol=o.get("tradingSymbol", ""),
                    exchange=o.get("exchangeSegment", ""),
                    order_side=o.get("transactionType", ""),
                    order_type=o.get("orderType", ""),
                    product_type=o.get("productType", ""),
                    quantity=o.get("quantity", 0),
                    price=o.get("price", 0.0),
                    trigger_price=o.get("triggerPrice", 0.0),
                    status=o.get("orderStatus", "UNKNOWN"),
                    filled_qty=o.get("filledQty", 0),
                    timestamp=datetime.utcnow(),
                )
                for o in data
            ]
        except Exception as exc:
            logger.error(f"Failed to fetch orders: {exc}")
            return []

    # ── Place Order ────────────────────────────────────────────────────────

    async def place_order(self, order: OrderRequest) -> OrderResponse:
        try:
            client = self._ensure_client()
            resp = await _run_sync(
                client.place_order,
                security_id=order.security_id,
                exchange_segment=_EXCHANGE_MAP.get(
                    order.exchange_segment, dhanhq.NSE
                ),
                transaction_type=_SIDE_MAP.get(order.order_side, dhanhq.BUY),
                quantity=order.quantity,
                order_type=_ORDER_TYPE_MAP.get(order.order_type, dhanhq.MARKET),
                product_type=_PRODUCT_MAP.get(
                    order.product_type, dhanhq.CNC
                ),
                price=order.price,
                trigger_price=order.trigger_price,
                tag=order.tag or "TradingPlatform",
            )
            status = resp.get("status", "")
            order_id = str(resp.get("data", {}).get("orderId", ""))
            return OrderResponse(
                order_id=order_id,
                status=(
                    OrderStatus.PENDING if status == "success" else OrderStatus.REJECTED
                ),
                message=resp.get("remarks", resp.get("message", "")),
                raw_response=resp,
            )
        except Exception as exc:
            logger.error(f"Order placement failed: {exc}")
            return OrderResponse(
                status=OrderStatus.REJECTED,
                message=str(exc),
            )

    # ── Modify Order ───────────────────────────────────────────────────────

    async def modify_order(self, req: ModifyOrderRequest) -> OrderResponse:
        try:
            client = self._ensure_client()
            resp = await _run_sync(
                client.modify_order,
                order_id=req.order_id,
                order_type=_ORDER_TYPE_MAP.get(req.order_type, dhanhq.MARKET),
                quantity=req.quantity,
                price=req.price,
                trigger_price=req.trigger_price,
            )
            return OrderResponse(
                order_id=req.order_id,
                status=OrderStatus.PENDING,
                message=resp.get("remarks", ""),
                raw_response=resp,
            )
        except Exception as exc:
            logger.error(f"Modify order failed: {exc}")
            return OrderResponse(
                order_id=req.order_id,
                status=OrderStatus.REJECTED,
                message=str(exc),
            )

    # ── Cancel Order ───────────────────────────────────────────────────────

    async def cancel_order(self, order_id: str) -> OrderResponse:
        try:
            client = self._ensure_client()
            resp = await _run_sync(client.cancel_order, order_id=order_id)
            return OrderResponse(
                order_id=order_id,
                status=OrderStatus.CANCELLED,
                message=resp.get("remarks", ""),
                raw_response=resp,
            )
        except Exception as exc:
            logger.error(f"Cancel order failed: {exc}")
            return OrderResponse(
                order_id=order_id,
                status=OrderStatus.REJECTED,
                message=str(exc),
            )

    # ── Market Data ────────────────────────────────────────────────────────

    async def get_ltp(self, security_id: str, exchange_segment: str) -> float:
        try:
            client = self._ensure_client()
            seg = _EXCHANGE_MAP.get(exchange_segment, dhanhq.NSE)
            resp = await _run_sync(client.get_market_quote, security_id, seg)
            data = resp.get("data", {}) or {}
            return float(data.get("lastTradedPrice", 0.0))
        except Exception as exc:
            logger.error(f"LTP fetch failed: {exc}")
            return 0.0

    async def get_market_data(
        self, security_id: str, exchange_segment: str
    ) -> dict[str, Any]:
        try:
            resp = await self._http.post(
                "/marketfeed/ltp",
                json={
                    "NSE_EQ": [int(security_id)]
                    if "NSE" in exchange_segment
                    else [],
                    "BSE_EQ": [int(security_id)]
                    if "BSE" in exchange_segment
                    else [],
                },
            )
            return resp.json()
        except Exception as exc:
            logger.error(f"Market data fetch failed: {exc}")
            return {}


# ── Singleton factory ──────────────────────────────────────────────────────────

_dhan_instance: DhanAdapter | None = None


def get_dhan_adapter() -> DhanAdapter:
    global _dhan_instance
    if _dhan_instance is None:
        _dhan_instance = DhanAdapter()
    return _dhan_instance
