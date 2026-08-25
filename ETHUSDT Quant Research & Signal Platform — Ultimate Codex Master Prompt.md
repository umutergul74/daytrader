# ETHUSDT QUANTITATIVE RESEARCH & SIGNAL PLATFORM
## MASTER ENGINEERING, RESEARCH, DATA, ML, COLAB AND DEVOPS SPECIFICATION

You are the principal quantitative engineer, staff-level software architect, data engineer, ML engineer, research infrastructure engineer, DevOps engineer, and trading-systems engineer responsible for building this project from zero into a professional, long-lived quantitative trading research platform.

This is NOT a toy trading bot.

This is NOT a TradingView indicator script.

This is NOT a notebook full of ad-hoc Python code.

This is NOT an AI that looks at a chart image and guesses LONG or SHORT.

Build a serious, reproducible, auditable, extensible quantitative research and real-time signal platform.

The initial market is:

- Exchange: Binance
- Product: USDⓈ-M Futures
- Instrument: ETHUSDT
- Contract: Perpetual
- Canonical historical timeframe: 1 minute
- Initial operating mode: research + backtesting + live shadow/paper signals
- Initial notification channel: Telegram
- Initial execution policy: NO real-money trading
- Primary interactive research environment: Google Colab
- Persistent code source of truth: GitHub
- Persistent research/data storage: Google Drive
- Future 24/7 runtime: Linux VPS/cloud server

The project must be designed so the exact same domain logic can run:

- in historical backtests
- in Google Colab research
- in live shadow mode
- later on a production Linux server

Do not create separate trading logic for notebooks and production.

---

# 1. THE REAL OBJECTIVE

The objective is NOT:

> predict the next candle perfectly.

The objective is:

> discover, test, validate, preserve, rank and eventually exploit statistically defensible trading edges in ETHUSDT perpetual futures.

The platform must continuously accumulate evidence.

It must remember:

- what was tested
- what worked
- what failed
- why it failed
- which market regimes it worked in
- which parameters were unstable
- which features added value
- which features added no value
- which hypotheses were rejected
- which datasets were used
- which source-code version produced the result

The project should become smarter over time through accumulated evidence.

This does NOT mean uncontrolled self-modification.

This does NOT mean automatically rewriting strategies after every losing trade.

This means disciplined scientific learning.

---

# 2. NON-NEGOTIABLE RESEARCH PRINCIPLES

Design the entire system around:

1. reproducibility
2. causality
3. auditability
4. deterministic computation where possible
5. explicit information-availability timestamps
6. strong typing
7. modular architecture
8. automated testing
9. immutable raw data
10. versioned derived data
11. versioned features
12. versioned strategies
13. versioned models
14. versioned experiment configurations
15. negative results as permanent knowledge
16. strict separation between research and production
17. strict separation between features, strategies and risk
18. strict separation between signals and execution
19. realistic costs
20. out-of-sample validation
21. robust parameter regions instead of fragile optimums
22. NO_TRADE as a valid and often desirable output

Aggressively prevent:

- look-ahead bias
- future leakage
- label leakage
- train/test contamination
- final-holdout contamination
- overfitting
- parameter mining
- selection bias
- unrealistic fills
- unrealistic fees
- unrealistic slippage
- accidental future knowledge in market structure
- accidental use of incomplete higher-timeframe candles
- duplicated experiments
- forgotten failed experiments
- silent assumptions
- fake confidence scores
- false profitability claims

A result that cannot be reproduced is not a valid result.

A concept that cannot be algorithmically specified is not yet a usable feature.

---

# 3. DO NOT ONLY DESIGN — IMPLEMENT

Do not spend the first task merely writing architecture documents.

Inspect the repository.

Initialize it if necessary.

Then implement a working vertical slice.

The first meaningful vertical slice must eventually perform:

Binance historical futures data
→ download
→ verify
→ canonicalize
→ validate
→ build timeframes
→ compute features
→ run strategy
→ risk evaluation
→ backtest
→ metrics
→ experiment registration
→ report generation
→ persistent research memory

Do not leave fake placeholder implementations.

TODOs may exist for future milestones, but current milestone functionality must actually work.

Never fabricate successful test results.

Never fabricate backtest profitability.

Never say something works unless you executed and verified it.

---

# 4. ZERO USER-SUPPLIED MARKET DATA DEPENDENCY

The user will NOT provide historical market datasets.

The project must construct its own authoritative historical data foundation.

No CSV supplied manually by the user should be required.

Initial canonical market:

BINANCE USDⓈ-M FUTURES  
ETHUSDT PERPETUAL  
1-MINUTE CONTRACT KLINES

If this authoritative futures data cannot be acquired:

fail explicitly.

Do NOT silently substitute:

- Binance Spot
- another exchange
- synthetic data
- a local file
- TradingView data

Data acquisition is part of the product.

---

# 5. HISTORICAL DATA ACQUISITION

Build permanent data-provider infrastructure.

Conceptually support:

- BinancePublicArchiveProvider
- BinanceFuturesRestProvider
- BinanceFuturesWebSocketProvider

Strategy code must never call Binance directly.

Research code must never manually download files.

Use provider interfaces.

For bulk history:

prefer official Binance bulk/public historical archives where currently supported.

For:

- recent missing candles
- incremental updates
- gap repair
- spot validation

use official Binance USDⓈ-M Futures APIs.

Before implementing API paths or assumptions:

verify current official Binance documentation.

Do not trust old tutorials when official documentation exists.

---

# 6. REQUIRED CORE DATASETS

Acquire as much authoritative historical coverage as legitimately available.

## Core required

### Contract Klines

ETHUSDT perpetual 1m futures klines.

Preserve:

- open_time
- open
- high
- low
- close
- volume
- close_time
- quote_asset_volume
- number_of_trades
- taker_buy_base_asset_volume
- taker_buy_quote_asset_volume

Preserve additional official fields when useful.

---

## Derivatives context

Acquire when authoritative historical sources exist:

### Mark Price
Prefer 1m where available.

### Index Price
Prefer 1m where available.

### Premium Index
Prefer 1m where available.

### Funding Rate
Preserve exact effective timestamp and rate.

---

# 7. ADVANCED DATASETS

The architecture must support:

- Open Interest
- historical Open Interest statistics
- aggregate trades
- trade-level data
- taker buy/sell flow
- liquidation / forced orders
- long/short ratios where trustworthy
- order-book depth
- bid/ask spread
- order-book imbalance
- live microstructure

