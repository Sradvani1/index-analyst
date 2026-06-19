# S&P 500 / SCHK Tactical Trading Methodology
### Disciplined Share Accumulation via Trim Waves & High-Probability Re-entry

---

## Overview & Philosophy

This framework governs tactical allocation analysis for the S&P 500 using the Schwab 1000 Index ETF (SCHK). The objective is disciplined share accumulation — identifying high-probability zones to trim a portion of the position at known resistance (Trim Waves) and redeploy at known support — capturing the market's inherent volatility as extra shares over time.

**Core principles:**
- Signals are only "overwhelmingly favorable" when **3+ independent indicators align simultaneously**
- Forcing a trade at an ambiguous midpoint is explicitly prohibited by this framework
- Allocation shifts are recommended in **5–10 percentage point increments**
- The framework integrates four analytical layers executed daily in sequence

| Layer | Frequency | Purpose |
|---|---|---|
| Fundamental Analysis | Weekly | Establish the macro valuation floor |
| Technical Analysis | Daily | Identify precise entry/exit price levels |
| Sentiment & Leverage Overlay | Daily | Gauge psychology and systemic risk |
| Monte Carlo Simulation | Per setup | Quantify statistical edge |

---

## Layer 1: Fundamental Analysis — The Macro Floor

Reviewed **weekly**. Establishes whether the current valuation environment supports dip-buying or demands caution.

### 1A. Equity Risk Premium (ERP)

Compare **S&P 500 Forward Earnings Yield** (1 ÷ Forward P/E) against the **10-Year Treasury Yield**:

- **ERP > 2%:** Equities attractive vs. bonds — support dip-buying
- **ERP 1–2%:** Caution zone — reduce aggression on re-entries
- **ERP below 1.0% or negative:** ⚠️ **Fundamental ceiling signal** — trim bias, do not add aggressively

### 1B. Forward P/E Calibration

Use FactSet consensus Forward EPS to calculate current Forward P/E. This directly governs Trim Wave price targets (recalculated each session):

| Forward P/E | Dip-Buying Posture |
|---|---|
| Below 18x | Aggressive — deploy maximum cash at support |
| 18–20x | Moderate — buy strong technical support only |
| 20–22x | Cautious — buy only Fib + SMA + sentiment confluence |
| Above 22x | Conservative — trim bias; only buy extreme fear + lower Bollinger Band |
| Above 24x | Trim ladder active — execute Trim Waves at resistance |

### 1C. Earnings Growth & Macro Regime

Confirm quarterly YoY earnings growth rate. Growth > 10% establishes a strong institutional buying floor on corrections.

| Indicator | Bullish | Bearish |
|---|---|---|
| Real GDP Growth | > 2.0% YoY | < 1.0% or contracting |
| 10-Year Treasury Yield | Stable or declining | Rising rapidly above 5% |
| Unemployment Rate | < 5% and stable | Rising above 5% |
| CPI Inflation | Declining toward 2% | Accelerating above 4% |

---

## Layer 2: Technical Analysis — The Daily Price Map

### 2A. SMA Trend Regime

| SMA Signal | Description | Allocation Bias |
|---|---|---|
| Golden Cross — 50-day crosses above 200-day | Bullish regime confirmed | Buy dips aggressively |
| 50-day above 200-day (stable) | Healthy bull market | Buy dips at 50-day; hold high equity |
| 50-day below 200-day (approaching crossover) | Caution; trend deteriorating | Trim at 50-day; reduce equity |
| Death Cross — 50-day crosses below 200-day | Bearish regime | Buy only at 200-day; reduce further |

Calculate and report the exact **% premium or discount** of today's close to both the 50-day and 200-day SMA each session.

### 2B. Bollinger Bands (20, 2)

- **Upper Band pierce:** Exhaustion signal — high-probability trim window, especially after a V-shaped recovery
- **Lower Band pierce:** Oversold signal — re-entry candidate; must be confirmed by RSI + MFI
- **Middle Band (20-day SMA):** Dynamic support in uptrends; low-risk add point on mild pullbacks

### 2C. RSI-14 & Money Flow Index (MFI)

| Signal | RSI-14 | MFI |
|---|---|---|
| Overbought / Trim zone | > 70 | > 80 |
| Approaching trim | 65–70 | 70–80 |
| Neutral / No-trade zone | 45–55 | 45–55 |
| Approaching buy zone | 30–35 | 20–30 |
| Oversold / Buy zone | < 30 | < 20 |

