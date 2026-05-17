"""
Broker API routes — holdings, positions, funds, orders, market data.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.brokers.factory import get_broker
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

router = APIRouter(prefix="/api/broker", tags=["Broker"])


@router.get("/status", response_model=BrokerStatus)
async def broker_status():
    """Check broker connectivity."""
    adapter = get_broker()
    return await adapter.connect()


@router.get("/holdings", response_model=list[Holding])
async def get_holdings():
    adapter = get_broker()
    return await adapter.get_holdings()


@router.get("/positions", response_model=list[Position])
async def get_positions():
    adapter = get_broker()
    return await adapter.get_positions()


@router.get("/funds", response_model=FundData)
async def get_funds():
    adapter = get_broker()
    return await adapter.get_funds()


@router.get("/orders", response_model=list[OrderDetail])
async def get_orders():
    adapter = get_broker()
    return await adapter.get_orders()


@router.post("/order", response_model=OrderResponse)
async def place_order(order: OrderRequest):
    """Place an order through the broker (live mode only for real broker)."""
    adapter = get_broker()
    return await adapter.place_order(order)


@router.put("/order", response_model=OrderResponse)
async def modify_order(req: ModifyOrderRequest):
    adapter = get_broker()
    return await adapter.modify_order(req)


@router.delete("/order/{order_id}", response_model=OrderResponse)
async def cancel_order(order_id: str):
    adapter = get_broker()
    return await adapter.cancel_order(order_id)


@router.get("/ltp/{security_id}")
async def get_ltp(security_id: str, exchange: str = "NSE_EQ"):
    adapter = get_broker()
    price = await adapter.get_ltp(security_id, exchange)
    return {"security_id": security_id, "exchange": exchange, "ltp": price}