But these must NOT block the first research pipeline.

Never fabricate missing historical data.

A feature requiring unavailable data must explicitly become unavailable for that historical interval.

---

# 8. OPEN INTEREST POLICY

Determine actual historical availability from current official sources.

Never assume full history exists.

Do not:

- forward-fill years of missing OI
- reconstruct fake OI
- substitute another unrelated metric

Every dataset gets an availability range.

Experiments requiring OI can only run where OI coverage is sufficient.

---

# 9. AGGTRADES POLICY

Support selective aggregate-trade acquisition.

Do not necessarily download every historical trade from the entire history during the first bootstrap.

Provide commands conceptually similar to:

`quant data fetch aggtrades ETHUSDT --from DATE --to DATE`

This allows richer order-flow research only when justified.

---

# 10. DATA STORAGE

Google Drive is persistent backing storage.

Colab `/content` is active high-performance workspace.

Recommended Drive root:

`/content/drive/MyDrive/ETHQuantPlatform/`

Conceptual layout:

ETHQuantPlatform/
    data/
        raw/
        canonical/
        manifests/
    research/
        ledger/
        experiments/
        checkpoints/
        rejected/
    ml/
        studies/
        checkpoints/
        models/
    reports/
    runtime/
        recovery/
    exports/

Raw data is immutable.

Never mutate verified source archives.

Use Parquet for canonical analytical data.

---

# 11. CANONICAL DATA STRUCTURE

Use UTC internally everywhere.

Suggested canonical layout:

`data/canonical/market=binance_usdm/symbol=ETHUSDT/dataset=contract_klines/timeframe=1m/year=YYYY/month=MM/*.parquet`

Similar namespaces should exist for:

- mark price
- index price
- premium index
- funding
- aggregate trades
- OI
- liquidations

Use explicit market identity.

Never represent the instrument merely as:

`ETHUSDT`

Use identities conceptually equivalent to:

`BINANCE_USDM_PERPETUAL:ETHUSDT`

---

# 12. DOWNLOAD ENGINEERING

Downloads must be:

- resumable
- idempotent
- retry-safe
- interruption-safe
- rate-limit-aware
- checksum-aware
- observable

Use temporary files:

`.part`

Only atomically rename after validation.

Verify official checksums when available.

Calculate internal SHA-256 fingerprints.

Never ingest corrupted archives.

---

# 13. DATASET MANIFEST

Every canonical dataset state requires an immutable identity.

Manifest must include:

- dataset_id
- schema_version
- provider
- market
- symbol
- contract_type
- dataset_type
- timeframe
- first timestamp
- last timestamp
- row count
- partition count
- source files
- source checksums
- canonical fingerprint
- duplicate count
- gap count
- unresolved gaps
- validation warnings
- build timestamp

Every experiment must reference a concrete dataset fingerprint.

Never record:

`used ETHUSDT data`

Record exact immutable dataset identity.

---

# 14. GAP DETECTION

For 1-minute data construct the expected time sequence.

Detect:

- missing minutes
- duplicates
- overlapping archives
- out-of-order timestamps
- malformed records
- impossible OHLC relationships
- negative volume
- invalid prices

Gap recovery:

official archive
→ official REST repair
→ validation
→ unresolved-gap record

Never silently generate synthetic candles.

---

# 15. HIGHER TIMEFRAMES

1-minute futures contract klines are canonical.

Generate internally:

- 3m
- 5m
- 15m
- 30m
- 1h
- 2h
- 4h
- 6h
- 12h
- 1d
- 1w

Rules:

- open = first
- high = max
- low = min
- close = last
- volume = sum

Use UTC-calendar alignment.

Write automated tests comparing selected internally generated candles against official higher-timeframe Binance candles.

Most importantly:

an incomplete higher-timeframe candle must NEVER leak into a lower-timeframe strategy.

A 1H candle that closes at 13:00 is not known at 12:45.

---

# 16. COLAB-FIRST OPERATING MODEL

Google Colab is the main research workstation.

Google Colab is NOT the final 24/7 server.

Responsibilities:

## GitHub

authoritative code history

## Google Drive

persistent:

- datasets
- research memory
- reports
- checkpoints
- model artifacts

## `/content`

temporary high-speed working environment

## Binance

authoritative market data

## Future VPS

24/7 shadow/live signal service

---

# 17. COLAB RUNTIME POLICY

Never assume T4 is available.

Detect:

- Colab
- Python
- CPU
- RAM
- disk
- GPU
- GPU model
- CUDA
- PyTorch CUDA

Support gracefully:

- CPU only
- T4
- other CUDA GPU

Do not consume GPU unnecessarily.

Most:

- Polars
- Parquet
- indicators
- FVG
- structure
- backtesting

will usually be CPU workloads.

Use GPU intentionally for suitable ML workloads.

---

# 18. COLAB IS EPHEMERAL

Assume runtime can disappear at any time.

Therefore:

important state must survive.

At important milestones persist:

- experiment state
- dataset manifests
- research ledger
- Optuna study
- model checkpoint
- reports
- trade ledger

A successful experiment is not complete until persistent storage succeeds.

---

# 19. ONLY FOUR NOTEBOOKS

Do NOT create ten fragmented notebooks.

Create exactly four primary user-facing Colab notebooks.

## `00_SETUP_AND_DATA.ipynb`

Responsibilities:

- mount Drive
- secure secrets
- clone repo if missing
- safe Git pull if repo exists
- install/update dependencies
- detect hardware
- restore persistent research state
- inspect dataset status
- initial Binance historical bootstrap if needed
- incremental market-data update
- checksum validation
- gap detection
- canonicalization
- higher-timeframe generation
- dataset fingerprint
- `quant doctor`

End with:

`SYSTEM_READY`

---

## `01_RESEARCH_AND_BACKTEST.ipynb`

This is the main research notebook.

Supported modes:

- DATA_AUDIT
- FEATURE_VALIDATION
- BASELINE
- STRATEGY_RESEARCH
- EXPERIMENT_COMPARE

Use this notebook for:

- data inspection
- indicator research
- ICT/SMC visual validation
- market-structure validation
- strategy backtests
- experiment comparison
- feature ablation previews
- research-ledger inspection

This notebook should be the user's main workspace.

---

## `02_OPTIMIZATION_AND_ML.ipynb`

Supported modes:

- WALK_FORWARD
- ROBUSTNESS
- ABLATION
- OPTUNA
- ML_TRAIN
- ML_EVALUATE

Responsibilities:

- walk-forward analysis
- temporal validation
- parameter search
- robustness
- cost sensitivity
- parameter sensitivity
- feature ablation
- model training
- calibration
- model evaluation

GPU may be used when appropriate.

---

## `03_LIVE_SHADOW.ipynb`

Responsibilities:

- connect to Binance Futures live streams
- consume finalized candles
- update features
- evaluate strategies
- run risk engine
- generate paper signals
- simulate trades
- send Telegram alerts
- record signal/trade state
- test reconnect logic
- test live/backtest parity

This is only an interactive shadow-test environment.

It is NOT the permanent 24/7 runtime.

---

# 20. NOTEBOOKS ARE CONTROLLERS, NOT CODEBASES

Real implementation must live in:

`src/quant_platform/...`

Do NOT put hundreds of lines of:

- indicators
- FVG logic
- backtest engine
- strategy logic
- risk logic

inside notebook cells.

Notebook cells should primarily:

- configure
- call package APIs
- invoke CLI
- display results

Example conceptual usage:

```python
ctx = bootstrap_environment()
result = run_experiment(config)
display_report(result)
```

---

# 21. SAFE GITHUB SYNCHRONIZATION

Each notebook may expose a shared `Pull Latest Code` action.

Implementation:

if repo absent:
    clone

else:
    inspect working tree

if clean:
    fetch
    pull --ff-only

if dirty:
    abort synchronization
    show changed files

Never automatically execute:

- reset --hard
- force checkout
- force push
- history rewriting

Never overwrite local changes silently.

Once an experiment starts:

pin:

- Git branch
- Git SHA
- dirty-state fingerprint

Do not pull code during an active canonical experiment.

---

# 22. GITHUB AUTH

If public repository:

no authentication needed for read operations.

If private:

use Colab Secrets.

Never store GitHub tokens in:

- notebooks
- source
- `.env` committed to Git
- Drive plaintext files
- logs
- outputs

Prefer minimum-permission credentials.

---

# 23. PROJECT SOURCE STRUCTURE

Use a modern `src/` layout.

A strong starting point:

eth-quant-platform/
    notebooks/
        00_SETUP_AND_DATA.ipynb
        01_RESEARCH_AND_BACKTEST.ipynb
        02_OPTIMIZATION_AND_ML.ipynb
        03_LIVE_SHADOW.ipynb

    src/
        quant_platform/
            config/
            domain/
            data/
            datasets/
            features/
            indicators/
            structure/
            smc/
            liquidity/
            regimes/
            derivatives/
            orderflow/
            strategies/
            signals/
            risk/
            portfolio/
            backtest/
            research/
            optimization/
            ml/
            live/
            exchange/
            notifications/
            persistence/
            observability/
            colab/
            cli/

    tests/
    docs/
    research/
    scripts/
    pyproject.toml
    uv.lock
    README.md
    PROJECT_STATE.md

Do not force this exact structure if a better professional design emerges.

Avoid giant generic `utils.py` modules.

---

# 24. MODERN ENGINEERING STACK

Use current actively maintained technologies.

Before pinning versions:

verify current compatibility and official documentation.

Preferred direction:

## Language

Newest well-supported Python version compatible with required libraries.

## Package management

- pyproject.toml
- uv
- dependency lock

## Data

- Polars
- PyArrow
- Parquet
- DuckDB

## Validation/config

- Pydantic v2
- typed settings

## API

- FastAPI

## Networking

- httpx
- robust async WebSocket client

## Persistence

- SQLite permitted for lightweight Colab research
- PostgreSQL for server deployment
- TimescaleDB where beneficial

## Experiment tracking

- MLflow

## Data lineage/versioning

- DVC where useful
- immutable dataset manifests regardless of DVC availability

## Optimization

- Optuna

## ML

- scikit-learn
- LightGBM
- XGBoost
- CatBoost
- PyTorch only when justified

## Testing

- pytest
- pytest-cov
- hypothesis where useful

## Quality

- Ruff
- strict static typing
- pre-commit

Do not add infrastructure purely for prestige.

---

# 25. PROFESSIONAL GIT WORKFLOW

If not already a Git repo:

initialize Git.

Create professional `.gitignore`.

Never commit:

- secrets
- data archives
- canonical market datasets
- local databases
- model binaries unless intentionally versioned externally
- caches
- giant generated reports
- notebook secrets

Use conventional commit style where practical:

- feat:
- fix:
- test:
- refactor:
- docs:
- perf:
- chore:
- ci:

Git is code history.

Git is NOT experiment memory.

Do not create one Git commit per backtest.

---

# 26. PERMANENT RESEARCH MEMORY

This is one of the most important requirements.

Build a Research Ledger.

The platform must NEVER rely on the user's memory.

Every serious experiment receives a unique ID.

Example:

`EXP-20260824-233100-a72bf9`

Record:

- experiment ID
- hypothesis
- experiment type
- status
- strategy ID/version
- feature-set version
- parameters
- parameter hash
- dataset fingerprint
- date ranges
- train range
- validation range
- test range
- walk-forward settings
- Git SHA
- dirty state
- dependency fingerprint
- random seed
- costs
- slippage
- funding assumptions
- execution model
- risk model
- metrics
- trade count
- regime metrics
- warnings
- leakage warnings
- artifacts
- conclusion
- lessons learned
- rejection reason
- recommended next experiment
- parent experiments
- related experiments

---

# 27. EXPERIMENT STATUSES

Support at least:

- proposed
- running
- interrupted
- completed
- rejected
- inconclusive
- candidate
- validated
- shadow
- deprecated
- invalid_due_to_leakage
- invalid_due_to_data
- invalid_due_to_execution_assumption

Never delete failed experiments.

Never overwrite them.

---

# 28. RESEARCH KNOWLEDGE BASE

Maintain human-readable summaries:

`research/KNOWLEDGE_BASE.md`

`research/REJECTED_HYPOTHESES.md`

`research/OPEN_QUESTIONS.md`

But structured Research Ledger remains source of truth.

Before running a serious experiment:

search for identical or similar experiments.

If identical:

avoid duplication unless intentionally rerun.

If rerun:

record why.

---

# 29. EXPERIMENT IDENTITY