**Highest-conviction divergence signals:**
- **Bullish divergence:** MFI makes a higher low while price makes a lower low → strongest re-entry signal in the framework
- **Bearish divergence:** MFI makes a lower high while price makes a higher high → trim confirmation
- MFI crossing below 50 on a declining market = institutional selling confirmed; do not buy against this flow

### 2D. Combined Signal Rule — 3-of-5 Confirmation

A trim or re-entry is only "overwhelmingly favorable" when **3 or more** of the following align simultaneously:

| Signal | Trim (Sell) | Re-entry (Buy) |
|---|---|---|
| Price vs. 50-day SMA | At or above resistance | At or below support |
| Bollinger Bands | At or near upper band | At or near lower band |
| RSI-14 | Above 65, flattening | Below 35, rising |
| MFI | Above 70, flattening | Below 30, rising or diverging |
| Price vs. 200-day SMA | Well above 200-day | At or near 200-day |

### 2E. Fibonacci Retracement Levels

After identifying the most recent significant swing high and swing low, apply Fibonacci ratios to project pullback depth:

| Level | Typical Behavior | Deployment |
|---|---|---|
| 23.6% | Shallow pullback; strong bull markets | Add small position |
| 38.2% | Standard healthy pullback — **primary re-entry zone** | Core re-entry target |
| 50.0% | Significant correction; tests conviction | High-probability bounce if fundamentals intact |
| 61.8% | Deep correction; high reward/risk | Maximum deployment zone |
| 78.6% | Near full reversal | Only if bull thesis is unambiguously intact |

**SMA/Fib Convergence — Primary Re-entry Zone:**
Project the 50-day SMA's daily rising rate forward to find the exact **price level and calendar date** where it intersects the 38.2% or 50% Fib retracement. This convergence is the highest-probability re-entry zone in the framework.

---

## Layer 3: Sentiment & Leverage Overlay

### 3A. CNN Fear & Greed Index

| Score | Zone | Signal |
|---|---|---|
| 0–25 | Extreme Fear | Strong re-entry signal — deploy cash |
| 25–40 | Fear | Scale in cautiously at technical support |
| 40–55 | Neutral | No-man's land — no allocation shift |
| 55–70 | Greed | Begin positioning for trim at next resistance |
| 75–100 | Extreme Greed | Strong trim signal — reduce equity |

> **Rule:** Sentiment must be confirmed by technical levels. Never act on sentiment alone. If the index makes a new price low but the F&G index holds a higher low (fear does not increase), this bullish divergence is a high-conviction re-entry signal.

### 3B. Put/Call Ratio

- Elevated put/call (> 1.2): Heavy hedging — potential contrarian buy signal
- Falling put/call (< 0.7): Complacency — trim alert

### 3C. Junk Bond Spreads (Credit Market Divergence)

Monitor the spread between high-yield bonds and Treasuries:

| Condition | Interpretation |
|---|---|
| Spreads widening while equity holds | ⚠️ Credit market warning — institutional risk-off beginning; trim bias |
| Spreads tightening while equity rallies | Confirms bull move — re-entry supported |
| Spreads at multi-year highs | Potential systemic risk — reduce equity allocation |

### 3D. VIX Regime Filter

| VIX Level | Regime | Implication |
|---|---|---|
| < 15 | Low vol / Complacency | Standard signals apply; watch for complacency reversal |
| 15–20 | Moderate | Full framework active; execute confirmed setups |
| **> 20** | **Elevated** | **Moving averages less reliable; forced selling risk rises; note in analysis** |
| 20–30 | Elevated | Caution — hold current allocation; await VIX normalization |
| > 30 | Crisis | Do not act — institutional forced selling can gap through any technical level |

**Critical exception:** VIX spiking above 30 then collapsing back toward 20 is one of the most powerful re-entry signals in market history. Flag re-entry when VIX falls back through 22 from an elevated state.

**VIX vs. its 50-day MA:** Flag any VIX spike above its own 50-day MA as an early risk-parity and leverage-unwind warning.

### 3E. Margin Debt & Leverage Monitor

Monitor the latest FINRA margin debt data monthly. Flag **structural divergences**:
- Margin debt rising while price stagnates or declines → leveraged buyers losing ground (bearish)
- Margin debt falling while price rises → deleveraging into strength (bearish medium-term)

