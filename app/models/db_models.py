"""
SQLAlchemy ORM models — persistent storage for audit logs, strategy state,
paper trades, and discovered strategies.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
)

from app.database import Base


class AuditLog(Base):
    """Every LLM decision and broker interaction is logged here."""

    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    raw_llm_output = Column(Text, default="")
    parsed_decision = Column(JSON, default=dict)
    strategy_used = Column(String(128), default="", index=True)
    market_regime = Column(String(64), default="")
    order_request = Column(JSON, default=dict)
    broker_response = Column(JSON, default=dict)
    risk_check = Column(JSON, default=dict)
    trading_mode = Column(String(16), default="paper")
    notes = Column(Text, default="")


class PaperTrade(Base):
    """Simulated order fills for paper trading."""

    __tablename__ = "paper_trades"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(String(64), unique=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    trading_symbol = Column(String(64), index=True)
    exchange = Column(String(16))
    side = Column(String(8))
    order_type = Column(String(16))
    product_type = Column(String(16))
    quantity = Column(Integer)
    price = Column(Float)
    trigger_price = Column(Float, default=0.0)
    status = Column(String(32), default="FILLED")
    pnl = Column(Float, default=0.0)
    strategy = Column(String(128), default="")


class PaperPosition(Base):
    """Current paper-trading positions."""

    __tablename__ = "paper_positions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    trading_symbol = Column(String(64), index=True, unique=True)
    exchange = Column(String(16))
    quantity = Column(Integer, default=0)
    avg_price = Column(Float, default=0.0)
    side = Column(String(8), default="BUY")
    strategy = Column(String(128), default="")
    opened_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DiscoveredStrategy(Base):
    """GitHub-discovered strategy candidates."""

    __tablename__ = "discovered_strategies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    repo_url = Column(String(512), unique=True)
    repo_name = Column(String(256))
    description = Column(Text, default="")
    stars = Column(Integer, default=0)
    language = Column(String(32), default="")
    topics = Column(JSON, default=list)
    relevance_score = Column(Float, default=0.0)
    indian_market_compatible = Column(Boolean, default=False)
    status = Column(String(32), default="candidate")
    discovered_at = Column(DateTime, default=datetime.utcnow)
    review_notes = Column(Text, default="")
    extracted_metadata = Column(JSON, default=dict)


class DailyPnL(Base):
    """Track daily P&L for risk management."""

    __tablename__ = "daily_pnl"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(String(10), unique=True, index=True)
    realized_pnl = Column(Float, default=0.0)
    unrealized_pnl = Column(Float, default=0.0)
    total_trades = Column(Integer, default=0)
    trading_mode = Column(String(16), default="paper")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
