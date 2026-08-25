# Project State & Architecture Status

**Platform**: ETHUSDT Quantitative Research & Signal Platform  
**Current Milestone**: Milestone 1 (Foundation & Baseline Vertical Slice)  
**Execution Policy**: `NO_REAL_MONEY` (Research + Backtesting + Live Shadow)  
**Market**: Binance USDⓈ-M Futures `BINANCE_USDM_PERPETUAL:ETHUSDT` (Canonical 1m)  

---

## 1. What Works (Milestone 1 Complete)
- **Data Engine**:
  - `BinancePublicArchiveProvider`: Downloads official monthly/daily ZIP archives from `data.binance.vision` with SHA-256 verification and atomic renaming.
  - `BinanceFuturesRestProvider`: Queries `/fapi/v1/klines` for incremental updates and gap repairs.
  - `CanonicalStorage`: Partitioned Parquet reader/writer (`year=YYYY/month=MM/*.parquet`).
  - `DataIntegrityValidator`: Detects missing timestamps, duplicates, irregular step sizes, impossible OHLC relationships, and negative volumes.
  - `DatasetManifestManager`: Computes cryptographic SHA-256 dataset fingerprints and generates immutable JSON manifests.
  - `CausalResampler`: Resamples 1m data to 3m, 5m, 15m, 30m, 1h, 2h, 4h, 1d, 1w with explicit `available_at_ms` timestamps.
- **Feature Engine**:
  - Vectorized indicators in Polars (SMA, EMA, WMA, HMA, RSI, Stochastic, MACD, ATR, Bollinger Bands, Realized Volatility, Volume Z-Score, RVOL, OBV).
  - `CausalSwingEngine`: Detects fractal pivot highs/lows with lookback $L$ and lookahead $R$, confirming points strictly at bar $i + R$ (zero lookahead).
  - `FeatureCatalog`: Machine-readable metadata and causality statuses.
- **Strategy & Risk**:
  - `BaseStrategy` & `StrategyCatalog`.
  - Baseline strategies: `EmaTrendStrategy`, `RsiMeanReversionStrategy`, `BreakoutSanityStrategy`, `RandomSanityBaseline`.
  - `RiskEngine`: Structural stop/target validation, minimum R:R enforcement, and `NO_TRADE` gating.
  - `PositionSizer`: Fixed notional, fixed % risk, and volatility-adjusted sizing.
- **Backtesting & Research**:
  - `BacktestEngine`: Event-aware backtester with bar $t$ signal $\to$ bar $t+1$ fill, maker/taker fee accounting, slippage, and conservative intrabar ambiguity handling.
  - `MetricCalculator`: Calculates Sharpe, Sortino, Calmar, profit factor, max drawdown, expectancy, R-multiples, MFE/MAE, long/short win rates.
  - `ResearchLedger`: Persistent JSON store with unique experiment IDs (`EXP-YYYYMMDD-...`), duplicate detection, and indexing.
  - `ReportGenerator`: Standalone HTML and JSON reports.
  - `MLflowAdapter`: Standardized run tracking.
- **Colab & CLI**:
  - `00_SETUP_AND_DATA.ipynb` & `01_RESEARCH_AND_BACKTEST.ipynb`.
  - `quant doctor`, `quant data`, `quant backtest`, `quant research`.
  - `DrivePersistenceManager`, `SafeGitSync`, `ResourceDetector`.

---

## 2. Incomplete Modules (Next Milestones)
- **Milestone 2**:
  - Extended SMC features (Fair Value Gaps, Order Blocks, Liquidity Sweeps, CHoCH/MSS, Equal Highs/Lows).
  - Causal Market Regime Engine (Trend, Range, Volatility, Liquidity expansion).
  - Multi-timeframe confluence engine.
  - Walk-forward temporal validation and Optuna parameter optimization.
  - Feature ablation framework.
  - Machine learning expectancy models (LightGBM/CatBoost).
  - `02_OPTIMIZATION_AND_ML.ipynb`.
- **Milestone 3**:
  - Live Binance Futures WebSocket stream.
  - Live feature calculation & historical/live parity checks.
  - Shadow paper trading portfolio.
  - Telegram bot signal notifications.
  - Signal replay audit system.
  - `03_LIVE_SHADOW.ipynb`.
- **Milestone 4**:
  - Derivatives context (Funding rate z-scores, Open Interest, Liquidations, Basis).
  - Order flow / CVD / Aggregated trades.

---

## 3. Important Commands
- Run diagnostics: `quant doctor`
- Run data verification: `quant data verify`
- Run baseline backtest: `quant backtest run --strategy-name ema_trend --timeframe 15m`
- Run pytest suite: `pytest -v --cov=quant_platform tests/`

---

## 4. Latest Validated Baseline Experiment
- **ID**: `EXP-BASELINE-001`
- **Strategy**: `baseline:ema_trend:v1`
- **Status**: Registered in ledger as baseline benchmark.
- **Next Task**: Implement Milestone 2 SMC feature suite (FVG, Liquidity sweeps, Order Blocks) and walk-forward optimization framework.
