# ADR 0004: Event-Aware Backtest Execution & Realistic Cost Modeling

## Context
Vectorized backtesters frequently assume unrealistic fills, zero slippage, unrecorded maker/taker fee differentials, and favorable intrabar execution (e.g. assuming TP is hit before SL when both extremes are within the same bar).

## Decision
1. **Event Lifecycle**:
   - Signal generated at bar $t$ close.
   - Order filled at bar $t+1$ open (with taker fee and slippage applied).
2. **Conservative Intrabar Policy**:
   - If both TP and SL are touched during the same bar, the backtester prioritizes the Stop Loss (conservative worst-case outcome) and increments `intrabar_ambiguity_count`.
3. **Transaction Costs**:
   - Explicit maker fee (0.02%), taker fee (0.05%), and basis points slippage (2.0 bps default) are tracked per trade.
   - Net PnL and R-multiples ($R = \frac{\text{Net PnL}}{\text{Risk USDT}}$) are computed after all friction.

## Status
Accepted.
