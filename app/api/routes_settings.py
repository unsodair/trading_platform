"""
Settings API routes — runtime configuration for broker and LLM.
Allows updating API keys, selecting LLM provider, and testing connections
without restarting the application.
"""

from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Optional
from fastapi import APIRouter

from loguru import logger

from app.config import ActiveLLM, settings

router = APIRouter(prefix="/api/settings", tags=["Settings"])


# ── Request / Response Models ──────────────────────────────────────────────────

class BrokerConfigRequest(BaseModel):
    """Payload to update Dhan broker credentials at runtime."""
    dhan_client_id: Optional[str] = None
    dhan_access_token: Optional[str] = None


class BrokerConfigResponse(BaseModel):
    dhan_client_id: str = ""
    dhan_access_token_masked: str = ""
    connected: bool = False


class LLMConfigRequest(BaseModel):
    """Payload to switch LLM provider and/or update credentials at runtime."""
    active_llm: Optional[str] = None          # openai | anthropic | gemini | ollama
    openai_api_key: Optional[str] = None
    openai_model: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    anthropic_model: Optional[str] = None
    gemini_api_key: Optional[str] = None
    gemini_model: Optional[str] = None
    ollama_host: Optional[str] = None
    ollama_model: Optional[str] = None


class LLMConfigResponse(BaseModel):
    active_llm: str = ""
    openai_api_key_masked: str = ""
    openai_model: str = ""
    anthropic_api_key_masked: str = ""
    anthropic_model: str = ""
    gemini_api_key_masked: str = ""
    gemini_model: str = ""
    ollama_host: str = ""
    ollama_model: str = ""
    healthy: Optional[bool] = None


class RiskConfigRequest(BaseModel):
    """Payload to update risk controls at runtime."""
    max_loss_per_day: Optional[float] = None
    max_order_size: Optional[float] = None
    max_open_positions: Optional[int] = None
    allowed_trading_start: Optional[str] = None
    allowed_trading_end: Optional[str] = None
    cooldown_between_trades_seconds: Optional[int] = None
    mandatory_stop_loss_percent: Optional[float] = None


class GithubConfigRequest(BaseModel):
    """Payload to update GitHub token at runtime."""
    github_token: Optional[str] = None


# ── Helpers ────────────────────────────────────────────────────────────────────

def _mask_key(key: str) -> str:
    """Mask an API key for safe display, e.g. 'sk-abc...xyz'."""
    if not key or len(key) < 8 or key.startswith("your"):
        return ""
    return key[:6] + "•" * min(len(key) - 10, 20) + key[-4:]


def _reset_broker_singleton():
    """Force broker adapter to reinitialize with new credentials."""
    from app.brokers import dhan_adapter
    dhan_adapter._dhan_instance = None
    from app.brokers import factory
    factory._broker_instance = None
    logger.info("🔄 Broker adapter singleton reset (will reconnect on next use)")


def _reset_llm_singleton():
    """Force LLM factory to create a fresh adapter with new config."""
    # The factory creates a new instance each call — no singleton to reset.
    # But we invalidate any cached references elsewhere.
    logger.info("🔄 LLM adapter config updated (next call will use new settings)")


# ── Broker Endpoints ──────────────────────────────────────────────────────────

@router.get("/broker", response_model=BrokerConfigResponse)
async def get_broker_config():
    """Get current broker configuration (keys are masked)."""
    return BrokerConfigResponse(
        dhan_client_id=settings.dhan_client_id,
        dhan_access_token_masked=_mask_key(settings.dhan_access_token),
    )


@router.post("/broker", response_model=BrokerConfigResponse)
async def update_broker_config(req: BrokerConfigRequest):
    """Update broker credentials at runtime. Only non-null fields are updated."""
    if req.dhan_client_id is not None:
        settings.dhan_client_id = req.dhan_client_id
        logger.info(f"✅ Updated dhan_client_id → {req.dhan_client_id}")

    if req.dhan_access_token is not None:
        settings.dhan_access_token = req.dhan_access_token
        logger.info("✅ Updated dhan_access_token → (masked)")

    # Reset the broker singleton so the next call uses new credentials
    _reset_broker_singleton()

    return BrokerConfigResponse(
        dhan_client_id=settings.dhan_client_id,
        dhan_access_token_masked=_mask_key(settings.dhan_access_token),
    )


