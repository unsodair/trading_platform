"""
Audit logger — persists every trading decision for compliance and debugging.
Stores: raw LLM output, parsed decision, strategy name, market regime,
order request, broker response, risk-check result, and trading mode.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db_models import AuditLog


class AuditLogger:
    """Writes structured audit entries to the database."""

    async def log(
        self,
        *,
        raw_llm_output: str = "",
        parsed_decision: dict[str, Any] | None = None,
        strategy_used: str = "",
        market_regime: str = "",
        order_request: dict[str, Any] | None = None,
        broker_response: dict[str, Any] | None = None,
        risk_check: dict[str, Any] | None = None,
        trading_mode: str = "paper",
        notes: str = "",
        db: AsyncSession | None = None,
    ) -> int | None:
        """
        Create an audit log entry.

        Returns the audit log ID, or None if no db session provided.
        """
        entry = AuditLog(
            timestamp=datetime.utcnow(),
            raw_llm_output=raw_llm_output,
            parsed_decision=parsed_decision or {},
            strategy_used=strategy_used,
            market_regime=market_regime,
            order_request=order_request or {},
            broker_response=broker_response or {},
            risk_check=risk_check or {},
            trading_mode=trading_mode,
            notes=notes,
        )

        if db is not None:
            db.add(entry)
            await db.flush()
            logger.debug(f"Audit log #{entry.id} created: {strategy_used} / {trading_mode}")
            return entry.id
        else:
            # Fallback — just log to stdout
            logger.info(
                f"AUDIT (no db) | strategy={strategy_used} | mode={trading_mode} | "
                f"regime={market_regime} | notes={notes}"
            )
            return None

    async def get_recent(
        self, db: AsyncSession, limit: int = 50
    ) -> list[dict[str, Any]]:
        """Fetch recent audit entries."""
        from sqlalchemy import select

        result = await db.execute(
            select(AuditLog).order_by(AuditLog.timestamp.desc()).limit(limit)
        )
        rows = result.scalars().all()
        return [
            {
                "id": r.id,
                "timestamp": r.timestamp.isoformat() if r.timestamp else "",
                "raw_llm_output": r.raw_llm_output,
                "parsed_decision": r.parsed_decision,
                "strategy_used": r.strategy_used,
                "market_regime": r.market_regime,
                "order_request": r.order_request,
                "broker_response": r.broker_response,
                "risk_check": r.risk_check,
                "trading_mode": r.trading_mode,
                "notes": r.notes,
            }
            for r in rows
        ]


# ── Singleton ──────────────────────────────────────────────────────────────────

_audit_logger: AuditLogger | None = None


def get_audit_logger() -> AuditLogger:
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger
