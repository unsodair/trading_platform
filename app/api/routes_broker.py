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


# ── Default watchlists per market ──────────────────────────────
_DEFAULT_WATCHLISTS: dict[str, list[dict]] = {
    "NSE_EQ": [
        {"symbol": "RELIANCE", "name": "Reliance Industries"},
        {"symbol": "TCS", "name": "Tata Consultancy"},
        {"symbol": "HDFCBANK", "name": "HDFC Bank"},
        {"symbol": "INFY", "name": "Infosys"},
        {"symbol": "ICICIBANK", "name": "ICICI Bank"},
        {"symbol": "BHARTIARTL", "name": "Bharti Airtel"},
        {"symbol": "ITC", "name": "ITC Ltd"},
        {"symbol": "SBIN", "name": "State Bank of India"},
    ],
    "CRYPTO": [
        {"symbol": "BTC/USDT", "name": "Bitcoin"},
        {"symbol": "ETH/USDT", "name": "Ethereum"},
        {"symbol": "SOL/USDT", "name": "Solana"},
        {"symbol": "BNB/USDT", "name": "BNB"},
        {"symbol": "XRP/USDT", "name": "Ripple"},
        {"symbol": "DOGE/USDT", "name": "Dogecoin"},
        {"symbol": "ADA/USDT", "name": "Cardano"},
        {"symbol": "AVAX/USDT", "name": "Avalanche"},
    ],
    "US_EQ": [
        {"symbol": "AAPL", "name": "Apple Inc."},
        {"symbol": "MSFT", "name": "Microsoft"},
        {"symbol": "GOOGL", "name": "Alphabet"},
        {"symbol": "AMZN", "name": "Amazon"},
        {"symbol": "NVDA", "name": "NVIDIA"},
        {"symbol": "TSLA", "name": "Tesla"},
        {"symbol": "META", "name": "Meta Platforms"},
        {"symbol": "JPM", "name": "JPMorgan Chase"},
    ],
    "GLOBAL_EQ": [
        {"symbol": "VOD.L", "name": "Vodafone Group (UK)"},
        {"symbol": "SAP.DE", "name": "SAP SE (Germany)"},
        {"symbol": "7203.T", "name": "Toyota Motor (Japan)"},
        {"symbol": "0700.HK", "name": "Tencent Holdings (HK)"},
        {"symbol": "BHP.AX", "name": "BHP Group (Australia)"},
        {"symbol": "PETR4.SA", "name": "Petrobras SA (Brazil)"},
        {"symbol": "RY.TO", "name": "Royal Bank of Canada"},
        {"symbol": "ASML.AS", "name": "ASML Holding (Netherlands)"},
    ],
}


@router.get("/watchlist")
async def get_watchlist(market: str = "NSE_EQ"):
    """Return live prices for the default watchlist of the selected market."""
    adapter = get_broker()
    items = _DEFAULT_WATCHLISTS.get(market, _DEFAULT_WATCHLISTS["NSE_EQ"])
    results = []
    for item in items:
        try:
            price = await adapter.get_ltp(item["symbol"], market)
        except Exception:
            price = 0.0
        results.append({
            "symbol": item["symbol"],
            "name": item["name"],
            "ltp": price,
            "exchange": market,
        })
    return {"market": market, "watchlist": results}