@router.post("/broker/test")
async def test_broker_connection():
    """Test broker connectivity with current credentials."""
    _reset_broker_singleton()
    from app.brokers.factory import get_broker
    adapter = get_broker()
    try:
        status = await adapter.connect()
        return {
            "success": status.connected,
            "client_id": status.client_id,
            "message": "Connected successfully" if status.connected else "Connection failed — check credentials",
        }
    except Exception as exc:
        return {"success": False, "message": str(exc)}


# ── LLM Endpoints ────────────────────────────────────────────────────────────

@router.get("/llm", response_model=LLMConfigResponse)
async def get_llm_config():
    """Get current LLM configuration (keys are masked)."""
    return LLMConfigResponse(
        active_llm=settings.active_llm.value,
        openai_api_key_masked=_mask_key(settings.openai_api_key),
        openai_model=settings.openai_model,
        anthropic_api_key_masked=_mask_key(settings.anthropic_api_key),
        anthropic_model=settings.anthropic_model,
        gemini_api_key_masked=_mask_key(settings.gemini_api_key),
        gemini_model=settings.gemini_model,
        ollama_host=settings.ollama_host,
        ollama_model=settings.ollama_model,
    )


@router.post("/llm", response_model=LLMConfigResponse)
async def update_llm_config(req: LLMConfigRequest):
    """Update LLM provider and/or credentials at runtime."""
    if req.active_llm is not None:
        try:
            settings.active_llm = ActiveLLM(req.active_llm)
            logger.info(f"✅ Switched active LLM → {req.active_llm}")
        except ValueError:
            logger.warning(f"⚠️ Invalid LLM provider: {req.active_llm}")

    # Update individual provider settings
    if req.openai_api_key is not None:
        settings.openai_api_key = req.openai_api_key
        logger.info("✅ Updated openai_api_key")
    if req.openai_model is not None:
        settings.openai_model = req.openai_model
        logger.info(f"✅ Updated openai_model → {req.openai_model}")

    if req.anthropic_api_key is not None:
        settings.anthropic_api_key = req.anthropic_api_key
        logger.info("✅ Updated anthropic_api_key")
    if req.anthropic_model is not None:
        settings.anthropic_model = req.anthropic_model
        logger.info(f"✅ Updated anthropic_model → {req.anthropic_model}")

    if req.gemini_api_key is not None:
        settings.gemini_api_key = req.gemini_api_key
        logger.info("✅ Updated gemini_api_key")
    if req.gemini_model is not None:
        settings.gemini_model = req.gemini_model
        logger.info(f"✅ Updated gemini_model → {req.gemini_model}")

    if req.ollama_host is not None:
        settings.ollama_host = req.ollama_host
        logger.info(f"✅ Updated ollama_host → {req.ollama_host}")
    if req.ollama_model is not None:
        settings.ollama_model = req.ollama_model
        logger.info(f"✅ Updated ollama_model → {req.ollama_model}")

    _reset_llm_singleton()

    return LLMConfigResponse(
        active_llm=settings.active_llm.value,
        openai_api_key_masked=_mask_key(settings.openai_api_key),
        openai_model=settings.openai_model,
        anthropic_api_key_masked=_mask_key(settings.anthropic_api_key),
        anthropic_model=settings.anthropic_model,
        gemini_api_key_masked=_mask_key(settings.gemini_api_key),
        gemini_model=settings.gemini_model,
        ollama_host=settings.ollama_host,
        ollama_model=settings.ollama_model,
    )


