"""
Indian Markets Trading Platform — FastAPI application entry point.

Registers all routes, initializes database, loads strategy plugins.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
import sys

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from loguru import logger

from app.config import settings
from app.database import init_db
from app.models import db_models  # Ensure models are registered with Base
from app.strategies.engine import get_strategy_engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown hooks."""
    # ── Startup ────────────────────────────────────────────────────
    logger.info(f"🚀 Starting Trading Platform (mode={settings.trading_mode.value})")

    # Initialize database tables
    await init_db()
    logger.info("✅ Database initialized")

    # Load strategy plugins
    engine = get_strategy_engine()
    count = engine.load_all()
    logger.info(f"✅ Loaded {count} strategy plugin(s)")

    yield

    # ── Shutdown ───────────────────────────────────────────────────
    logger.info("👋 Shutting down Trading Platform")

    # Gracefully close Dhan broker HTTP client session
    from app.brokers import dhan_adapter
    if dhan_adapter._dhan_instance is not None:
        await dhan_adapter._dhan_instance.close()
        logger.info("✅ Dhan broker adapter client closed")


# ── Create application ────────────────────────────────────────────────────────

app = FastAPI(
    title="Indian Markets Trading Platform",
    description=(
        "AI-powered algorithmic trading platform for Indian stock markets "
        "(NSE/BSE) using Dhan broker API, pluggable LLM layer, and strategy engine."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# ── Register routers ──────────────────────────────────────────────────────────

from app.api.routes_broker import router as broker_router
from app.api.routes_strategy import router as strategy_router
from app.api.routes_trading import router as trading_router
from app.api.routes_discovery import router as discovery_router
from app.api.routes_dashboard import router as dashboard_router
from app.api.routes_settings import router as settings_router
from app.api.routes_emergency import router as emergency_router

app.include_router(broker_router)
app.include_router(strategy_router)
app.include_router(trading_router)
app.include_router(discovery_router)
app.include_router(dashboard_router)
app.include_router(settings_router)
app.include_router(emergency_router)

# ── Static files for dashboard ─────────────────────────────────────────────────

from app.utils.paths import get_static_path

static_dir = get_static_path()
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


# ── Health check ───────────────────────────────────────────────────────────────

@app.get("/health", tags=["System"])
async def health_check():
    return {
        "status": "healthy",
        "version": "1.0.0",
        "mode": settings.trading_mode.value,
        "active_llm": settings.active_llm.value,
    }


# ── CLI entry point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    
    # Reload should be False when running as an EXE
    is_reload = not getattr(sys, 'frozen', False) and settings.app_debug

    uvicorn.run(
        app,
        host=settings.app_host,
        port=settings.app_port,
        reload=is_reload,
        log_level=settings.log_level.lower(),
    )