**Dynamic Liquidation Thresholds** — calculated from the most recent swing high each session:

| Zone | Drop from Swing High | Trigger Mechanism |
|---|---|---|
| Nervous Zone | −5% to −7% | Late-buyers go underwater; initial stop-loss selling begins |
| First Margin Call Wave | −10% | Retail/institutional maintenance margins breached |
| Forced Liquidation Cascade | −15% | Algorithmic systemic unwinding accelerates |

> These are **acceleration zones**, not price predictions. A normal pullback can cascade if leverage is elevated when these levels are breached.

---

## Layer 4: Monte Carlo Probability Analysis

Every trade setup concludes with a 20,000-path Geometric Brownian Motion simulation to quantify statistical edge and remove emotional bias.

**Model parameters:**

\[ S_t = S_0 \cdot e^{(\mu - \frac{1}{2}\sigma^2)t + \sigma W_t} \]

- \(S_0\) = today's closing price (recentered each session)
- \(\mu\) = 8% annualized drift
- \(\sigma\) = 20% annualized volatility
- Horizon: **60 trading days**
- Paths: **20,000**

### Required Outputs Every Session

| Output | Purpose |
|---|---|
| **First-Hit Probabilities** | P(upside target hit first) vs. P(downside target hit first) |
| **Conditional Cascade Probabilities** | Given Level A hit, what is P(Level B), P(Level C)? |
| **Median Days to Hit** | Timeline for each key level — establishes tactical urgency |
| **Cash Drag Analysis** | P(support level never hit within 60 days) — cost of waiting in cash |

**Action threshold:** Flag setups with ≥ 65% probability as actionable. Flag 50–65% as "monitor only." Flag < 50% as insufficient edge — do not recommend action.

---

## Daily 7-Step Workflow

Execute these steps in exact order after receiving the closing price, updated chart, and sentiment data.

---

### Step 1: Price Action & Trend Recentering

- Log: close, point change, % change
- State: % below the 52-week high
- Calculate: net % recovery from the cycle/structural low
- Identify: current SMA regime (Golden Cross / Death Cross / transitional)

---

### Step 2: Technical & Sentiment Pulse

**Momentum indicators:**
- RSI-14: exact level; flag overbought (> 70), oversold (< 30), or divergence
- MFI: exact level; flag overbought (> 80), oversold (< 20), or divergence

**Bands & averages:**
- Bollinger Band position: upper pierce / lower pierce / within band / middle band test
- Exact % premium or discount to 50-day SMA
- Exact % premium or discount to 200-day SMA

**Sentiment:**
- CNN Fear & Greed: score + zone
- Put/Call ratio + interpretation
- Junk Bond Spreads: tightening or widening? Note any credit divergence

---

### Step 3: Fundamental Valuation & ERP

- **Trailing P/E** = Current Close ÷ Trailing 12-Month EPS
- **Forward P/E** = Current Close ÷ FactSet Consensus Forward EPS
- **Forward Earnings Yield** = 1 ÷ Forward P/E
- **ERP** = Forward Earnings Yield − 10-Year Treasury Yield
- ⚠️ Flag if ERP < 1.0% (caution) or negative (fundamental ceiling — trim bias)
- State current dip-buying posture from the Forward P/E calibration table

---

### Step 4: Leverage & Margin Debt Monitor

- **Margin Debt Divergence:** Note any structural divergence between latest FINRA data and current price action
- **Update Dynamic Liquidation Thresholds** from the current swing high:
  - Nervous Zone (−5 to −7%): [calculated price level]
  - First Margin Call Wave (−10%): [calculated price level]
  - Forced Liquidation Cascade (−15%): [calculated price level]
- **VIX Catalyst:** Is VIX above 20? Above its own 50-day MA? State the risk implication clearly

---

### Step 5: Monte Carlo & Brownian Motion

- Run 20,000-path GBM simulation recentered on today's close (μ = 8%, σ = 20%, 60-day horizon)
- Report:
  - P(upside target hit first) vs. P(downside target hit first)
  - Conditional cascade probabilities for 2–3 key levels
  - Median days to reach each target
  - Cash drag probability (P that support is never hit within 60 days)
- State: does this setup meet the ≥ 65% action threshold?

---

### Step 6: Tactical Matrix — Trims & Re-entries