Conceptually:

Git SHA
+
dataset fingerprint
+
feature versions
+
strategy version
+
parameters
+
cost assumptions
+
time split
+
random seed
=
experiment identity

Detect exact duplicates automatically.

---

# 30. PROJECT STATE FOR FUTURE CODEX SESSIONS

Maintain:

`PROJECT_STATE.md`

It must always summarize:

- current architecture
- what works
- current milestone
- incomplete modules
- current blockers
- important commands
- latest validated experiment
- current strategy candidates
- known rejected ideas
- next recommended engineering task

A future Codex session must read:

- PROJECT_STATE.md
- relevant ADRs
- research summaries

before making major architectural changes.

---

# 31. ARCHITECTURE DECISION RECORDS

Create:

`docs/adr/`

Record important decisions such as:

- Colab-first research
- Google Drive persistence
- 1m canonical timeframe
- Polars choice
- Research Ledger architecture
- MLflow use
- no-real-money policy
- backtest execution model
- feature availability semantics

Do not let major architecture silently change.

---

# 32. STRATEGY & FEATURE KNOWLEDGE UNIVERSE

Do NOT limit research to:

- RSI
- MACD
- FVG

Maintain an extensible catalog of trading concepts.

Every concept must pass through a lifecycle:

DISCOVERED
→ SPECIFIED
→ IMPLEMENTED
→ UNIT_TESTED
→ CAUSALITY_TESTED
→ BACKTESTED
→ ROBUSTNESS_TESTED
→ ACCEPTED / REJECTED / INCONCLUSIVE

Never automatically assume a popular concept has edge.

---

# 33. TECHNICAL INDICATOR UNIVERSE

Support research into at least these families.

## Moving averages / trend

- SMA
- EMA
- WMA
- HMA
- VWMA
- moving-average slopes
- MA distance
- MA spreads
- ADX
- DMI
- Aroon
- Supertrend
- Parabolic SAR
- Ichimoku components

## Momentum

- RSI
- Stochastic
- Stochastic RSI
- MACD
- MACD histogram
- ROC
- Momentum
- CCI
- Williams %R
- MFI

## Volatility

- ATR
- normalized ATR
- realized volatility
- Bollinger Bands
- Bollinger bandwidth
- Keltner Channels
- Donchian Channels
- volatility percentiles
- rolling return volatility
- range expansion/contraction

## Volume

- raw volume
- relative volume
- volume z-score
- OBV
- CMF
- MFI
- VWAP
- Anchored VWAP where formally defined
- taker-buy ratios

Do not dump every indicator into one model.

Test incremental value.

---

# 34. PRICE ACTION UNIVERSE

Research mathematically defined versions of:

- support/resistance
- breakout
- failed breakout
- retest
- trend pullback
- range breakout
- range rejection
- momentum breakout
- compression
- expansion
- volatility contraction
- volatility expansion
- inside bar
- outside bar
- pin-bar-like structures
- engulfing structures
- doji-like structures
- multi-candle patterns

Candlestick names are not truths.

They are hypotheses.

---

# 35. MARKET STRUCTURE ENGINE

Create a dedicated subsystem.

Research:

- swing high
- swing low
- HH
- HL
- LH
- LL
- bullish structure
- bearish structure
- range structure
- Break of Structure
- Change of Character
- Market Structure Shift
- structural invalidation

Swing detection must be causal.

If N future candles are required to confirm a swing:

knowledge becomes available only after those candles exist.

Never back-date the information.

---

# 36. ICT / SMART MONEY / SMC KNOWLEDGE UNIVERSE

Research formal definitions of:

- Fair Value Gap
- bullish FVG
- bearish FVG
- partially filled FVG
- fully mitigated FVG
- inverse/inversion FVG
- displacement
- Break of Structure
- Change of Character
- Market Structure Shift
- equal highs
- equal lows
- buy-side liquidity
- sell-side liquidity
- liquidity sweep
- liquidity grab
- liquidity void
- Order Block
- Breaker Block
- Mitigation Block
- Rejection Block
- Propulsion Block
- inducement
- premium
- discount
- equilibrium
- dealing range
- internal range liquidity
- external range liquidity
- Balanced Price Range
- Consequent Encroachment
- Optimal Trade Entry / OTE
- Power of Three
- accumulation
- manipulation
- distribution
- Judas Swing
- Kill Zones
- session liquidity
- previous day high/low
- previous week high/low
- daily open
- weekly open
- opening range
- discount/premium arrays
- SMT divergence

Do NOT assume internet definitions agree.

For every ambiguous concept:

document exact selected mathematical definition.

Where multiple definitions exist:

version them separately and experimentally compare them.

---

# 37. SMC SPECIFICATION REQUIREMENT

Create:

`docs/quant/SMC_CONCEPTS_SPEC.md`

Every concept must define:

- mathematical conditions
- candle indexing
- required lookback
- confirmation delay
- availability timestamp
- parameters
- edge cases
- invalidation
- synthetic examples
- known ambiguity
- feature version

Words like:

- strong displacement
- important high
- institutional candle
- major liquidity

must never remain undefined.

Translate subjective language into measurable rules.

---

# 38. LIQUIDITY ENGINE

Research proxies including:

- swing highs
- swing lows
- equal highs
- equal lows
- previous day high
- previous day low
- previous week high
- previous week low
- session high
- session low
- clustered highs
- clustered lows
- unmitigated FVG boundaries
- volume-profile areas when available

Use ATR/volatility-relative tolerances where appropriate.

Avoid arbitrary fixed-dollar thresholds.

---

# 39. VOLUME PROFILE UNIVERSE

Add research architecture for:

- Volume Profile
- Point of Control
- Value Area High
- Value Area Low
- High Volume Nodes
- Low Volume Nodes
- Session Volume Profile
- Anchored Volume Profile

Implement only when data resolution supports the claimed interpretation.

Do not pretend OHLCV gives perfect tick-level volume-at-price information.

---

# 40. ORDER FLOW UNIVERSE

When data permits, research:

- Cumulative Volume Delta
- trade delta
- aggressive buy volume
- aggressive sell volume
- trade imbalance
- trade frequency
- average trade size
- large-trade detection
- buy/sell aggressor imbalance
- absorption proxies
- exhaustion proxies
- order-book imbalance
- depth imbalance
- liquidity-wall persistence
- order-book changes

Differentiate:

historically available
vs
live-only

