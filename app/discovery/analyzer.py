"""
Code analyzer for discovered strategy repositories.
Parses and reviews code WITHOUT executing it.
Extracts logic patterns and metadata for manual review.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from typing import Any

from loguru import logger


@dataclass
class CodeAnalysis:
    """Result of static analysis on strategy source code."""

    file_count: int = 0
    total_lines: int = 0
    imports: list[str] = field(default_factory=list)
    classes: list[str] = field(default_factory=list)
    functions: list[str] = field(default_factory=list)
    uses_broker_api: bool = False
    uses_ml: bool = False
    uses_technical_indicators: bool = False
    detected_patterns: list[str] = field(default_factory=list)
    risk_flags: list[str] = field(default_factory=list)
    safety_score: float = 0.0  # 0-1, higher = safer
    summary: str = ""


# ── Dangerous patterns we flag ─────────────────────────────────────────────────

_DANGEROUS_PATTERNS = [
    (r"os\.system", "Executes shell commands"),
    (r"subprocess\.", "Uses subprocess — potential code execution"),
    (r"eval\(", "Uses eval() — arbitrary code execution"),
    (r"exec\(", "Uses exec() — arbitrary code execution"),
    (r"__import__", "Dynamic import — potential security risk"),
    (r"ctypes\.", "Uses ctypes — low-level system access"),
    (r"socket\.", "Direct socket access"),
    (r"requests\.(post|put|delete|patch)", "Makes mutating HTTP requests"),
]

# ── Positive patterns we look for ──────────────────────────────────────────────

_INDICATOR_PATTERNS = [
    "sma", "ema", "rsi", "macd", "bollinger", "atr", "adx",
    "vwap", "supertrend", "ichimoku", "stochastic", "obv",
]

_STRATEGY_PATTERNS = [
    "crossover", "mean_reversion", "momentum", "breakout",
    "pairs_trading", "scalping", "swing", "trend_following",
    "options_selling", "iron_condor", "straddle", "strangle",
]


class StrategyCodeAnalyzer:
    """
    Static analyzer for strategy source code.
    Extracts metadata and flags risks WITHOUT executing code.
    """

    def analyze_source(self, source_code: str, filename: str = "") -> CodeAnalysis:
        """Analyze a single Python source file."""
        analysis = CodeAnalysis()
        analysis.total_lines = len(source_code.splitlines())

        # AST-based analysis
        try:
            tree = ast.parse(source_code)
            analysis.imports = self._extract_imports(tree)
            analysis.classes = self._extract_classes(tree)
            analysis.functions = self._extract_functions(tree)
        except SyntaxError as exc:
            analysis.risk_flags.append(f"Syntax error: {exc}")

        # Pattern matching
        lower_src = source_code.lower()

        for pattern, desc in _DANGEROUS_PATTERNS:
            if re.search(pattern, source_code):
                analysis.risk_flags.append(desc)

        for ind in _INDICATOR_PATTERNS:
            if ind in lower_src:
                analysis.uses_technical_indicators = True
                analysis.detected_patterns.append(f"indicator:{ind}")

        for strat in _STRATEGY_PATTERNS:
            if strat in lower_src:
                analysis.detected_patterns.append(f"strategy:{strat}")

        # Broker detection
        broker_keywords = [
            "zerodha", "kite", "dhan", "dhanhq", "fyers", "upstox",
            "angel", "aliceblue", "iifl", "5paisa",
        ]
        if any(bk in lower_src for bk in broker_keywords):
            analysis.uses_broker_api = True

        # ML detection
        ml_keywords = ["sklearn", "tensorflow", "pytorch", "keras", "xgboost", "lightgbm"]
        if any(mk in lower_src for mk in ml_keywords):
            analysis.uses_ml = True

        # Safety score
        risk_count = len(analysis.risk_flags)
        analysis.safety_score = max(0.0, 1.0 - (risk_count * 0.2))

        # Summary
        analysis.summary = self._build_summary(analysis)
        return analysis

    def analyze_multiple(
        self, files: dict[str, str]
    ) -> dict[str, CodeAnalysis]:
        """Analyze multiple files. Keys = filename, values = source code."""
        results: dict[str, CodeAnalysis] = {}
        for fname, code in files.items():
            results[fname] = self.analyze_source(code, fname)
        return results

    # ── AST helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _extract_imports(tree: ast.AST) -> list[str]:
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                imports.append(module)
        return imports

    @staticmethod
    def _extract_classes(tree: ast.AST) -> list[str]:
        return [
            node.name
            for node in ast.walk(tree)
            if isinstance(node, ast.ClassDef)
        ]

    @staticmethod
    def _extract_functions(tree: ast.AST) -> list[str]:
        return [
            node.name
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef)
        ]

    @staticmethod
    def _build_summary(analysis: CodeAnalysis) -> str:
        parts = [f"{analysis.total_lines} lines of code"]
        if analysis.classes:
            parts.append(f"{len(analysis.classes)} class(es)")
        if analysis.functions:
            parts.append(f"{len(analysis.functions)} function(s)")
        if analysis.uses_technical_indicators:
            parts.append("uses technical indicators")
        if analysis.uses_ml:
            parts.append("uses ML/AI")
        if analysis.uses_broker_api:
            parts.append("integrates with broker API")
        if analysis.risk_flags:
            parts.append(f"⚠ {len(analysis.risk_flags)} risk flag(s)")
        return "; ".join(parts)


# ── Singleton ──────────────────────────────────────────────────────────────────

_analyzer: StrategyCodeAnalyzer | None = None


def get_code_analyzer() -> StrategyCodeAnalyzer:
    global _analyzer
    if _analyzer is None:
        _analyzer = StrategyCodeAnalyzer()
    return _analyzer
