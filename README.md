# 📊 Indian Markets Trading Platform

A production-style, AI-powered algorithmic trading platform for Indian stock markets (NSE/BSE) built with **Python + FastAPI**, using **Dhan** as the broker layer and a pluggable **LLM abstraction** for intelligent decision-making.

---

## ✨ Features

| Module | Description |
|--------|-------------|
| **Dhan Broker Adapter** | Full integration — holdings, positions, funds, orders, market data |
| **Pluggable LLM Layer** | OpenAI, Anthropic Claude, Google Gemini, local Ollama |
| **Strategy Plugin Engine** | Hot-loadable plugins with metadata, config, backtest support |
| **Market Regime Detector** | SMA/ADX/BB/ATR-based classification (trending, range, volatile, event) |
| **GitHub Strategy Discovery** | Search, score, and review — never auto-execute external code |
| **Paper Trading Engine** | Simulated fills, virtual positions, slippage modeling |
| **Live Trading Engine** | Multi-gate safeguards before every real order |
| **Hard Risk Controls** | Daily loss limit, order cap, position limit, hours, cooldown, mandatory SL |
| **Audit Logging** | Every decision persisted — LLM output, strategy, regime, broker response |
| **Web Dashboard** | Real-time status, positions, strategies, discovered repos, regime display |

---

## 📁 Project Structure

```
trading_platform/
├── app/
│   ├── main.py                     # FastAPI entry point
│   ├── config.py                   # Pydantic-settings (.env loader)
│   ├── database.py                 # Async SQLAlchemy (SQLite → PostgreSQL)
│   ├── models/
│   │   ├── schemas.py              # All Pydantic request/response models
│   │   └── db_models.py            # SQLAlchemy ORM models
│   ├── brokers/
│   │   ├── base.py                 # Abstract broker interface
│   │   └── dhan_adapter.py         # Dhan API implementation
│   ├── llms/
│   │   ├── base.py                 # Abstract LLM interface + JSON parser
│   │   ├── factory.py              # LLM adapter factory
│   │   ├── openai_adapter.py       # ChatGPT adapter
│   │   ├── anthropic_adapter.py    # Claude adapter
│   │   ├── gemini_adapter.py       # Gemini adapter
│   │   └── ollama_adapter.py       # Local Ollama adapter
│   ├── strategies/
│   │   └── engine.py               # Plugin discovery, loading, execution
│   ├── regime/
│   │   └── detector.py             # Market regime classifier
│   ├── discovery/
│   │   ├── github_scanner.py       # GitHub repository search & ranking
│   │   └── analyzer.py             # Static code analysis (no execution)
│   ├── trading/
│   │   ├── risk_manager.py         # Hard risk controls
│   │   ├── paper_engine.py         # Paper trading simulator
│   │   └── live_engine.py          # Live execution with safeguards
│   ├── audit/
│   │   └── logger.py               # Structured audit trail
│   ├── api/
│   │   ├── routes_broker.py        # /api/broker/* endpoints
│   │   ├── routes_strategy.py      # /api/strategies/* endpoints
│   │   ├── routes_trading.py       # /api/trading/* endpoints
│   │   ├── routes_discovery.py     # /api/discovery/* endpoints
│   │   └── routes_dashboard.py     # Dashboard + /api/dashboard/*
│   └── dashboard/
│       └── templates/
│           └── index.html          # Web dashboard UI
├── plugins/
│   ├── mean_reversion_rsi/         # RSI Oversold/Overbought
│   ├── scalping_ema_crossover/     # EMA 9/15 Scalping
│   ├── breakout_consolidation/     # Volume-confirmed Breakouts
│   ├── trend_following_supertrend/ # Supertrend Follower
│   ├── option_buying_vwap_ema/     # Options Scalper (VWAP+EMA9)
│   ├── gap_fill/                   # Gap Reversion Strategy
│   ├── pivot_points/               # Pivot Level Bounces (S1/R1)
│   ├── golden_cross/               # EMA 50/200 Long-term Trend
│   ├── candlestick_patterns/       # Price Action Reversals
│   ├── bollinger_band_squeeze/     # Volatility Breakout
│   └── sample_sma_crossover/       # Example strategy plugin
│       ├── metadata.json
│       ├── strategy.py
│       ├── config.yaml
│       └── backtest.py
├── tests/
│   ├── test_broker.py
│   ├── test_llm.py
│   ├── test_strategy.py
│   ├── test_risk.py
│   └── test_regime.py
├── .env.example
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── pytest.ini
├── requirements.txt
└── README.md
```

---

## 🚀 Quick Start

### 1. Clone & Setup Environment

```bash
cd trading_platform

# Create virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
# Copy the sample env file
copy .env.example .env       # Windows
# cp .env.example .env       # macOS/Linux

# Edit .env with your credentials
# At minimum, set:
#   DHAN_CLIENT_ID and DHAN_ACCESS_TOKEN (for broker)
#   One LLM API key (OPENAI_API_KEY, ANTHROPIC_API_KEY, etc.)
```

### 3. Run the Platform