features.

---

# 41. DERIVATIVES UNIVERSE

Research:

- Funding Rate
- funding z-score
- funding momentum
- funding extremes
- time until funding
- time since funding
- Open Interest
- OI change
- OI z-score
- price/OI regimes
- mark/trade divergence
- index/trade divergence
- premium index
- futures basis
- basis z-score
- long/short ratios
- taker buy/sell ratios
- liquidation volume
- long liquidations
- short liquidations
- liquidation imbalance
- liquidation bursts
- leverage-stress proxies

Relationships such as:

Price ↑ + OI ↑  
Price ↑ + OI ↓  
Price ↓ + OI ↑  
Price ↓ + OI ↓

are research hypotheses, not hard-coded truths.

---

# 42. TIME & SESSION FEATURES

Time itself is a feature universe.

Research:

- hour of day
- day of week
- weekend
- Asia session
- London session
- New York session
- session overlaps
- daily open
- weekly open
- previous session range
- opening range
- time since high/low
- time since volatility expansion
- time before/after funding

All timestamps remain UTC internally.

Optional presentation may also show Europe/Istanbul time.

---

# 43. STATISTICAL / QUANT UNIVERSE

Do not restrict the project to discretionary trading concepts.

Research:

- momentum
- time-series momentum
- mean reversion
- trend following
- volatility breakout
- return z-scores
- rolling regressions
- regression channels
- autocorrelation
- volatility clustering
- realized volatility
- change-point detection
- regime-switching models
- Hidden Markov Models
- Kalman-filter approaches
- statistical spread analysis

When multiple assets are later supported, architecture may expand toward:

- cross-sectional momentum
- pairs trading
- cointegration
- statistical arbitrage
- cross-market relative strength

ETHUSDT remains the initial target.

---

# 44. CROSS-MARKET RESEARCH ARCHITECTURE

Prepare future support for relationships such as:

- ETH vs BTC
- ETH futures vs ETH spot
- ETH vs broader crypto market

Potential features:

- relative momentum
- lead/lag
- correlation shifts
- SMT-like divergence
- spread/basis
- volatility divergence

Do not add other assets to V1 unless necessary for an explicit experiment.

---

# 45. FEATURE CATALOG

Maintain a machine-readable Feature Catalog.

Every feature records:

- feature_id
- version
- category
- name
- mathematical definition
- implementation path
- required datasets
- timeframe
- lookback
- available_at_timestamp semantics
- parameters
- expected interpretation
- unit tests
- causality status
- experimental evidence
- known failures
- current status

Examples:

`technical:rsi:v1`

`smc:fvg:v2`

`structure:causal_swing:v3`

`derivatives:funding_zscore:v1`

---

# 46. STRATEGY CATALOG

Every strategy records:

- strategy_id
- version
- hypothesis
- required features
- required datasets
- supported market regimes
- entry rules
- invalidation rules
- stop model
- target model
- maximum holding period
- allowed direction
- contraindications
- current evidence
- current status

Never hide strategy rules inside anonymous notebook cells.

---

# 47. INITIAL STRATEGY FAMILIES

Build simple transparent baselines before sophisticated systems.

Initial baseline families:

- EMA trend
- EMA crossover
- RSI mean reversion
- momentum
- volatility breakout
- simple trend pullback
- random-direction sanity baseline

Then research advanced strategies such as:

- StructureContinuationStrategy
- TrendPullbackStrategy
- LiquiditySweepReversalStrategy
- LiquiditySweepFVGStrategy
- FVGContinuationStrategy
- BreakoutContinuationStrategy
- MeanReversionStrategy
- SessionLiquidityStrategy

No advanced strategy receives credibility before outperforming reasonable baselines in robust OOS evaluation.

---

# 48. MULTI-TIMEFRAME ENGINE

Provide infrastructure such as:

- 4H macro context
- 1H structure
- 15M setup
- 5M entry
- 1M execution refinement

But do not hard-code this as the only valid configuration.

Strategies declare the timeframes they require.

Prevent higher-timeframe leakage.

---

# 49. MARKET REGIME ENGINE

Build a dedicated causal market-regime subsystem.

Possible dimensions:

## Direction

- bullish
- bearish
- neutral

## Structure

- trend
- range
- breakout
- compression

## Volatility

- very low
- low
- normal
- high
- extreme

## Liquidity state

- normal
- sweep
- expansion
- post-liquidation when available

Store every strategy's performance by regime.

Strategies may declare supported regimes.

---

# 50. STRATEGY OUTPUT

Every strategy returns a structured `SignalCandidate`.

Include:

- signal_candidate_id
- strategy_id
- strategy_version
- timestamp
- symbol
- direction
- entry type
- entry zone
- structural invalidation
- stop candidate
- target candidates
- evidence
- contraindications
- market regime
- timeframe context
- feature snapshot
- expiry
- diagnostics

Strategies must NOT:

- send Telegram
- write directly to DB
- execute orders

---

# 51. META / CONFLUENCE ENGINE

Avoid simplistic logic:

RSI + MACD + FVG = trade.

Build a meta-decision layer.

Initially deterministic scoring is acceptable if:

- transparent
- versioned
- configurable
- fully explainable
- empirically validated

Later this may become an ML meta-model.

Outputs:

- LONG
- SHORT
- NO_TRADE

NO_TRADE is a first-class output.

---

# 52. RISK ENGINE

Risk must be separate from alpha.

Evaluate:

- structural invalidation
- ATR/volatility buffer
- minimum stop distance
- maximum stop distance
- logical target candidates
- nearby liquidity
- minimum acceptable reward/risk
- maximum holding period
- signal expiry

Do NOT use:

- blind fixed 1% stop
- forced 1:3 R:R

unless explicitly being tested.

If the logical target does not provide enough reward:

NO_TRADE.

---

# 53. POSITION SIZING

Support:

- fixed notional
- fixed equity fraction
- fixed risk per trade
- volatility-normalized sizing

Keep leverage separate from strategy edge.

Do not make a strategy look good merely by applying high leverage.

---

# 54. BACKTEST ENGINE

Build an event-aware or hybrid professional backtester.

Distinguish:

- signal time
- decision time
- order time
- execution time
- fill time
- position state

Support:

- LONG
- SHORT
- NO_TRADE
- market entries
- architecture for limit entries
- stop loss
- multiple targets
- partial exits architecture
- maximum holding time
- fees
- spread
- slippage
- funding
- position sizing
- signal expiration
- trade rejection

