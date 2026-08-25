# Smart Money Concepts (SMC) & Price Action Specification

This document provides formal, unambiguous mathematical definitions for Smart Money Concepts (SMC), Market Structure, and Price Action features.

---

## 1. Causal Fractal Swing Points (Pivots)

### Definition
Given a sequence of bars $i \in \{0, \dots, N-1\}$ with parameters $L$ (left lookback bars) and $R$ (right confirmation bars):
- **Swing High at bar $i$**:
  $$High[i] > High[i - k] \quad \forall k \in [1, L] \quad \land \quad High[i] > High[i + k] \quad \forall k \in [1, R]$$
- **Swing Low at bar $i$**:
  $$Low[i] < Low[i - k] \quad \forall k \in [1, L] \quad \land \quad Low[i] < Low[i + k] \quad \forall k \in [1, R]$$

### Causality & Availability
- Confirmation timestamp: Close of bar $i + R$.
- An algorithm executing at bar $t < i + R$ has **zero awareness** of the swing at bar $i$.

---

## 2. Fair Value Gap (FVG)

### Definition (3-Candle Pattern)
Given consecutive closed candles $C_{t-2}, C_{t-1}, C_t$:
- **Bullish FVG**:
  $$Low[C_t] > High[C_{t-2}]$$
  - FVG Zone: $[High[C_{t-2}], Low[C_t]]$
  - Gap Size: $Low[C_t] - High[C_{t-2}]$
  - Consequent Encroachment (CE): $\frac{Low[C_t] + High[C_{t-2}]}{2}$
- **Bearish FVG**:
  $$High[C_t] < Low[C_{t-2}]$$
  - FVG Zone: $[High[C_t], Low[C_{t-2}]]$
  - Gap Size: $Low[C_{t-2}] - High[C_t]$
  - Consequent Encroachment (CE): $\frac{High[C_t] + Low[C_{t-2}]}{2}$

### Mitigation Semantics
- **Unmitigated**: Price has not entered the FVG zone.
- **Partially Mitigated**: Price has entered the zone but not crossed CE.
- **Fully Mitigated / Invalidated**: Price has completely traded through the opposite boundary.

---

## 3. Market Structure Shift (MSS) / Break of Structure (BOS)

### Definition
- **Bullish BOS**: Current candle close $Close[t] > \text{LastConfirmedSwingHigh}$.
- **Bearish BOS**: Current candle close $Close[t] < \text{LastConfirmedSwingLow}$.
- **Change of Character (CHoCH)**: Bullish BOS following a series of Lower Lows and Lower Highs, or Bearish BOS following a series of Higher Highs and Higher Lows.

---

## 4. Liquidity Sweeps

### Definition
- **Sell-Side Liquidity (SSL) Sweep**:
  $$Low[t] < \text{LastConfirmedSwingLow} \quad \land \quad Close[t] > \text{LastConfirmedSwingLow}$$
  Price pierces the liquidity level intrabar but closes back inside the range.
- **Buy-Side Liquidity (BSL) Sweep**:
  $$High[t] > \text{LastConfirmedSwingHigh} \quad \land \quad Close[t] < \text{LastConfirmedSwingHigh}$$
