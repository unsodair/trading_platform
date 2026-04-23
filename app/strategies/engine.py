"""
Strategy plugin engine — discovers, loads, and runs strategy plugins from
the /plugins directory.

Each plugin folder must contain:
  metadata.json   — name, version, author, tags, etc.
  strategy.py     — class inheriting from BaseStrategy
  config.yaml     — runtime parameters
  backtest.py     — (optional) backtesting harness
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Optional

import yaml
from loguru import logger

from app.models.schemas import (
    MarketRegime,
    StrategyConfig,
    StrategyMetadata,
    StrategySignal,
    StrategyStatus,
)

from app.utils.paths import get_plugins_path

PLUGINS_DIR = get_plugins_path()


class BaseStrategy:
    """
    Base class that all strategy plugins must subclass.
    Plugins override `evaluate()` to produce trading signals.
    """

    name: str = "base"
    metadata: StrategyMetadata | None = None
    config: StrategyConfig | None = None

    async def evaluate(
        self,
        market_data: dict[str, Any],
        indicators: dict[str, Any],
        regime: MarketRegime,
        positions: list[Any] | None = None,
    ) -> list[StrategySignal]:
        """
        Analyse market data + indicators and return zero or more signals.
        Override in your plugin.
        """
        return []

    async def on_activate(self) -> None:
        """Hook called when the strategy is activated."""
        pass

    async def on_deactivate(self) -> None:
        """Hook called when the strategy is deactivated."""
        pass


class StrategyEngine:
    """
    Manages the lifecycle of strategy plugins:
    discover → load → validate → run → deactivate.
    """

    def __init__(self) -> None:
        self._strategies: dict[str, BaseStrategy] = {}
        self._metadata: dict[str, StrategyMetadata] = {}
        self._configs: dict[str, StrategyConfig] = {}

    # ── Discovery & Loading ────────────────────────────────────────────────

    def discover_plugins(self) -> list[str]:
        """Scan the plugins directory and return a list of plugin names."""
        if not PLUGINS_DIR.exists():
            PLUGINS_DIR.mkdir(parents=True, exist_ok=True)
            return []

        found: list[str] = []
        for folder in PLUGINS_DIR.iterdir():
            if folder.is_dir() and (folder / "metadata.json").exists():
                found.append(folder.name)
        logger.info(f"Discovered {len(found)} strategy plugin(s): {found}")
        return found

    def load_plugin(self, plugin_name: str) -> Optional[BaseStrategy]:
        """Load a single plugin by folder name. Returns the strategy instance."""
        plugin_path = PLUGINS_DIR / plugin_name

        # --- metadata.json ---
        meta_file = plugin_path / "metadata.json"
        if not meta_file.exists():
            logger.error(f"Plugin {plugin_name}: missing metadata.json")
            return None

        try:
            meta = StrategyMetadata(**json.loads(meta_file.read_text()))
        except Exception as exc:
            logger.error(f"Plugin {plugin_name}: invalid metadata.json — {exc}")
            return None

        # Only load plugins that are APPROVED or ACTIVE
        if meta.status not in (StrategyStatus.APPROVED, StrategyStatus.ACTIVE):
            logger.warning(
                f"Plugin {plugin_name}: status is '{meta.status}', skipping load"
            )
            self._metadata[plugin_name] = meta
            return None

        # --- config.yaml ---
        cfg_file = plugin_path / "config.yaml"
        config = StrategyConfig()
        if cfg_file.exists():
            try:
                raw = yaml.safe_load(cfg_file.read_text()) or {}
                config = StrategyConfig(**raw)
            except Exception as exc:
                logger.warning(f"Plugin {plugin_name}: config.yaml parse error — {exc}")

        # --- strategy.py ---
        strategy_file = plugin_path / "strategy.py"
        if not strategy_file.exists():
            logger.error(f"Plugin {plugin_name}: missing strategy.py")
            return None

        try:
            spec = importlib.util.spec_from_file_location(
                f"plugins.{plugin_name}.strategy", strategy_file
            )
            if spec is None or spec.loader is None:
                raise ImportError("Cannot create module spec")

            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)

            # Find the first BaseStrategy subclass
            strategy_cls = None
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, BaseStrategy)
                    and attr is not BaseStrategy
                ):
                    strategy_cls = attr
                    break

            if strategy_cls is None:
                logger.error(
                    f"Plugin {plugin_name}: no BaseStrategy subclass found in strategy.py"
                )
                return None

            instance = strategy_cls()
            instance.name = meta.name
            instance.metadata = meta
            instance.config = config

            self._strategies[plugin_name] = instance
            self._metadata[plugin_name] = meta
            self._configs[plugin_name] = config

            logger.info(f"Loaded strategy plugin: {meta.name} v{meta.version}")
            return instance

        except Exception as exc:
            logger.error(f"Plugin {plugin_name}: failed to load strategy.py — {exc}")
            return None

    def load_all(self) -> int:
        """Discover and load all valid plugins. Returns count loaded."""
        names = self.discover_plugins()
        loaded = 0
        for name in names:
            if self.load_plugin(name) is not None:
                loaded += 1
        return loaded

    # ── Runtime ────────────────────────────────────────────────────────────

    async def run_strategy(
        self,
        plugin_name: str,
        market_data: dict[str, Any],
        indicators: dict[str, Any],
        regime: MarketRegime,
        positions: list[Any] | None = None,
    ) -> list[StrategySignal]:
        """Execute a loaded strategy and return its signals."""
        strategy = self._strategies.get(plugin_name)
        if strategy is None:
            logger.warning(f"Strategy '{plugin_name}' not loaded")
            return []

        config = self._configs.get(plugin_name, StrategyConfig())
        if not config.enabled:
            return []

        try:
            signals = await strategy.evaluate(
                market_data=market_data,
                indicators=indicators,
                regime=regime,
                positions=positions,
            )
            return signals
        except Exception as exc:
            logger.error(f"Strategy '{plugin_name}' evaluation error: {exc}")
            return []

    async def run_all(
        self,
        market_data: dict[str, Any],
        indicators: dict[str, Any],
        regime: MarketRegime,
        positions: list[Any] | None = None,
    ) -> dict[str, list[StrategySignal]]:
        """Run all loaded & enabled strategies, return name→signals mapping."""
        results: dict[str, list[StrategySignal]] = {}
        for name in list(self._strategies.keys()):
            signals = await self.run_strategy(
                name, market_data, indicators, regime, positions
            )
            if signals:
                results[name] = signals
        return results

    # ── Accessors ──────────────────────────────────────────────────────────

    def get_loaded_strategies(self) -> list[StrategyMetadata]:
        return list(self._metadata.values())

    def get_active_strategies(self) -> list[StrategyMetadata]:
        return [
            m
            for m in self._metadata.values()
            if m.status in (StrategyStatus.ACTIVE, StrategyStatus.APPROVED)
        ]

    def get_strategy(self, name: str) -> Optional[BaseStrategy]:
        return self._strategies.get(name)


# ── Singleton ──────────────────────────────────────────────────────────────────

_engine: StrategyEngine | None = None


def get_strategy_engine() -> StrategyEngine:
    global _engine
    if _engine is None:
        _engine = StrategyEngine()
    return _engine