Never assume perfect fills.

---

# 55. INTRABAR AMBIGUITY

OHLC bars do not reveal the exact price path.

If TP and SL are both reachable within the same candle:

do not choose the favorable result.

Implement explicit policies.

Default should be conservative.

If lower timeframe data can causally resolve ambiguity:

use it.

Record:

`intrabar_ambiguity_count`

---

# 56. TRADING COSTS

Support configurable:

- maker fee
- taker fee
- spread
- slippage
- funding
- tick size
- quantity step
- minimum notional
- latency assumptions where relevant

Never hard-code current exchange fees as eternal values.

Cost assumptions must be experiment metadata.

---

# 57. PERFORMANCE METRICS

Calculate at minimum:

- total net return
- gross return
- fees
- funding
- slippage
- number of trades
- win rate
- average winner
- average loser
- payoff ratio
- expectancy
- average R
- median R
- profit factor
- maximum drawdown
- drawdown duration
- Sharpe
- Sortino
- Calmar where meaningful
- exposure
- turnover
- average holding period
- MFE
- MAE
- consecutive wins
- consecutive losses
- long results
- short results
- monthly results
- yearly results
- regime results
- session results
- tail metrics

Always distinguish:

- in-sample
- validation
- out-of-sample
- shadow/live

---

# 58. LOOK-AHEAD DEFENSE

Every feature must define:

`available_at_timestamp`

Examples:

A confirmed pivot cannot appear at its original pivot candle before confirmation.

A 15m FVG cannot be used before the defining candle closes.

A 1h candle is unavailable before 1h close.

A future-derived label is never a feature.

Build synthetic leakage tests.

Fail loudly.

---

# 59. HOLDOUT POLICY

Use chronological splits.

Never use random train/test splitting for normal time-series evaluation.

Support:

- train
- validation
- final holdout
- rolling walk-forward
- anchored walk-forward

Final holdout is sacred.

If a developer repeatedly looks at final-holdout performance and changes strategy accordingly:

mark that holdout contaminated.

Create a new future holdout.

Maintain a holdout-access registry.

---

# 60. ROBUSTNESS

A candidate strategy must face:

- walk-forward testing
- parameter perturbation
- fee sensitivity
- slippage sensitivity
- entry-delay sensitivity
- regime analysis
- subperiod analysis
- trade concentration
- bootstrap confidence intervals where appropriate
- Monte Carlo trade-sequence analysis
- feature ablation
- strategy ablation

Prefer wide robust parameter plateaus over narrow performance spikes.

---

# 61. PARAMETER OPTIMIZATION

Use Optuna where useful.

Persist studies.

Allow resume after Colab disconnect.

Record:

- study ID
- search space
- sampler
- pruner
- seed
- trials
- Git SHA
- dataset fingerprint

Most important rule:

BEST OPTUNA TRIAL != VALIDATED STRATEGY

Never optimize against final holdout.

---

# 62. AUTOMATED RESEARCH LOOP

Build controlled infrastructure for automated experimentation.

The research loop may:

1. read an explicit hypothesis/search space
2. inspect prior experiments
3. avoid duplicates
4. generate configurations
5. run backtests
6. perform robustness checks
7. record results
8. compare baselines
9. summarize findings
10. suggest next experiments

It must NOT automatically promote historical winners to production.

It must NOT autonomously mutate live strategy rules without validation.

---

# 63. WHAT “LEARNING” MEANS

There are three distinct layers.

## Feature Engine

does not learn.

It calculates objective values such as:

- RSI
- ATR
- FVG
- BOS
- OI change

## Research Engine

learns scientifically by accumulating evidence.

Example:

FVG alone:
weak/no edge.

FVG + liquidity sweep:
small improvement.

FVG + sweep + HTF trend:
stronger OOS result.

Adding RSI:
no incremental value.

Extreme positive funding:
reduced long expectancy.

This becomes permanent research memory.

## ML Model

later learns statistical relationships between features and outcomes.

Do not confuse these layers.

---

# 64. MACHINE LEARNING POLICY

Do NOT start with neural networks.

First establish trusted deterministic infrastructure.

Initial model candidates:

- Logistic Regression
- LightGBM
- XGBoost
- CatBoost

Possible targets:

- probability TP occurs before SL
- expected R
- expected favorable excursion
- setup quality
- regime classification

Potential later labeling architecture:

triple-barrier style:

- upper barrier
- lower barrier
- max holding time

Avoid label leakage.

---

# 65. ML FEATURE INPUT EXAMPLE

A future model may consume features such as:

- RSI
- ATR percentile
- FVG size in ATR
- liquidity sweep
- HTF trend
- CHoCH
- funding z-score
- OI change
- taker imbalance
- CVD
- hour of day
- market regime
- distance to target liquidity
- stop distance
- volume anomaly

It may output:

`P(TP before SL)`

or:

`Expected R`

But only after proper calibration and OOS testing.

---

# 66. PROBABILITY CALIBRATION

Do not call arbitrary scores probabilities.

If displaying probability:

evaluate calibration.

Track:

- Brier score
- calibration curve
- reliability

Consider:

- sigmoid/Platt
- isotonic

If not calibrated:

call it `score`.

---

# 67. MODEL REGISTRY

Use model lineage.

Every model traces to:

- model ID
- code version
- dataset version
- feature version
- label version
- training period
- validation period
- experiment
- parameters
- metrics

Lifecycle:

- candidate
- shadow
- champion
- deprecated

Never overwrite model identity.

---

# 68. LIVE MARKET DATA

Use official Binance USD-M Futures interfaces.

Implement:

- WebSocket
- REST recovery
- reconnect
- exponential backoff + jitter
- stale-data detection
- duplicate detection
- timestamp validation
- graceful shutdown
- health reporting

For closed-candle strategies:

only finalized candles trigger decisions.

Live feature computation must match backtest feature computation.

Historical/live parity is mandatory.

---

# 69. LIVE SHADOW TRADING

Before real trading:

run shadow.

Shadow mode:

- reads live market data
- generates signals
- simulates entry
- simulates stop
- simulates target
- applies configured costs
- persists results
- never sends exchange orders

Compare:

historical OOS
vs
live shadow

Detect degradation.

---

# 70. SIGNAL REPLAY

Every emitted live signal must be reproducible.

Persist:

