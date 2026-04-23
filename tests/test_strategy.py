"""
Tests for the strategy plugin engine.
"""

import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch

from app.strategies.engine import StrategyEngine, BaseStrategy, PLUGINS_DIR
from app.models.schemas import MarketRegime, StrategySignal


class TestStrategyEngine:
    """Test strategy discovery, loading, and execution."""

    def test_discover_empty_dir(self, tmp_path):
        """No plugins → empty list."""
        engine = StrategyEngine()
        with patch("app.strategies.engine.PLUGINS_DIR", tmp_path):
            found = engine.discover_plugins()
            assert found == []

    def test_discover_valid_plugin(self, tmp_path):
        """Plugin with metadata.json is discovered."""
        plugin_dir = tmp_path / "test_strategy"
        plugin_dir.mkdir()
        (plugin_dir / "metadata.json").write_text(json.dumps({
            "name": "Test",
            "version": "1.0.0",
            "status": "approved",
        }))
        (plugin_dir / "strategy.py").write_text("""
from app.strategies.engine import BaseStrategy
class TestStrat(BaseStrategy):
    async def evaluate(self, market_data, indicators, regime, positions=None):
        return []
""")
        (plugin_dir / "config.yaml").write_text("enabled: true\nsymbols: [TEST]\nparameters: {}")

        engine = StrategyEngine()
        with patch("app.strategies.engine.PLUGINS_DIR", tmp_path):
            found = engine.discover_plugins()
            assert "test_strategy" in found

    def test_load_plugin_with_candidate_status_skips(self, tmp_path):
        """Plugin with 'candidate' status should NOT be loaded."""
        plugin_dir = tmp_path / "candidate_strat"
        plugin_dir.mkdir()
        (plugin_dir / "metadata.json").write_text(json.dumps({
            "name": "Candidate",
            "version": "1.0.0",
            "status": "candidate",
        }))
        (plugin_dir / "strategy.py").write_text("pass")

        engine = StrategyEngine()
        with patch("app.strategies.engine.PLUGINS_DIR", tmp_path):
            result = engine.load_plugin("candidate_strat")
            assert result is None

    @pytest.mark.asyncio
    async def test_run_strategy_not_loaded(self):
        """Running a strategy that isn't loaded returns empty signals."""
        engine = StrategyEngine()
        signals = await engine.run_strategy(
            "nonexistent", {}, {}, MarketRegime.RANGE_BOUND
        )
        assert signals == []

    def test_base_strategy_interface(self):
        """BaseStrategy can be instantiated."""
        strat = BaseStrategy()
        assert strat.name == "base"
