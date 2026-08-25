# ADR 0003: Causal Multi-Timeframe Resampling & Lookahead Defense

## Context
A primary pitfall in quantitative trading research is lookahead bias caused by incomplete higher-timeframe bars (e.g. using a 1-hour candle close at 12:15) or non-causal swing high/low labeling.

## Decision
1. **UTC-Aligned Causal Resampling**: Higher timeframes (3m, 5m, 15m, 30m, 1h, 2h, 4h, 1d, 1w) are derived from canonical 1m bars using left-closed UTC calendar aggregation.
2. **Explicit Availability Timestamps**: Each aggregated bar explicitly carries an `available_at_ms = close_time + 1` timestamp. A strategy operating at minute $t$ cannot access any candle whose close time is $> t$.
3. **Causal Swing Confirmation**: A pivot high or low with $L$ left bars and $R$ right bars is mathematically confirmed only at bar $i + R$. It is emitted and forward-filled strictly from bar $i + R$ onward.

## Status
Accepted.
