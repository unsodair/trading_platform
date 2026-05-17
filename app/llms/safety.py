"""
LLM Safety Layer — ensures AI decisions are ADVISORY ONLY.

Enforces the critical safety chain:
    LLM → Safety Guard → Rule Engine → Risk Engine → Execution

An LLM must NEVER:
  - Directly place orders
  - Bypass risk checks
  - Control position sizing without human-approved limits
  - Generate signals faster than rate limits allow

This module wraps every LLM decision with validation, rate limiting,
schema enforcement, and action whitelisting.
"""

from __future__ import annotations

from datetime import datetime, timezone
from collections import deque
from typing import Optional

from loguru import logger
from pydantic import BaseModel, Field

from app.models.schemas import LLMDecision


# ── Configuration ──────────────────────────────────────────────────────────────

class LLMSafetyConfig(BaseModel):
    """Configurable safety thresholds for LLM decision filtering."""

    # Minimum confidence to allow any actionable decision
    min_confidence_threshold: float = 0.3

    # Maximum signals per minute from LLM (rate limiting)
    max_signals_per_minute: int = 10

    # Maximum order value an LLM can recommend (₹)
    max_recommended_order_value: float = 50_000.0

    # Maximum quantity per LLM-recommended order
    max_recommended_quantity: int = 500

    # Allowed actions the LLM may recommend
    allowed_actions: list[str] = Field(
        default_factory=lambda: ["BUY", "SELL", "HOLD", "CLOSE", "NO_ACTION"]
    )

    # Blocked actions that must never pass through
    blocked_actions: list[str] = Field(default_factory=list)

    # Whether to require stop_loss on BUY/SELL actions
    require_stop_loss: bool = True

    # Maximum leverage ratio LLM can suggest (1.0 = no leverage)
    max_leverage_ratio: float = 1.0


# ── Safety Validation Result ──────────────────────────────────────────────────

class SafetyCheckResult(BaseModel):
    """Result of LLM safety validation."""
    passed: bool
    original_decision: LLMDecision
    filtered_decision: LLMDecision
    warnings: list[str] = Field(default_factory=list)
    blocked_reason: Optional[str] = None


# ── LLM Safety Guard ──────────────────────────────────────────────────────────

