# ETHUSDT Quantitative Research & Signal Platform

A reproducible, auditable, and extensible quantitative trading research platform for Binance USDⓈ-M ETHUSDT Perpetual Futures.

---

## Non-Negotiable Research Principles
1. **Zero User Data Dependency**: Data is fetched and verified directly from authoritative Binance public archives (`data.binance.vision`) and REST APIs.
2. **Deterministic & Causal**: Strict availability timestamps and causal resampling prevent lookahead bias.
3. **Permanent Research Memory**: Every experiment is indexed in a persistent Research Ledger. Negative outcomes and rejected hypotheses are permanently retained.
4. **Realistic Execution & Friction**: Explicit maker/taker fee schedules, slippage modeling, and conservative intrabar ambiguity handling.
5. **Colab-First & VPS-Ready**: Identical domain code runs in Google Colab notebooks, local terminals, and future 24/7 server environments.

---

## Directory Structure

```
eth-quant-platform/
├── notebooks/
│   ├── 00_SETUP_AND_DATA.ipynb          # Environment, hardware & Binance data bootstrap
│   ├── 01_RESEARCH_AND_BACKTEST.ipynb   # Strategy research, causal features & backtest
│   ├── 02_OPTIMIZATION_AND_ML.ipynb     # Walk-forward, ablation & ML (Milestone 2)
│   └── 03_LIVE_SHADOW.ipynb             # Live paper trading & Telegram (Milestone 3)
├── src/quant_platform/
│   ├── config/                          # Typed settings & system constants
│   ├── domain/                          # Immutable domain models (Klines, Signals, Trades)
│   ├── data/                            # Public archive ingestion, canonical Parquet, manifest
│   ├── features/                        # Polars indicators & causal swing high/low engine
│   ├── strategies/                      # Baseline catalog (EMA Trend, RSI Reversion, Breakout)
│   ├── risk/                            # Structural invalidation, ATR stops, position sizing
│   ├── backtest/                        # Event-aware backtester, trade ledger, quant metrics
│   ├── research/                        # Permanent Research Ledger, MLflow, HTML reporting
│   ├── colab/                           # Drive sync, hardware detection, safe git sync
│   └── cli/                             # CLI commands (`quant doctor`, `quant data`, etc.)
├── docs/                                # Architecture Decision Records (ADRs) & Specs
├── research/                            # Knowledge base, rejected hypotheses, open questions
└── tests/                               # Full test suite (unit, causality, golden regression)
```

---

## Quickstart

### 1. Installation
```bash
pip install -e ".[dev]"
```

### 2. Run Diagnostics
```bash
quant doctor
```

### 3. Fetch Historical Data & Build Manifest
```bash
quant data fetch --symbol ETHUSDT --timeframe 1m --year 2024 --month 1
quant data verify --symbol ETHUSDT --timeframe 1m
quant data manifest --symbol ETHUSDT --timeframe 1m
```

### 4. Execute a Baseline Backtest
```bash
quant backtest run --strategy-name ema_trend --timeframe 15m
```

### 5. Inspect Research Ledger
```bash
quant research list
```

### 6. Run Test Suite
```bash
pytest -v --cov=quant_platform tests/
```
