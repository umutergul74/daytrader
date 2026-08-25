# Project State: ETHUSDT Quantitative Research Platform

## Current Milestone: Milestone 3 Completed (Live Shadow / Paper Platform & Parity Engine)

### Architecture Overview
1. **Data Layer**:
   - `BinancePublicArchiveProvider`: Official Binance USDⓈ-M historical 1m kline archive downloader with SHA-256 `.CHECKSUM` verification.
   - `BinanceFuturesRestProvider`: Incremental live REST updates and gap repairing.
   - `CanonicalStorage`: Partitioned Hive Parquet storage (`year=YYYY/month=MM/`).
   - `DataIntegrityValidator`: Duplicate, gap, negative volume, and impossible OHLC geometry validator.
   - `DatasetManifestManager`: Immutable dataset SHA-256 fingerprinting.
   - `CausalResampler`: Multi-timeframe generator with explicit `available_at_ms = close_time + 1`.
   - `MultiTimeframeAligner`: Causal backward matching with zero lookahead leakage assertions.
2. **Feature & Market Structure Engines**:
   - Vectorized Polars indicators: SMA, EMA, WMA, HMA, VWMA, EMA slope, MA distance, Supertrend, ADX/DMI, Aroon, RSI, MACD, Stochastic, Stoch RSI, ROC, Momentum, CCI, Williams %R, MFI, ATR, nATR, Bollinger Bands, Keltner, Donchian, Realized Vol, Volatility Percentiles, CMF, Volume Z-Score, RVOL, OBV, Taker Buy Ratios, Volume Expansion.
   - `CausalSwingEngine`: Fractal swings with left/right confirmation delay.
   - `MarketStructureEngine`: Sequence tracking (HH, HL, LH, LL), BOS (by Wick and Close), CHoCH, MSS, and dynamic ATR swings.
   - `FvgEngine`: 3-candle Fair Value Gap detection, 50% Consequent Encroachment (CE), partial/full mitigation states.
   - `DisplacementEngine`: Quantitative displacement metrics (body/range, range/ATR, RVOL).
   - `LiquidityEngine`: EQH/EQL clusters, Liquidity Sweeps, Previous Day/Week levels (PDH/PDL, PWH/PWL), and Dealing Ranges.
   - `MarketRegimeEngine`: Causal 3D classification (Direction, State, Volatility).
   - `TimeSessionEngine`: UTC-aligned session and temporal features.
   - `FeatureCatalog`: Evidence-aware lifecycle registry.
3. **Strategy & Risk Systems**:
   - Baselines: `EmaTrendStrategy`, `RsiMeanReversionStrategy`, `BreakoutSanityStrategy`, `RandomSanityBaseline`.
   - Advanced: `StructureContinuationStrategy`, `LiquiditySweepReversalStrategy`, `LiquiditySweepFVGStrategy`, `FvgTrendContinuationStrategy`, `RegimeAwareMeanReversionStrategy`.
   - `RiskEngine`: Structural stop/target candidate evaluation, minimum R:R gating ($\ge 1.5$), `NO_TRADE` gating.
   - `PositionSizer`: Fixed notional, fixed risk %, and step-size rounding.
4. **Validation, Robustness & Optimization Engines**:
   - `BacktestEngine`: Event-aware execution, maker/taker fee modeling (0.02% / 0.05%), slippage (2 bps), intrabar MFE/MAE tracking, conservative intrabar ambiguity handling.
   - `AblationEngine`: Marginal feature contribution analysis.
   - `WalkForwardEngine`: Anchored and rolling out-of-sample multi-fold evaluator.
   - `RobustnessEngine`: Fee (+25%, +50%), slippage (+50%, +100%), concentration, and Monte Carlo bootstrap stress testing.
   - `OptunaOptimizer`: Persistent SQLite/Drive study management with guarded multi-objective evaluation.
5. **Live Shadow, Replay & Parity Systems (Milestone 3)**:
   - `LiveStateEngine`: Rolling multi-timeframe candle buffer with causal $+1$ms close-time recalculation.
   - `ParityEngine`: Path A (batch) vs Path B (streaming) mathematical and event parity validator (100% parity verified).
   - `MarketReplayEngine`: Accelerated historical event replayer (e.g. 1 day in 30 seconds).
   - `BinanceFuturesWebSocketClient`: Live 1m kline and mark price stream listener with auto-reconnect.
   - `PaperBroker`: Event-driven paper portfolio simulator (Entry, SL, TP1, TP2, fees, slippage, mark-to-market).
   - `ChampionChallengerCoordinator`: Concurrent multi-strategy tournament coordinator with isolated portfolios.
   - `DecisionLogger`: Structured daily `.jsonl` audit records with explicit `NO_TRADE` reasoning.
   - `DriftMonitor`: Real-time signal frequency and feature drift detector.
   - `TelegramNotifier`: Institutional-grade live shadow signal notification formatter and dispatcher.
   - `notebooks/03_LIVE_SHADOW.ipynb`: Interactive live paper trading and replay dashboard.
   - CLI commands: `quant live parity`, `quant live replay`, `quant live start`.

---

### Verification Summary
- **Total Automated Tests**: 34 / 34 passing (100% success rate).
- **Parity Verification**: 100% feature match between batch backtest and live streaming.
- **Git Commit**: Milestone 3 fully implemented and verified.
