"""
Pydantic schemas — the single source of truth for all request/response shapes.
Every LLM decision, broker interaction, and API payload is modeled here.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ─── Enums ─────────────────────────────────────────────────────────────────────

class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    SL = "SL"
    SL_MARKET = "SL_MARKET"


class ProductType(str, Enum):
    INTRADAY = "INTRADAY"
    DELIVERY = "DELIVERY"
    MTF = "MTF"


class ExchangeSegment(str, Enum):
    NSE_EQ = "NSE_EQ"
    BSE_EQ = "BSE_EQ"
    NSE_FNO = "NSE_FNO"
    BSE_FNO = "BSE_FNO"
    MCX_COMM = "MCX_COMM"


class OrderStatus(str, Enum):
    PENDING = "PENDING"
    OPEN = "OPEN"
    FILLED = "FILLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class MarketRegime(str, Enum):
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGE_BOUND = "range_bound"
    HIGH_VOLATILITY = "high_volatility"
    EVENT_RISK = "event_risk"


class TradingMode(str, Enum):
    PAPER = "paper"
    LIVE = "live"


class StrategyStatus(str, Enum):
    CANDIDATE = "candidate"
    REVIEWED = "reviewed"
    APPROVED = "approved"
    ACTIVE = "active"
    DISABLED = "disabled"


# ─── Broker Schemas ────────────────────────────────────────────────────────────

class BrokerStatus(BaseModel):
    connected: bool
    broker_name: str = "Dhan"
    client_id: str = ""
    last_checked: datetime = Field(default_factory=datetime.utcnow)


class Holding(BaseModel):
    trading_symbol: str
    exchange: str
    isin: str = ""
    quantity: int
    avg_price: float
    ltp: float = 0.0
    pnl: float = 0.0
    current_value: float = 0.0


class Position(BaseModel):
    trading_symbol: str
    exchange: str
    security_id: str = ""
    product_type: str = ""
    quantity: int
    avg_price: float
    ltp: float = 0.0
    pnl: float = 0.0
    buy_qty: int = 0
    sell_qty: int = 0
    buy_avg: float = 0.0
    sell_avg: float = 0.0


class FundData(BaseModel):
    available_balance: float = 0.0
    utilized_amount: float = 0.0
    blocked_amount: float = 0.0
    total_balance: float = 0.0


class OrderRequest(BaseModel):
    trading_symbol: str
    exchange_segment: ExchangeSegment
    security_id: str
    order_side: OrderSide
    order_type: OrderType
    product_type: ProductType
    quantity: int
    price: float = 0.0
    trigger_price: float = 0.0
    stoploss_price: Optional[float] = None
    tag: str = ""


class OrderResponse(BaseModel):
    order_id: str = ""
    status: OrderStatus = OrderStatus.PENDING
    message: str = ""
    raw_response: dict[str, Any] = Field(default_factory=dict)


class OrderDetail(BaseModel):
    order_id: str
    trading_symbol: str
    exchange: str
    order_side: str
    order_type: str
    product_type: str
    quantity: int
    price: float
    trigger_price: float = 0.0
    status: str
    filled_qty: int = 0
    timestamp: Optional[datetime] = None


class ModifyOrderRequest(BaseModel):
    order_id: str
    order_type: OrderType
    quantity: int
    price: float = 0.0
    trigger_price: float = 0.0


# ─── LLM Decision Schemas ─────────────────────────────────────────────────────

class LLMDecision(BaseModel):
    """Strict JSON structure that every LLM adapter must return."""
    action: str = Field(
        ..., description="BUY | SELL | HOLD | CLOSE | NO_ACTION"
    )
    symbol: str = ""
    confidence: float = Field(
        0.0, ge=0.0, le=1.0,
        description="Confidence score 0-1",
    )
    reasoning: str = ""
    stop_loss: Optional[float] = None
    target_price: Optional[float] = None
    quantity: Optional[int] = None
    order_type: str = "MARKET"
    urgency: str = Field("low", description="low | medium | high")
    raw_output: str = Field("", description="Raw LLM text for audit")


class LLMQuery(BaseModel):
    """Input context sent to the LLM for decision-making."""
    strategy_name: str
    market_regime: MarketRegime
    current_positions: list[Position] = Field(default_factory=list)
    holdings: list[Holding] = Field(default_factory=list)
    market_data: dict[str, Any] = Field(default_factory=dict)
    indicators: dict[str, Any] = Field(default_factory=dict)
    news_context: str = ""
    custom_prompt: str = ""


# ─── Strategy Schemas ──────────────────────────────────────────────────────────

class StrategyMetadata(BaseModel):
    name: str
    version: str = "1.0.0"
    author: str = ""
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    supported_exchanges: list[str] = Field(default_factory=lambda: ["NSE_EQ"])
    timeframe: str = "1d"
    status: StrategyStatus = StrategyStatus.CANDIDATE


class StrategyConfig(BaseModel):
    enabled: bool = False
    symbols: list[str] = Field(default_factory=list)
    parameters: dict[str, Any] = Field(default_factory=dict)
    risk_overrides: dict[str, Any] = Field(default_factory=dict)


class StrategySignal(BaseModel):
    strategy_name: str
    symbol: str
    action: str  # BUY | SELL | HOLD
    confidence: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ─── Discovery Schemas ─────────────────────────────────────────────────────────

class CandidateStrategy(BaseModel):
    repo_url: str
    repo_name: str
    description: str = ""
    stars: int = 0
    language: str = ""
    topics: list[str] = Field(default_factory=list)
    relevance_score: float = 0.0
    indian_market_compatible: bool = False
    status: StrategyStatus = StrategyStatus.CANDIDATE
    discovered_at: datetime = Field(default_factory=datetime.utcnow)
    review_notes: str = ""


# ─── Risk Schemas ──────────────────────────────────────────────────────────────

class RiskCheckResult(BaseModel):
    passed: bool
    violations: list[str] = Field(default_factory=list)
    checks_performed: list[str] = Field(default_factory=list)


# ─── Audit Schemas ─────────────────────────────────────────────────────────────

class AuditEntry(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    raw_llm_output: str = ""
    parsed_decision: dict[str, Any] = Field(default_factory=dict)
    strategy_used: str = ""
    market_regime: str = ""
    order_request: dict[str, Any] = Field(default_factory=dict)
    broker_response: dict[str, Any] = Field(default_factory=dict)
    risk_check: dict[str, Any] = Field(default_factory=dict)
    trading_mode: str = "paper"
    notes: str = ""


# ─── Dashboard Schemas ────────────────────────────────────────────────────────

class DashboardState(BaseModel):
    broker_status: BrokerStatus
    trading_mode: TradingMode = TradingMode.PAPER
    market_regime: MarketRegime = MarketRegime.RANGE_BOUND
    positions: list[Position] = Field(default_factory=list)
    holdings: list[Holding] = Field(default_factory=list)
    active_strategies: list[StrategyMetadata] = Field(default_factory=list)
    candidate_strategies: list[CandidateStrategy] = Field(default_factory=list)
    todays_pnl: float = 0.0
    funds: FundData = Field(default_factory=FundData)
    recent_orders: list[OrderDetail] = Field(default_factory=list)