- signal ID
- timestamp
- market snapshot
- feature snapshot
- market structure
- regime
- strategy evidence
- risk decision
- code version
- config version
- dataset/live-state reference

Given a signal ID:

the system should reconstruct why it was emitted.

---

# 71. TELEGRAM

Use Telegram Bot API.

Secrets:

- TELEGRAM_BOT_TOKEN
- TELEGRAM_CHAT_ID

must come from secrets/environment.

Never commit them.

Telegram signal should include:

ETHUSDT — LONG/SHORT

- signal ID
- strategy
- timestamp
- current price
- entry zone
- stop
- TP1/TP2/TP3 when relevant
- R:R
- regime
- score
- calibrated probability if available
- setup expiration
- evidence
- invalidation
- risk notes

Example evidence must come from structured engine output:

- 4H bullish structure
- 15M sell-side sweep
- bullish FVG
- 5M structure shift
- relative volume expansion

Do not generate vague AI explanations unrelated to actual features.

---

# 72. OPERATIONAL TELEGRAM ALERTS

Also support:

- startup
- shutdown
- stale data
- WebSocket disconnect
- persistent reconnect failure
- severe exception
- risk kill switch

Avoid spam.

---

# 73. LLM POLICY

An LLM must NOT be the trading decision engine.

LLMs may later help with:

- research summaries
- experiment comparisons
- human-readable signal explanation
- news classification
- documentation
- hypothesis generation

Trading decisions must remain reproducible without an LLM.

---

# 74. CLI

Build a professional CLI.

Conceptual commands:

`quant doctor`

`quant bootstrap`

`quant data status ETHUSDT`

`quant data update ETHUSDT`

`quant data verify ETHUSDT`

`quant data gaps ETHUSDT`

`quant data manifest ETHUSDT`

`quant features build`

`quant backtest run`

`quant backtest report`

`quant research list`

`quant research show EXP-ID`

`quant research compare EXP-A EXP-B`

`quant research search`

`quant research rejected`

`quant research candidates`

`quant optimization run`

`quant shadow start`

`quant colab status`

`quant colab checkpoint`

`quant colab restore`

Use a modern typed CLI framework where appropriate.

---

# 75. `quant doctor`

Check:

- Python environment
- dependency compatibility
- Git state
- Drive
- persistent root
- disk space
- GPU
- dataset status
- dataset gaps
- Research Ledger
- MLflow
- Binance connectivity
- Telegram configuration
- timestamps/clock sanity

Return a clear readiness summary.

---

# 76. COLAB BOOTSTRAP EXPERIENCE

A fresh Colab session should be recoverable quickly.

Expected flow:

Open notebook
→ mount Drive
→ clone/pull repo
→ install environment
→ restore state
→ inspect data
→ copy necessary data to local cache
→ run research

Do not make every session re-download historical ETHUSDT.

Future updates:

existing Drive dataset
+
new Binance data
→ incremental update

---

# 77. DRIVE I/O

Do not run millions of tiny filesystem operations directly on Drive.

Prefer:

Drive
→ copy relevant partitions to `/content`
→ process locally
→ persist compact results/checkpoints back to Drive

Avoid giant numbers of tiny experiment files.

Use structured storage.

---

# 78. DATABASE SAFETY

If SQLite is used in Colab:

do not treat a live SQLite DB directly mounted on Drive as high-performance transactional storage.

Use:

Drive backup
→ local `/content`
→ operate
→ safe checkpoint/backup
→ persist atomically to Drive

Abstract persistence so PostgreSQL can later replace SQLite.

---

# 79. MLFLOW

Use MLflow for:

- run metadata
- parameters
- metrics
- tags
- artifacts
- code revision
- model lineage

Support local tracking during early Colab research.

Persist necessary state safely.

Allow future migration to server-backed MLflow.

---

# 80. DVC / DATA LINEAGE

Use DVC where beneficial.

But data lineage must work even if DVC remote infrastructure is initially simple.

Always preserve:

- source checksums
- canonical fingerprints
- manifests
- experiment dataset references

Do not commit large datasets to Git.

---

# 81. TESTING

Tests are mandatory.

Create:

## Unit tests

- indicators
- timeframe resampling
- FVG
- market structure
- liquidity
- risk
- fees
- metrics
- position accounting

## Synthetic causality tests

Hand-constructed candle sequences.

## Property tests

Use Hypothesis where beneficial.

## Integration tests

- data ingestion
- Research Ledger
- MLflow adapter
- Binance adapter mocked
- Telegram mocked
- full backtest pipeline

## Regression tests

Every discovered bug should gain a regression test.

---

# 82. GOLDEN BACKTESTS

Create small immutable synthetic datasets with known expected trades.

Backtester behavior must remain deterministic.

Changes to golden results require intentional updates.

---

# 83. OBSERVABILITY

Use structured logs.

Useful context fields:

- experiment_id
- signal_id
- strategy_id
- symbol
- timeframe
- Git SHA

Track metrics such as:

- candles processed
- data lag
- reconnects
- strategy evaluations
- signals
- NO_TRADE counts
- Telegram failures
- backtest runtime
- experiment runtime
- exceptions

---

# 84. ERROR HANDLING

Never use:

`except Exception: pass`

Classify errors:

- temporary network failure
- exchange API error
- data corruption
- configuration error
- strategy bug
- database failure

Retry only where appropriate.

Never silently hide failures.

---

# 85. SECURITY

Initial research/shadow mode must not require Binance trading API credentials.

Public market data only.

Secrets never go to Git.

Future real trading must require explicit safety gates.

Default:

`LIVE_TRADING_ENABLED=false`

Future execution safeguards must include:

- max position size
- max leverage
- daily loss limit
- max simultaneous positions
- stale-data kill switch
- abnormal-volatility guard
- duplicate-order prevention
- reconciliation
- emergency flatten/cancel
- withdrawal permission disabled

Do NOT implement real-money execution in initial milestones.

---

# 86. CI/CD

Create GitHub Actions.

On push/PR run:

- install locked dependencies
- lint
- formatting check
- type checks
- unit tests
- integration tests without production secrets
- coverage

Consider:

- CodeQL
- Dependabot/security update tooling

Never execute live trading in CI.

---

# 87. DOCKER / FUTURE SERVER DEPLOYMENT

Provide production-quality Docker configuration.

Prefer:

- non-root user
- health checks
- graceful shutdown
- locked dependencies
- minimal image

