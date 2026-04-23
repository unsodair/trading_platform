"""
Application configuration — loads settings from .env with Pydantic-settings.
Designed for SQLite first, PostgreSQL-ready.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class TradingMode(str, Enum):
    PAPER = "paper"
    LIVE = "live"


class ActiveLLM(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    OLLAMA = "ollama"


BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Central configuration, sourced from environment / .env file."""

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ──────────────────────────────────────────────────────────
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"
    secret_key: str = "change-me-in-production"

    # ── Trading Mode ─────────────────────────────────────────────────
    trading_mode: TradingMode = TradingMode.PAPER

    # ── Dhan Broker ──────────────────────────────────────────────────
    dhan_client_id: str = ""
    dhan_access_token: str = ""

    # ── LLM Selection ────────────────────────────────────────────────
    active_llm: ActiveLLM = ActiveLLM.OPENAI

    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"

    # Anthropic
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"

    # Gemini
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"

    # Ollama
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"

    # ── Risk Controls ────────────────────────────────────────────────
    max_loss_per_day: float = 5000.0
    max_order_size: float = 100_000.0
    max_open_positions: int = 10
    allowed_trading_start: str = "09:15"
    allowed_trading_end: str = "15:30"
    cooldown_between_trades_seconds: int = 30
    mandatory_stop_loss_percent: float = 2.0

    # ── Database ─────────────────────────────────────────────────────
    database_url: str = f"sqlite+aiosqlite:///{BASE_DIR.as_posix()}/trading_platform.db"

    # ── GitHub Discovery ─────────────────────────────────────────────
    github_token: str = ""

    # ── Symbol Whitelist (comma-separated) ───────────────────────────
    symbol_whitelist: str = ""

    @property
    def whitelisted_symbols(self) -> list[str]:
        if not self.symbol_whitelist:
            return []
        return [s.strip().upper() for s in self.symbol_whitelist.split(",") if s.strip()]


settings = Settings()
