# ADR 0002: Canonical 1-Minute Parquet Storage & SHA-256 Dataset Fingerprinting

## Context
Quantitative backtests require an unshakeable, immutable data foundation. Using loose CSV files or ambiguous datasets ("ETHUSDT data") leads to non-reproducible research and silent data bugs.

## Decision
1. **Canonical Resolution**: 1-minute Binance USD(S)-M ETHUSDT Perpetual Futures contract klines form the single authoritative source of historical truth.
2. **Partition Hierarchy**: Canonical analytical storage uses Hive-partitioned Parquet files:
   `data/canonical/market=binance_usdm/symbol=ETHUSDT/dataset=contract_klines/timeframe=1m/year=YYYY/month=MM/*.parquet`
3. **Immutability & Fingerprinting**: Every canonical dataset build generates an immutable JSON manifest containing row count, partition count, detected gaps, and a cryptographic SHA-256 hash fingerprint of the canonical price/volume series.
4. **Experiment Lineage**: Every backtest experiment must record the exact dataset fingerprint it consumed.

## Status
Accepted.
