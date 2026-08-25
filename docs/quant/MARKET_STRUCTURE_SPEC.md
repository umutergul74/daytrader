# Market Structure & SMC Engineering Specification

## 1. Mathematical Definitions

### 1.1 Fractal Swings (`structure:swing_fractal:v1`)
Given lookback $L$ and confirmation $R$:
- **Swing High at bar $i$**:
  $$\text{High}[i] > \text{High}[i-k] \quad \forall k \in [1, L] \quad \text{and} \quad \text{High}[i] \ge \text{High}[i+k] \quad \forall k \in [1, R]$$
- **Swing Low at bar $i$**:
  $$\text{Low}[i] < \text{Low}[i-k] \quad \forall k \in [1, L] \quad \text{and} \quad \text{Low}[i] \le \text{Low}[i+k] \quad \forall k \in [1, R]$$
- **Causality Constraint**: A swing occurring at bar $i$ is only confirmed and visible at bar $i + R$ (close time $+ 1$ ms).

---

### 1.2 Structural Sequences & Trend State
- **Higher High (HH)**: $\text{SwingHigh}_{\text{new}} > \text{SwingHigh}_{\text{prev}}$
- **Lower High (LH)**: $\text{SwingHigh}_{\text{new}} \le \text{SwingHigh}_{\text{prev}}$
- **Higher Low (HL)**: $\text{SwingLow}_{\text{new}} \ge \text{SwingLow}_{\text{prev}}$
- **Lower Low (LL)**: $\text{SwingLow}_{\text{new}} < \text{SwingLow}_{\text{prev}}$
- **Structural Trend**:
  - `BULLISH` (+1): Sequence of confirmed HH and HL.
  - `BEARISH` (-1): Sequence of confirmed LH and LL.
  - `NEUTRAL` (0): Mixed or unconfirmed initial state.

---

### 1.3 Break of Structure (BOS) vs Change of Character (CHoCH)
- **BOS by Wick** (`structure:bos_wick:v1`):
  - Bullish: $\text{High}[t] > \text{LastConfirmedSwingHigh}$
  - Bearish: $\text{Low}[t] < \text{LastConfirmedSwingLow}$
- **BOS by Close** (`structure:bos_close:v1`):
  - Bullish: $\text{Close}[t] > \text{LastConfirmedSwingHigh}$
  - Bearish: $\text{Close}[t] < \text{LastConfirmedSwingLow}$
- **Change of Character (CHoCH)**:
  - Bullish CHoCH: In a Bearish structural trend, a candle closes above the most recent confirmed Lower High.
  - Bearish CHoCH: In a Bullish structural trend, a candle closes below the most recent confirmed Higher Low.

---

### 1.4 Fair Value Gap Lifecycle (`smc:fvg_three_candle:v1`)
- **Bullish 3-Candle FVG**:
  $$\text{Low}[i] > \text{High}[i-2]$$
  - Upper Boundary = $\text{Low}[i]$
  - Lower Boundary = $\text{High}[i-2]$
  - Consequent Encroachment (50% CE) = $\frac{\text{Upper} + \text{Lower}}{2}$
- **Mitigation Lifecycle**:
  - `UNMITIGATED`: Price has not penetrated upper boundary since creation.
  - `PARTIALLY_MITIGATED`: Price traded below upper boundary and touched CE (50%).
  - `FULLY_MITIGATED`: Price traded through lower boundary or closed below it.

---

### 1.5 Liquidity Levels & Sweeps (`smc:liquidity_sweep:v1`)
- **Equal Highs / Equal Lows (EQH/EQL)**:
  $$|\text{Swing}_1 - \text{Swing}_2| \le \text{tolerance}_{\text{ATR}} \times \text{ATR}[t]$$
- **Sell-Side Liquidity Sweep & Reclaim**:
  $$\text{Low}[t] < \text{ConfirmedSwingLow} \quad \text{and} \quad \text{Close}[t] > \text{ConfirmedSwingLow}$$
- **Buy-Side Liquidity Sweep & Reclaim**:
  $$\text{High}[t] > \text{ConfirmedSwingHigh} \quad \text{and} \quad \text{Close}[t] < \text{ConfirmedSwingHigh}$$