Future VPS deployment should conceptually require:

git clone
→ configure environment
→ sync persistent state/data
→ `quant shadow start`

No strategy rewrite.

---

# 88. REPORTING

Every canonical backtest report should contain:

- experiment ID
- hypothesis
- Git SHA
- dataset fingerprint
- strategy version
- feature versions
- assumptions
- costs
- equity curve
- drawdown
- trade distribution
- R distribution
- MFE/MAE
- monthly returns
- yearly returns
- long vs short
- regime breakdown
- session breakdown
- parameter summary
- warning section
- data-quality summary
- IS/OOS labeling
- conclusion

Generate machine-readable JSON and human-readable report.

---

# 89. RESEARCH CONCENTRATION CHECKS

Detect whether results depend on:

- a tiny number of trades
- one year
- one month
- one regime
- one extreme market event
- one direction

Report this explicitly.

---

# 90. ABLATION

If a strategy uses:

HTF bias
+ FVG
+ liquidity sweep
+ RSI
+ volume
+ CHoCH

test:

- without RSI
- without volume
- without FVG
- without sweep
- without HTF
- without CHoCH

Do not preserve useless components merely because they sound sophisticated.

---

# 91. FEATURE VALUE EVIDENCE

The platform should eventually answer questions such as:

- Does FVG alone add predictive value?
- Does RSI improve FVG setups?
- Does funding improve liquidity-sweep setups?
- Which feature hurts performance?
- Which regime makes a strategy fail?
- Does order-flow confirmation help?
- Does the feature work only because of 2021?
- Does it survive higher fees?
- Does it survive delayed entry?

This evidence must become permanent research memory.

---

# 92. PROMOTION GATES

A strategy cannot become a shadow candidate merely because historical profit is positive.

Promotion gates should consider:

- adequate trade count
- positive expectancy after realistic costs
- acceptable drawdown
- OOS profitability
- walk-forward stability
- parameter robustness
- regime robustness
- no leakage
- realistic execution
- cost sensitivity
- concentration
- reproducibility
- baseline comparison

Failure must be recorded.

---

# 93. FIRST IMPLEMENTATION MILESTONE

Immediately implement a real working foundation.

Milestone 1 must include:

1. Git repository
2. modern Python project
3. src architecture
4. typed configuration
5. GitHub Actions
6. Colab helpers
7. Drive persistence manager
8. safe Git sync
9. resource detector
10. `00_SETUP_AND_DATA.ipynb`
11. Binance historical data acquisition
12. 1m ETHUSDT futures canonical dataset
13. checksum verification
14. gap detection
15. canonical Parquet
16. dataset manifest/fingerprint
17. higher timeframe generation
18. initial technical indicators
19. causal swing engine
20. at least one transparent baseline strategy
21. basic risk engine
22. backtester
23. realistic fees/slippage configuration
24. trade ledger
25. metrics
26. Research Ledger
27. MLflow
28. HTML/JSON report
29. `01_RESEARCH_AND_BACKTEST.ipynb`
30. tests
31. README
32. PROJECT_STATE.md
33. ADRs
34. at least one successfully executed baseline experiment

Do NOT optimize for profitability during this milestone.

Prove correctness first.

---

# 94. SECOND MILESTONE

Implement:

- extended indicator catalog
- market structure
- BOS
- CHoCH
- FVG variants
- equal highs/lows
- liquidity sweeps
- displacement
- regime engine
- multi-timeframe engine
- advanced strategy candidate
- feature catalog
- strategy catalog
- SMC specification
- ablation framework
- walk-forward testing
- robustness testing
- Optuna
- `02_OPTIMIZATION_AND_ML.ipynb`

Every concept follows:

spec
→ test
→ implementation
→ causal validation
→ backtest
→ evidence

---

# 95. THIRD MILESTONE

Implement:

- live Binance Futures stream
- REST recovery
- live feature parity
- shadow portfolio
- live signal engine
- Telegram
- signal replay
- persistent live ledger
- reconnects
- health monitoring
- `03_LIVE_SHADOW.ipynb`

Still no real-money trading.

---

# 96. FOURTH MILESTONE

Extend research with:

- funding
- OI
- premium
- mark/index relationships
- aggregate trades
- order flow
- liquidations
- volume profile
- cross-market features
- ML meta-model
- probability calibration
- model registry

Only introduce deep learning if simpler models fail and evidence justifies it.

---

# 97. DEVELOPMENT BEHAVIOR

When making decisions:

- inspect first
- verify assumptions
- use official documentation
- prefer current supported APIs
- avoid deprecated interfaces
- test before claiming success
- record important decisions
- choose reversible professional defaults
- continue rather than repeatedly asking trivial questions

Do not stop development for minor architectural choices.

Document the choice and continue.

---

# 98. FIRST-RUN CODEX BEHAVIOR

Start now.

Perform this sequence:

1. inspect repository
2. inspect Git state
3. create/update PROJECT_STATE.md
4. define architecture
5. initialize professional Python project
6. build Colab/Drive bootstrap infrastructure
7. create `00_SETUP_AND_DATA.ipynb`
8. implement official Binance Futures historical data acquisition
9. build ETHUSDT perpetual canonical 1m data
10. validate and fingerprint it
11. create timeframe engine
12. create feature framework
13. create baseline strategy
14. create backtest engine
15. create Research Ledger
16. integrate MLflow
17. create `01_RESEARCH_AND_BACKTEST.ipynb`
18. run tests
19. run a baseline experiment
20. persist the experiment
21. generate report
22. create coherent Git commits
23. update PROJECT_STATE.md with actual results

Do not merely tell the user what should be built.

Build it.

---

# 99. FINAL PRINCIPLE

The purpose of this system is not to create an impressive-looking backtest.

The purpose is to build a research machine we can trust after thousands of experiments.

Over time the platform should know:

what has been tested  
what was rejected  
what survived  
which features add information  
which combinations work only in specific regimes  
which results were overfit  
which parameters are robust  
which models generalize  
which assumptions are dangerous  
which strategy candidates deserve live shadow testing

The platform must progressively reduce ignorance without progressively increasing overfitting.

Correctness first.

Then reproducibility.

Then research infrastructure.

Then baseline strategies.

Then advanced market concepts.

Then robustness.

Then ML.

Then live shadow testing.

Only much later, if evidence is strong enough, consider real execution.