"""
Market Scanner — fetches top gainers/losers from NSE India.

Uses NSE's public API with proper session/cookie handling.
Falls back to preset stock lists when the live API is unavailable.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx
from loguru import logger
from pydantic import BaseModel, Field


# ── Data Models ────────────────────────────────────────────────────────────────

class MarketMover(BaseModel):
    """A single stock entry returned by the scanner."""
    symbol: str
    ltp: float = 0.0
    open_price: float = 0.0
    high_price: float = 0.0
    low_price: float = 0.0
    prev_close: float = 0.0
    change: float = 0.0
    change_pct: float = 0.0
    volume: int = 0


class ScanResult(BaseModel):
    """Aggregated result of a market scan."""
    gainers: list[MarketMover] = Field(default_factory=list)
    losers: list[MarketMover] = Field(default_factory=list)
    source: str = "nse"  # nse | unavailable
    timestamp: str = ""


# ── Preset Stock Lists ────────────────────────────────────────────────────────

NIFTY_50 = [
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK",
    "HINDUNILVR", "ITC", "SBIN", "BHARTIARTL", "KOTAKBANK",
    "LT", "BAJFINANCE", "HCLTECH", "AXISBANK", "MARUTI",
    "ASIANPAINT", "SUNPHARMA", "TITAN", "ULTRACEMCO", "DMART",
    "WIPRO", "NTPC", "POWERGRID", "TATAMOTORS", "M&M",
    "NESTLEIND", "TATASTEEL", "JSWSTEEL", "ADANIENT", "ADANIPORTS",
    "ONGC", "COALINDIA", "BPCL", "IOC", "TECHM",
    "INDUSINDBK", "GRASIM", "CIPLA", "DRREDDY", "DIVISLAB",
    "BRITANNIA", "HEROMOTOCO", "BAJAJFINSV", "EICHERMOT", "APOLLOHOSP",
    "UPL", "TATACONSUM", "SBILIFE", "HDFCLIFE", "BAJAJ-AUTO",
]

BANK_NIFTY = [
    "HDFCBANK", "ICICIBANK", "KOTAKBANK", "AXISBANK", "SBIN",
    "INDUSINDBK", "BANDHANBNK", "FEDERALBNK", "IDFCFIRSTB", "PNB",
    "BANKBARODA", "AUBANK",
]

IT_STOCKS = [
    "TCS", "INFY", "HCLTECH", "WIPRO", "TECHM",
    "LTIM", "MPHASIS", "COFORGE", "PERSISTENT", "LTTS",
]

PHARMA_STOCKS = [
    "SUNPHARMA", "DRREDDY", "CIPLA", "DIVISLAB", "AUROPHARMA",
    "BIOCON", "LUPIN", "TORNTPHARM", "ALKEM", "IPCALAB",
]

AUTO_STOCKS = [
    "TATAMOTORS", "M&M", "MARUTI", "BAJAJ-AUTO", "HEROMOTOCO",
    "EICHERMOT", "ASHOKLEY", "TVSMOTOR", "BALKRISIND", "MRF",
]

PRESET_CATEGORIES: dict[str, dict[str, Any]] = {
    "nifty50": {"name": "Nifty 50", "symbols": NIFTY_50},
    "banknifty": {"name": "Bank Nifty", "symbols": BANK_NIFTY},
    "it": {"name": "IT Sector", "symbols": IT_STOCKS},
    "pharma": {"name": "Pharma Sector", "symbols": PHARMA_STOCKS},
    "auto": {"name": "Auto Sector", "symbols": AUTO_STOCKS},
}


# ── Scanner Implementation ────────────────────────────────────────────────────

class MarketScanner:
    """Fetches live market data from NSE India's public API."""

    NSE_BASE = "https://www.nseindia.com"

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None
        self._cookies_valid = False

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                    "Accept": "application/json, text/plain, */*",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Accept-Encoding": "gzip, deflate, br",
                    "Referer": "https://www.nseindia.com/",
                },
                timeout=15.0,
                follow_redirects=True,
            )
            self._cookies_valid = False
        return self._client

    async def _ensure_session(self) -> None:
        """Hit NSE homepage to get session cookies."""
        if not self._cookies_valid:
            client = self._get_client()
            resp = await client.get(self.NSE_BASE)
            if resp.status_code == 200:
                self._cookies_valid = True
                logger.debug("NSE session cookies initialized")
            else:
                raise ConnectionError(f"NSE returned status {resp.status_code}")

    async def _fetch_index_data(self, index: str = "NIFTY 50") -> list[dict[str, Any]]:
        """Fetch stock data for a given NSE index."""
        await self._ensure_session()
        client = self._get_client()
        resp = await client.get(
            f"{self.NSE_BASE}/api/equity-stockIndices",
            params={"index": index},
        )
        resp.raise_for_status()
        data = resp.json()
        # Filter out the index summary row itself
        stocks = [
            item for item in data.get("data", [])
            if item.get("symbol", "") != index
            and not item.get("symbol", "").startswith("NIFTY")
        ]
        return stocks

    @staticmethod
    def _parse_stock(item: dict[str, Any]) -> MarketMover:
        return MarketMover(
            symbol=item.get("symbol", ""),
            ltp=float(item.get("lastPrice", 0) or 0),
            open_price=float(item.get("open", 0) or 0),
            high_price=float(item.get("dayHigh", 0) or 0),
            low_price=float(item.get("dayLow", 0) or 0),
            prev_close=float(item.get("previousClose", 0) or 0),
            change=float(item.get("change", 0) or 0),
            change_pct=float(item.get("pChange", 0) or 0),
            volume=int(item.get("totalTradedVolume", 0) or 0),
        )

    # ── Public API ─────────────────────────────────────────────────────────

    async def scan_market(self, index: str = "NIFTY 50", count: int = 10) -> ScanResult:
        """Fetch top gainers and losers from NSE for the given index."""
        try:
            stocks = await self._fetch_index_data(index)
            movers = [self._parse_stock(s) for s in stocks]

            sorted_desc = sorted(movers, key=lambda x: x.change_pct, reverse=True)
            gainers = [s for s in sorted_desc if s.change_pct > 0][:count]
            losers = [s for s in reversed(sorted_desc) if s.change_pct < 0][:count]

            return ScanResult(
                gainers=gainers,
                losers=losers,
                source="nse",
                timestamp=datetime.now().isoformat(),
            )
        except Exception as exc:
            logger.warning(f"NSE market scan failed: {exc}")
            return ScanResult(
                source="unavailable",
                timestamp=datetime.now().isoformat(),
            )

    def get_preset_categories(self) -> dict[str, dict[str, Any]]:
        """Return metadata for all preset stock categories."""
        return {
            k: {"name": v["name"], "count": len(v["symbols"])}
            for k, v in PRESET_CATEGORIES.items()
        }

    def get_preset_stocks(self, category: str) -> list[str]:
        """Return stocks belonging to a preset category."""
        cat = PRESET_CATEGORIES.get(category)
        return list(cat["symbols"]) if cat else []

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()


# ── Singleton ──────────────────────────────────────────────────────────────────

_scanner: MarketScanner | None = None


def get_market_scanner() -> MarketScanner:
    global _scanner
    if _scanner is None:
        _scanner = MarketScanner()
    return _scanner
