# ADR 0005: Permanent Research Ledger & Scientific Knowledge Accumulation

## Context
Ad-hoc backtests in Jupyter notebooks are lost or forgotten, leading to parameter mining, repeated failed experiments, and selection bias where only accidentally profitable runs are remembered.

## Decision
1. **Permanent Research Ledger**:
   - Every experiment is assigned a unique ID (`EXP-YYYYMMDD-HHMMSS-<hash>`).
   - Stores full metadata: hypothesis, parameters, dataset fingerprint, Git SHA, metrics, status, warnings, and conclusions.
2. **Negative Results as Permanent Knowledge**:
   - Failed and rejected experiments are permanently preserved with exact rejection reasons (e.g. negative expectancy after fees, excessive drawdown, overfitting).
3. **Automated Deduplication**:
   - The ledger computes an experiment identity hash and warns/prevents duplicate redundant executions.
4. **Dual Tracking**:
   - Local JSON-based Research Ledger for portable auditability.
   - MLflow integration for visual parameter/metric tracking and artifact management.

## Status
Accepted.