**Trim Ladder** — recalculate each session using current FactSet Forward EPS:

| Trim Wave | Fwd P/E Trigger | Implied SPX Level | Suggested Shift |
|---|---|---|---|
| Wave 1 | 22x Forward P/E | [calculated] | ~3–5% equity reduction |
| Wave 2 | 23x Forward P/E | [calculated] | ~3–5% equity reduction |
| Wave 3 | 24x+ Forward P/E | [calculated] | ~3–5% equity reduction |

**SMA/Fib Convergence Re-entry Zones:**
- Calculate Fib retracements (23.6%, 38.2%, 50%, 61.8%) from cycle peak
- Project 50-day SMA's daily rising rate forward
- Identify the exact **price and calendar date** where the 50-day SMA intersects the 38.2% or 50% Fib → **Primary Re-entry Zone**
- Secondary re-entry: 61.8% Fib (maximum deployment consideration)

---

### Step 7: Narrative & Executive Summary

- Synthesize all 6 steps into a concise 2–3 paragraph executive narrative
- State current **base case: Bull or Bear** (30–60 day horizon)
- Note the single most important risk or opportunity not captured by technicals alone
- End with the **Updated Decision Matrix:**

| Signal Layer | Current Reading | Signal |
|---|---|---|
| Trend Regime (SMA) | [state] | Bull / Bear / Neutral |
| RSI / MFI | [state] | Overbought / Oversold / Neutral / Divergence |
| Bollinger Band | [state] | Upper Pierce / Lower Pierce / Within |
| ERP | [state] | Attractive / Caution / Ceiling |
| Leverage Risk | [state] | Elevated / Moderate / Low |
| Monte Carlo Edge | [state] | Actionable (≥65%) / Monitor / Insufficient |
| Sentiment (F&G / VIX) | [state] | Extreme Fear / Fear / Neutral / Greed / Extreme Greed |
| **RECOMMENDED ACTION** | | **[Trim Wave X / Hold / Deploy X% Cash / Monitor]** |

---

## Alpha Accumulation Math

For each trim/re-entry cycle, the additional shares accumulated as a percentage of the trimmed tranche:

\[ \alpha = \frac{R - S}{S} \]

Where \(R\) = trim (resistance) price and \(S\) = re-entry (support) price. Executed 3–4 times per year across a meaningful portfolio, this compounds into material long-run outperformance vs. pure buy-and-hold.

---

## Risk Management Framework

1. **Never force a signal.** Mixed or ambiguous data = hold and monitor.
2. **Never recommend trimming the entire position.** Remaining equity always participates in unexpected melt-ups.
3. **Scale in, scale out.** Split re-entry across two Fib levels (e.g., 50% at 38.2%, 50% at 50%). Never recommend full deployment if the market can fall further.
4. **VIX > 20 = elevated risk flag.** Note reduced reliability of moving averages and increased forced-selling risk.
5. **Monte Carlo minimum.** < 65% probability = flag as insufficient edge; do not recommend action.
6. **The re-entry is never guaranteed.** If the market does not pull back to the target, hold cash patiently. Panic-buying at higher prices after trimming is the primary failure mode.

---

## Allocation Signal Reference Table

| Condition | Recommended Analysis Output | Directional Bias |
|---|---|---|
| Price at 50-day resistance + RSI > 65 + MFI > 70 + F&G > 55 | Flag Trim Wave 1 level | Reduce equity |
| Above Trim Wave 1 + Fwd P/E > 23x + Monte Carlo ≥ 65% | Flag Trim Wave 2 level | Reduce further |
| Above Trim Wave 2 + Fwd P/E > 24x + ERP < 1% | Flag Trim Wave 3 level | Reduce further |
| 38.2% Fib + 50-day SMA convergence + RSI < 40 + F&G < 40 | Flag Primary Re-entry Zone | Deploy cash |
| 50% Fib + RSI < 35 + MFI divergence + F&G < 30 | Flag Secondary Re-entry Zone | Deploy remaining cash |
| Price in channel between 50-day and 200-day SMA | No actionable setup | Hold and monitor |
| Monte Carlo P(target first) < 55% | Insufficient edge | Wait for cleaner setup |
| VIX > 20 | Risk elevated — note implications | Reduce aggression |

---

*This is a living document, refined as market conditions evolve and each session generates new data.*
