# Quantitative Knowledge Base — Accumulated Research Findings

## 1. Market Dynamics on ETHUSDT Perpetual Futures
- **Baseline Trend**: Simple EMA Trend continuation strategies provide positive net expectancy during moderate-to-strong trends when combined with structural ATR stop losses and R:R $\ge 2.0$.
- **Volatility Breakouts**: Channel breakouts capture strong momentum during volatility expansion phases (+8.57% net return in baseline tests).
- **Mean Reversion Gating**: Unconditional RSI mean-reversion suffers from severe trend exhaustion losses; filtering by market regime (`regime_state in [RANGING, COMPRESSION]`) prevents counter-trend drawdowns.

## 2. SMC & Market Structure Insights
- **Causal Swings**: Swing Highs and Lows require explicit confirmation delay (e.g. $R=5$ bars). Assuming instantaneous swing availability creates massive backtest lookahead bias.
- **Fair Value Gaps**: FVGs are effective areas of interest when formed during high-displacement bars; 50% Consequent Encroachment (CE) serves as a key partial mitigation checkpoint.
- **Liquidity Sweeps**: Sweeping resting stop clusters at prior swing highs/lows followed by immediate candle close reclaims creates favorable risk-reward reversal setups.