```bash
# Development mode (with auto-reload)
python -m app.main

# Or directly with uvicorn
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. Open Dashboard

Navigate to **http://localhost:8000** in your browser.

### 5. Run Tests

```bash
pytest -v
```

---

## 🐳 Docker

```bash
# Build and run
docker-compose up --build

# With local Ollama LLM
docker-compose --profile local-llm up --build
```

---

## 🔑 API Endpoints

### Broker
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/broker/status` | Check broker connectivity |
| GET | `/api/broker/holdings` | Get current holdings |
| GET | `/api/broker/positions` | Get open positions |
| GET | `/api/broker/funds` | Get fund details |
| GET | `/api/broker/orders` | Get order history |
| POST | `/api/broker/order` | Place an order |
| PUT | `/api/broker/order` | Modify an order |
| DELETE | `/api/broker/order/{id}` | Cancel an order |

### Trading
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/trading/mode` | Get current mode (paper/live) |
| POST | `/api/trading/mode/{mode}` | Switch trading mode |
| POST | `/api/trading/order` | Execute order (paper or live) |
| GET | `/api/trading/positions` | Get positions (mode-aware) |
| GET | `/api/trading/pnl` | Get daily P&L |
| GET | `/api/trading/risk-status` | View risk control settings |
| GET | `/api/trading/audit` | Get audit trail |

### Strategies
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/strategies/` | List all plugins |
| POST | `/api/strategies/load` | Load all approved plugins |
| POST | `/api/strategies/run/{name}` | Run a specific strategy |

### Discovery
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/discovery/search` | Search GitHub for strategies |
| GET | `/api/discovery/candidates` | List discovered candidates |
| POST | `/api/discovery/candidates/{repo}/review` | Mark as reviewed |
| POST | `/api/discovery/candidates/{repo}/approve` | Approve for conversion |

---

## 🔒 Safety & Security

### Hard Constraints
- **Default mode is PAPER** — live trading requires explicit opt-in via `TRADING_MODE=live`
- **All LLM outputs are validated** — decisions are parsed into strict Pydantic schemas before any action
- **Risk controls are non-bypassable** — every order passes through 8 risk checks
- **GitHub code is NEVER executed** — discovered strategies are analyzed statically and scored
- **Manual approval required** — candidate strategies must be manually reviewed, approved, and converted to internal plugin format

### Risk Controls
| Control | Default | Setting |
|---------|---------|---------|
| Max daily loss | ₹5,000 | `MAX_LOSS_PER_DAY` |
| Max order size | ₹1,00,000 | `MAX_ORDER_SIZE` |
| Max open positions | 10 | `MAX_OPEN_POSITIONS` |
| Trading hours | 09:15-15:30 IST | `ALLOWED_TRADING_*` |
| Cooldown between trades | 30s | `COOLDOWN_BETWEEN_TRADES_SECONDS` |
| Mandatory stop loss | 2% | `MANDATORY_STOP_LOSS_PERCENT` |

---

## 🔌 Creating a Strategy Plugin

Create a new folder in `/plugins/` with these files:

### `metadata.json`
```json
{
    "name": "My Strategy",
    "version": "1.0.0",
    "author": "Your Name",
    "description": "What this strategy does",
    "tags": ["momentum", "intraday"],
    "supported_exchanges": ["NSE_EQ"],
    "timeframe": "5m",
    "status": "approved"
}
```

### `strategy.py`
```python
from app.strategies.engine import BaseStrategy
from app.models.schemas import MarketRegime, StrategySignal

class MyStrategy(BaseStrategy):
    async def evaluate(self, market_data, indicators, regime, positions=None):
        signals = []
        # Your trading logic here
        return signals
```

### `config.yaml`
```yaml
enabled: true
symbols:
  - RELIANCE
  - TCS
parameters:
  lookback: 20
```

> **Note:** Set `"status": "approved"` in metadata.json to allow loading. Strategies with `"candidate"` status are intentionally blocked from execution.

---

## 🤖 LLM Configuration

Set `ACTIVE_LLM` in `.env` to switch between providers:

| Provider | Value | Required Key |
|----------|-------|-------------|
| OpenAI ChatGPT | `openai` | `OPENAI_API_KEY` |
| Anthropic Claude | `anthropic` | `ANTHROPIC_API_KEY` |
| Google Gemini | `gemini` | `GEMINI_API_KEY` |
| Ollama (local) | `ollama` | None (run Ollama locally) |

All LLM adapters return the same strict JSON schema (`LLMDecision`), making them interchangeable.

---

## 📊 Database

- **Default:** SQLite (zero-config, file-based)
- **Production:** Change `DATABASE_URL` to PostgreSQL:
  ```
  DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/trading_db
  ```
  Add `asyncpg` to requirements and the schema works as-is.

---

## 📝 License

This project is for educational and research purposes. Use at your own risk. Always paper-trade first.

> **⚠ Disclaimer:** Algorithmic trading involves significant financial risk. This platform is a development tool, not financial advice. Test thoroughly in paper mode before considering any live deployment.