@router.post("/llm/test")
async def test_llm_connection():
    """Test connectivity to the currently active LLM provider."""
    from app.llms.factory import get_llm_adapter
    try:
        adapter = get_llm_adapter()
        healthy = await adapter.health_check()
        return {
            "success": healthy,
            "provider": settings.active_llm.value,
            "message": f"{settings.active_llm.value} is reachable" if healthy else f"{settings.active_llm.value} health check failed",
        }
    except Exception as exc:
        return {
            "success": False,
            "provider": settings.active_llm.value,
            "message": str(exc),
        }


# ── Risk Control Endpoints ───────────────────────────────────────────────────

@router.post("/risk")
async def update_risk_config(req: RiskConfigRequest):
    """Update risk control parameters at runtime."""
    if req.max_loss_per_day is not None:
        settings.max_loss_per_day = req.max_loss_per_day
    if req.max_order_size is not None:
        settings.max_order_size = req.max_order_size
    if req.max_open_positions is not None:
        settings.max_open_positions = req.max_open_positions
    if req.allowed_trading_start is not None:
        settings.allowed_trading_start = req.allowed_trading_start
    if req.allowed_trading_end is not None:
        settings.allowed_trading_end = req.allowed_trading_end
    if req.cooldown_between_trades_seconds is not None:
        settings.cooldown_between_trades_seconds = req.cooldown_between_trades_seconds
    if req.mandatory_stop_loss_percent is not None:
        settings.mandatory_stop_loss_percent = req.mandatory_stop_loss_percent

    logger.info("✅ Risk controls updated at runtime")
    return {"message": "Risk controls updated", "settings": {
        "max_loss_per_day": settings.max_loss_per_day,
        "max_order_size": settings.max_order_size,
        "max_open_positions": settings.max_open_positions,
        "allowed_trading_start": settings.allowed_trading_start,
        "allowed_trading_end": settings.allowed_trading_end,
        "cooldown_between_trades_seconds": settings.cooldown_between_trades_seconds,
        "mandatory_stop_loss_percent": settings.mandatory_stop_loss_percent,
    }}


# ── GitHub Token Endpoint ────────────────────────────────────────────────────

@router.post("/github")
async def update_github_token(req: GithubConfigRequest):
    """Update GitHub token for strategy discovery."""
    if req.github_token is not None:
        settings.github_token = req.github_token
        logger.info("✅ Updated github_token")
    return {"message": "GitHub token updated", "masked": _mask_key(settings.github_token)}


# ── Full Config Summary (for dashboard) ──────────────────────────────────────

@router.get("/summary")
async def get_settings_summary():
    """Return a full summary of all runtime-configurable settings."""
    return {
        "broker": {
            "dhan_client_id": settings.dhan_client_id,
            "dhan_access_token_set": bool(settings.dhan_access_token and not settings.dhan_access_token.startswith("your")),
            "dhan_access_token_masked": _mask_key(settings.dhan_access_token),
        },
        "llm": {
            "active_llm": settings.active_llm.value,
            "openai": {
                "key_set": bool(settings.openai_api_key and not settings.openai_api_key.startswith("sk-your")),
                "key_masked": _mask_key(settings.openai_api_key),
                "model": settings.openai_model,
            },
            "anthropic": {
                "key_set": bool(settings.anthropic_api_key and not settings.anthropic_api_key.startswith("sk-ant-your")),
                "key_masked": _mask_key(settings.anthropic_api_key),
                "model": settings.anthropic_model,
            },
            "gemini": {
                "key_set": bool(settings.gemini_api_key and not settings.gemini_api_key.startswith("your")),
                "key_masked": _mask_key(settings.gemini_api_key),
                "model": settings.gemini_model,
            },
            "ollama": {
                "host": settings.ollama_host,
                "model": settings.ollama_model,
            },
        },
        "github_token_set": bool(settings.github_token and not settings.github_token.startswith("ghp_your")),
        "github_token_masked": _mask_key(settings.github_token),
        "trading_mode": settings.trading_mode.value,
    }