class LLMSafetyGuard:
    """
    Wraps every LLM decision with safety validation.

    Must be called BEFORE any LLM decision reaches the execution pipeline.
    Acts as a strict gatekeeper between AI output and trading actions.
    """

    def __init__(self, config: LLMSafetyConfig | None = None) -> None:
        self._config = config or LLMSafetyConfig()
        # Sliding window for rate limiting (timestamps of recent signals)
        self._signal_timestamps: deque[datetime] = deque(maxlen=1000)
        # Counters for observability
        self._total_checked: int = 0
        self._total_blocked: int = 0
        self._total_modified: int = 0

    def validate(self, decision: LLMDecision) -> SafetyCheckResult:
        """
        Validate and filter an LLM decision through all safety checks.

        Returns a SafetyCheckResult containing the filtered decision
        and any warnings or block reasons.
        """
        self._total_checked += 1
        warnings: list[str] = []
        blocked_reason: str | None = None

        # Start with a copy of the original decision
        filtered = decision.model_copy()

        # ── 1. Action Whitelist ────────────────────────────────────────
        if decision.action not in self._config.allowed_actions:
            blocked_reason = (
                f"Action '{decision.action}' not in allowed list: "
                f"{self._config.allowed_actions}"
            )
            self._total_blocked += 1
            logger.warning(f"🛡️ LLM Safety BLOCKED: {blocked_reason}")
            return SafetyCheckResult(
                passed=False,
                original_decision=decision,
                filtered_decision=self._force_no_action(decision, blocked_reason),
                warnings=warnings,
                blocked_reason=blocked_reason,
            )

        # ── 2. Blocked Actions ─────────────────────────────────────────
        if decision.action in self._config.blocked_actions:
            blocked_reason = f"Action '{decision.action}' is explicitly blocked"
            self._total_blocked += 1
            logger.warning(f"🛡️ LLM Safety BLOCKED: {blocked_reason}")
            return SafetyCheckResult(
                passed=False,
                original_decision=decision,
                filtered_decision=self._force_no_action(decision, blocked_reason),
                warnings=warnings,
                blocked_reason=blocked_reason,
            )

        # ── 3. Confidence Floor ────────────────────────────────────────
        if (
            decision.action in ("BUY", "SELL", "CLOSE")
            and decision.confidence < self._config.min_confidence_threshold
        ):
            blocked_reason = (
                f"Confidence {decision.confidence:.2f} below minimum "
                f"{self._config.min_confidence_threshold}"
            )
            self._total_blocked += 1
            logger.warning(f"🛡️ LLM Safety BLOCKED: {blocked_reason}")
            return SafetyCheckResult(
                passed=False,
                original_decision=decision,
                filtered_decision=self._force_no_action(decision, blocked_reason),
                warnings=warnings,
                blocked_reason=blocked_reason,
            )

        # ── 4. Rate Limiting ──────────────────────────────────────────
        if decision.action in ("BUY", "SELL", "CLOSE"):
            now = datetime.now(timezone.utc)
            # Count signals in the last 60 seconds
            cutoff = now.timestamp() - 60.0
            recent_count = sum(
                1 for ts in self._signal_timestamps if ts.timestamp() > cutoff
            )
            if recent_count >= self._config.max_signals_per_minute:
                blocked_reason = (
                    f"Rate limit exceeded: {recent_count} signals in last 60s "
                    f"(max {self._config.max_signals_per_minute})"
                )
                self._total_blocked += 1
                logger.warning(f"🛡️ LLM Safety BLOCKED: {blocked_reason}")
                return SafetyCheckResult(
                    passed=False,
                    original_decision=decision,
                    filtered_decision=self._force_no_action(decision, blocked_reason),
                    warnings=warnings,
                    blocked_reason=blocked_reason,
                )
            self._signal_timestamps.append(now)

        # ── 5. Quantity Cap ────────────────────────────────────────────
        if (
            filtered.quantity is not None
            and filtered.quantity > self._config.max_recommended_quantity
        ):
            warnings.append(
                f"Quantity capped: {filtered.quantity} → "
                f"{self._config.max_recommended_quantity}"
            )
            filtered.quantity = self._config.max_recommended_quantity
            self._total_modified += 1

        # ── 6. Stop Loss Requirement ───────────────────────────────────
        if (
            self._config.require_stop_loss
            and decision.action in ("BUY", "SELL")
            and decision.stop_loss is None
        ):
            warnings.append(
                "LLM did not provide a stop_loss — must be set manually "
                "before execution"
            )

        # ── 7. Confidence Cap (prevent over-confidence) ────────────────
        if filtered.confidence > 0.95:
            warnings.append(
                f"Confidence capped: {filtered.confidence:.2f} → 0.95 "
                f"(AI over-confidence protection)"
            )
            filtered.confidence = 0.95
            self._total_modified += 1

        # ── 8. Urgency Sanitization ────────────────────────────────────
        if filtered.urgency not in ("low", "medium", "high"):
            warnings.append(
                f"Invalid urgency '{filtered.urgency}' → defaulting to 'low'"
            )
            filtered.urgency = "low"
            self._total_modified += 1

        passed = blocked_reason is None
        if warnings:
            logger.info(f"🛡️ LLM Safety warnings: {warnings}")

        return SafetyCheckResult(
            passed=passed,
            original_decision=decision,
            filtered_decision=filtered,
            warnings=warnings,
            blocked_reason=blocked_reason,
        )

    def get_stats(self) -> dict:
        """Return observability counters."""
        return {
            "total_checked": self._total_checked,
            "total_blocked": self._total_blocked,
            "total_modified": self._total_modified,
            "block_rate": (
                round(self._total_blocked / self._total_checked, 3)
                if self._total_checked > 0
                else 0.0
            ),
        }

    @staticmethod
    def _force_no_action(decision: LLMDecision, reason: str) -> LLMDecision:
        """Convert a blocked decision into a safe NO_ACTION."""
        return LLMDecision(
            action="NO_ACTION",
            symbol=decision.symbol,
            confidence=0.0,
            reasoning=f"BLOCKED BY SAFETY GUARD: {reason}",
            raw_output=decision.raw_output,
        )


# ── Singleton ──────────────────────────────────────────────────────────────────

_safety_guard: LLMSafetyGuard | None = None


def get_llm_safety_guard() -> LLMSafetyGuard:
    global _safety_guard
    if _safety_guard is None:
        _safety_guard = LLMSafetyGuard()
    return _safety_guard
