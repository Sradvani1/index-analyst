# S&P 500 / SCHK Tactical Trading Methodology
### Disciplined Allocation via Trim Waves & High-Probability Re-entry
**Version 3.0 — Revised June 2026 | Monte Carlo Framework Upgrade**

---

## Overview & Philosophy

This framework governs tactical allocation analysis for the S&P 500 using the Schwab 1000 Index ETF (SCHK). The objective is disciplined share accumulation — identifying high-probability zones to trim a portion of the position at known resistance (Trim Waves) and redeploy at known support, capturing the market's inherent volatility as extra shares over time.

| Layer | Frequency | Purpose |
|---|---|---|
| Structural Regime Classification | Daily pre-step | Set the master context that modulates all signal weights |
| Fundamental Analysis | Weekly | Establish the macro valuation floor and ceiling |
| Technical Analysis | Daily | Identify precise entry/exit price levels |
| Sentiment & Leverage Overlay | Daily | Gauge psychology, breadth, and systemic risk |
| Monte Carlo Simulation | Per setup | Quantify statistical edge with regime-adjusted parameters |

**Core Principles:**
- Signals are only actionable when 3+ independent indicators align simultaneously
- Forcing a trade at an ambiguous midpoint is explicitly prohibited
- Allocation shifts are executed in 5–10 percentage point increments
- The Structural Regime Classification runs before Step 1 and modulates all downstream signal weights
- The 7-Step workflow is executed in exact order, every session

---

## Pre-Step: Structural Regime Classification

**Run this before Step 1 every session.** This is the master context assessment. Its output — a Structural Bias classification — determines how Monte Carlo thresholds, signal weights, and the 23.6% Fib rule are applied for the entire session.

Answer all four questions using current data, then assign the Structural Bias.

### Q1: Price Extension from 200-Day SMA
| % Above 200-Day SMA | Extension Level |
|---|---|
| < 5% | Normal — no adjustment |
| 5–10% | Moderate extension |
| 10–15% | Elevated extension |
| > 15% | Extreme extension — flag explicitly |

### Q2: Equity Risk Premium Trend
| ERP vs. Prior 20-Session Average | Signal |
|---|---|
| ERP expanding (rising) | Bullish structural support |
| ERP stable | Neutral |
| ERP contracting (falling) | Bearish structural pressure |

Also note: Is current ERP in the upper, middle, or lower quartile of its own 2-year range?

### Q3: Credit Confirmation
| Junk Bond Spread (20-session trend) | Signal |
|---|---|
| Tightening | Credit confirms equity strength |
| Flat | Neutral |
| Widening | Credit diverging from equity — bearish |

### Q4: Breadth Confirmation
| McClellan Summation (10-session trend) | New Highs/Lows Ratio | Signal |
|---|---|---|
| Rising, > 1,200 | Expanding | Broad participation — bullish |
| Flat, 800–1,200 | Flat | Mixed |
| Falling, < 800 | Contracting | Breadth deteriorating — bearish |

### Structural Bias Classification

| Regime | Criteria | Monte Carlo Action Threshold | 23.6% Fib Rule |
|---|---|---|---|
| **Early Bull** | Price 0–10% above 200-day; ERP expanding; ERP > 1.5%; breadth rising; credit tightening | 65% (standard) | Light re-entry if Fwd PE < 18x and ERP > 2% |
| **Mid Bull** | Price 5–12% above 200-day; ERP stable at 1–2%; breadth confirming | 65% (standard) | Pause zone; monitor only |
| **Late Bull / Topping** | Price > 12% above 200-day; ERP < 0.5%; breadth diverging; credit widening | **70% required** | Hard pause zone — no deployment |
| **Bear Market** | Death Cross; EPS estimates declining; ERP compressing on falling prices | **75% required** | Fib levels reset from new lows; buy only at 200-day |

> **The Structural Bias is the single most important input to the session.** State it explicitly at the top of every analysis before proceeding to Step 1.

---

## Layer 1: Fundamental Analysis — The Macro Floor

*Reviewed weekly. Establishes whether the current valuation environment supports dip-buying or demands caution.*

### 1A. Equity Risk Premium (ERP)

**Formula:** `ERP = Forward Earnings Yield (1 / Forward PE) − 10-Year Treasury Yield`

**Calculate and report every session.**

| ERP Level | Interpretation | Posture |
|---|---|---|
| ERP > 2.0% | Equities attractively valued vs. bonds | Aggressive dip-buying supported |
| ERP 1.0–2.0% | Moderate cushion | Normal dip-buying |
| ERP 0.5–1.0% | Caution zone — thin margin | Reduce aggression on re-entries |
| ERP 0.0–0.5% | Fundamental ceiling — equities barely beating cash | Trim bias; do not add aggressively |
| ERP < 0.0% | Negative — equities more expensive than risk-free | Trim only; no new longs at current price |

> **Session rule:** Calculate the SPX price level at which ERP crosses the 0.5% threshold. This becomes the **ERP-confirmed re-entry floor** for the current session. When the ERP floor converges with the primary Fib/SMA re-entry zone, it is a maximum-conviction buy zone.

> **ERP Trend rule:** Track the direction of ERP over the prior 20 sessions. A contracting ERP (rising P/E or rising yields) into a topping pattern is a structural warning even when the absolute level is still positive. An expanding ERP during a correction is a structural tailwind for re-entry.

### 1B. Forward PE Calibration

Use FactSet Consensus Forward EPS. **Recalculate every session** using the current close.

| Forward PE | Dip-Buying Posture |
|---|---|
| Below 18x | Aggressive — deploy maximum cash at support |
| 18–20x | Moderate — buy at strong technical support only |
| 20–22x | Cautious — buy only at Fib/SMA/sentiment confluence |
| 22–24x | Conservative — trim bias; buy only at extreme fear + lower Bollinger Band |
| Above 24x | Trim Ladder active — execute Trim Waves at resistance |

> **Session rule:** Report both Trailing PE and Forward PE. Forward PE drives the Trim Wave trigger levels. Trailing PE provides historical context for valuation extremity.

### 1C. Earnings Growth & Macro Regime

Confirm quarterly YoY earnings growth rate. Growth ≥ 10% establishes a strong institutional buying floor on corrections.

| Indicator | Bullish | Bearish |
|---|---|---|
| Real GDP Growth | > 2.0% YoY | < 1.0% or contracting |
| 10-Year Treasury Yield | Stable or declining | Rising rapidly; above 5% |
| Unemployment Rate | < 5% and stable | Rising above 5% |
| CPI Inflation | Declining toward 2% | Accelerating above 4% |

---

## Layer 2: Technical Analysis — The Daily Price Map

### 2A. SMA Trend Regime

Calculate and report the **exact premium or discount** of today's close to both the 50-day and 200-day SMA each session.

| SMA Signal | Description | Allocation Bias |
|---|---|---|
| Golden Cross (50-day crosses above 200-day) | Bullish regime confirmed | Buy dips aggressively |
| 50-day above 200-day (stable) | Healthy bull market | Buy dips at 50-day; hold high equity |
| 50-day below 200-day (approaching crossover) | Caution — trend deteriorating | Trim at 50-day; reduce equity |
| Death Cross (50-day crosses below 200-day) | Bearish regime | Buy only at 200-day; reduce further |

> **Session rule:** Also note the 125-day MA (CNN F&G Market Momentum component). When SPX falls below its 125-day MA, the Market Momentum F&G component downgrades from Greed — this is a high-visibility early warning.

### 2B. Bollinger Bands (20, 2)

| Signal | Interpretation |
|---|---|
| Upper Band pierce | Exhaustion signal; high-probability trim window, especially after a V-shaped recovery |
| Riding/walking the upper band | Extended but not yet exhausted; monitor for close-of-day rejection pattern |
| Lower Band pierce | Oversold signal; re-entry candidate — must be confirmed by RSI/MFI |
| Middle Band (20-day SMA) | Dynamic support in uptrends; key regime indicator — track **closing basis** |

> **Middle Band Regime Rule:** The 20-day SMA (middle Bollinger Band) is a critical trend regime indicator. When SPX closes below the 20-day SMA after an extended uptrend, this is a regime shift — the band converts from support to resistance. Flag this event explicitly. When SPX reclaims the 20-day SMA on a close, the regime flips back bullish.

### 2C. RSI-14 & Money Flow Index (MFI)

| Signal | RSI-14 | MFI |
|---|---|---|
| Overbought — Trim zone | > 70 | > 80 |
| Approaching trim | 65–70 | 70–80 |
| Neutral — No-trade zone | 45–55 | 45–55 |
| Approaching buy zone | 30–35 | 20–30 |
| Oversold — Buy zone | < 30 | < 20 |

**Highest-conviction divergence signals:**
- **Bullish divergence:** MFI makes a higher low while price makes a lower low → strongest re-entry signal in the framework
- **Bearish divergence:** MFI makes a lower high while price makes a higher high → trim confirmation
- **MFI crossing below 50** on a declining market → institutional selling confirmed; do not buy against this flow

> **Multi-timeframe RSI/MFI Rule:** Evaluate RSI and MFI on **1-day, 1-month, 3-month, and 6-month** chart views each session. A bearish divergence forming on the 3-month or 6-month chart carries significantly more weight than a 1-day reading. Flag any multi-timeframe alignment explicitly (e.g., "3-month bearish MFI divergence confirmed while price makes new highs").

### 2D. Combined Signal Rule — 3-of-5 Confirmation

| Signal | Trim (Sell) | Re-entry (Buy) |
|---|---|---|
| Price vs. 50-day SMA | At or above resistance | At or below support |
| Bollinger Bands | At or near upper band | At or near lower band |
| RSI-14 | Above 65, flattening | Below 35, rising |
| MFI | Above 70, flattening | Below 30, rising or diverging |
| Price vs. 200-day SMA | Well above 200-day | At or near 200-day |

> **Intraday Structure Rule:** Beyond the closing price, report **where in the daily range the close fell.** A close in the bottom 15–25% of the day's range (open at high, close near low) is a distribution signal — qualitatively equivalent to an additional bearish indicator, even on nominally positive sessions. A close in the top 15–25% of range is a strength signal. State this explicitly each session. **Volume qualifier:** Flag as high-conviction only when accompanied by above-average volume. Low-volume intraday structure is noted as "low-conviction" and carries reduced weight.

### 2E. Fibonacci Retracement Levels

After identifying the most recent significant swing high and swing low, apply Fibonacci ratios to project pullback depth.

| Level | Typical Behavior | Deployment | Regime Modifier |
|---|---|---|---|
| 23.6% | Shallow pullback | **Pause zone — no deployment in Mid/Late Bull.** Light re-entry only in Early Bull (Fwd PE < 18x, ERP > 2%) | Regime-dependent |
| 38.2% | Standard healthy pullback — **Primary re-entry zone** | Deploy 50% of trimmed cash | All regimes |
| 50.0% | Significant correction; tests conviction | Deploy 25% of trimmed cash if 38.2% failed to hold | All regimes |
| 61.8% | Deep correction; high reward/risk | Maximum deployment — especially if 50-day SMA converges here | All regimes |
| 78.6% | Near full reversal | Only if bull thesis is unambiguously intact | All regimes |

> **CRITICAL — 23.6% Fib Is Regime-Dependent:** In Mid Bull and Late Bull regimes, the 23.6% retracement is routinely violated on the way to 38.2%. Never deploy cash at 23.6% in these regimes. In Early Bull (low PE, high ERP, rising breadth), it can serve as a light re-entry. The Structural Bias classification determines which rule applies each session.

**SMA/Fib Convergence — Primary Re-entry Zone:**
Project the 50-day SMA's daily rising rate forward to find the exact price level and calendar date where it intersects the 38.2% or 50% Fib retracement. This convergence is the highest-probability re-entry zone in the framework. **Calculate and report the convergence date each session.**

---

## Layer 3: Sentiment & Leverage Overlay

### 3A. CNN Fear & Greed Index — Full Component Analysis

Report all 7 components every session, not just the headline score.

| Score | Zone | Signal |
|---|---|---|
| 0–25 | Extreme Fear | Strong re-entry signal — deploy cash |
| 25–40 | Fear | Scale in cautiously at technical support |
| 40–55 | Neutral | No-man's land — no allocation shift |
| 55–70 | Greed | Begin positioning for trim at next resistance |
| 75–100 | Extreme Greed | Strong trim signal — reduce equity |

**Rule:** Sentiment must be confirmed by technical levels. Never act on sentiment alone.

> **Internal Divergence Rule:** Track and explicitly flag when the headline F&G score diverges from its sub-components:
> - **Bullish headline / Bearish breadth:** Headline Greed while McClellan Volume Summation is Extreme Fear → narrow mega-cap-driven rally; do not treat as broad strength
> - **F&G falling for 3+ consecutive sessions while price makes new highs:** Highest-priority topping signal in the framework
> - **Safe Haven Demand downgrade:** When bonds begin outperforming stocks on the 20-day differential, this is an active institutional rotation signal — flag tier changes explicitly

> **F&G Collapse Rate as Bottoming Signal:** Track the cumulative F&G point decline from any peak. A drop of 25+ points in 8–10 sessions places the composite in the same zone as prior cycle bottoms. When F&G reaches Extreme Fear (< 25) after a rapid decline AND the Put/Call ratio spikes above 0.75–0.80, treat as a contrarian re-entry watch signal (confirmation still required).

> **McClellan Comparison Rule:** Rather than using a fixed Extreme Fear threshold (e.g., 950), compare McClellan readings to **the most recent cycle low's McClellan level.** When McClellan reaches the same level it printed at the prior cycle low while price is substantially above that low, it is a breadth capitulation signal. This approach works across all market cycles regardless of absolute scale.

### 3B. Put/Call Ratio

| Level | Interpretation |
|---|---|
| > 1.2 | Heavy hedging — potential contrarian buy signal |
| 0.8–1.0 | Rising fear — watch for reversal |
| 0.7–0.8 | Neutral |
| < 0.70 | Complacency — trim alert |
| < 0.65 | Deep complacency — historically precedes corrections within 5–10 days |

> **Put/Call as Leading Bottom Indicator:** A Put/Call ratio rising from deep complacency (< 0.65) toward 0.75–0.80 is the first contrarian signal that typically appears 2–5 sessions before a local bottom. When Put/Call reaches 0.80+ in conjunction with F&G Extreme Fear, it has historically marked near-term bottoms within 1–3 sessions.

### 3C. Junk Bond Spreads — Credit Market Divergence

Monitor the spread between high-yield bonds and Treasuries.

| Condition | Interpretation |
|---|---|
| Spreads widening while equity holds | Credit market warning — institutional risk-off beginning; trim bias |
| Spreads tightening while equity rallies | Confirms bull move — re-entry supported |
| Spreads at multi-year highs | Potential systemic risk — reduce equity allocation |

> **Relative Spread Rule (Cycle-Robust):** Rather than relying on fixed absolute spread levels (which are cycle-dependent), track the **spread change vs. the prior 60-session average.** A spread widening of 30+ bps above the 60-session average is a caution signal. A widening of 50+ bps is a warning. A widening of 70+ bps sustained over 3+ sessions is an alarm. This calibration works across different rate cycles where absolute spread levels differ materially.

> **Absolute spread reference levels from the 2026 cycle** (use as context, not as universal thresholds): 1.28–1.33 = caution; 1.45 = warning level seen before the April and June corrections; 1.50+ = alarm.

### 3D. VIX Regime Filter

| VIX Level | Regime | Implication |
|---|---|---|
| < 15 | Low vol | Complacency; standard signals apply — watch for reversal |
| 15–20 | Moderate | Full framework active; execute confirmed setups |
| > 20 | **Elevated** | **Moving averages less reliable; forced selling risk rises — note explicitly** |
| 20–30 | Elevated | Caution; hold current allocation; await VIX normalization |
| > 30 | Crisis | Do not act; institutional forced selling can gap through any technical level |

**Critical exception:** VIX spiking above 30 then collapsing back toward 20 is one of the most powerful re-entry signals in market history. Flag re-entry when VIX falls back through 22 from an elevated state.

**VIX vs. its 50-day MA:** Flag any VIX spike above its own 50-day MA as an early risk-parity and leverage-unwind warning.

> **VIX Capitulation Spike Rule:** A correction that unfolds without a VIX capitulation spike is a controlled, orderly decline — do not deploy cash aggressively. The framework supports two valid re-entry pathways: (1) VIX spikes above 25–30 then collapses below 22 — highest-conviction re-entry; (2) Primary Fib/SMA re-entry zone is reached with 3-of-4 re-entry checklist confirmed, even without a VIX spike — sufficient if structural bias is Early or Mid Bull.

### 3E. Margin Debt & Leverage Monitor

Monitor the latest FINRA margin debt data (monthly). Flag structural divergences:
- **Margin debt rising while price stagnates or declines:** Leveraged buyers losing ground — bearish
- **Margin debt falling while price rises:** Deleveraging into strength — bearish medium-term

**Dynamic Liquidation Thresholds** — calculated from the most recent swing high each session:

| Zone | Drop from Swing High | Trigger Mechanism |
|---|---|---|
| Caution Zone | −3% | Early warning; first sign topping process may have begun |
| Nervous Zone | −5 to −7% | Late-buyers go underwater; initial stop-loss selling begins |
| First Margin Call Wave | −10% | Retail/institutional maintenance margins breached |
| Forced Liquidation Cascade | −15% | Algorithmic/systematic unwinding accelerates |

*These are acceleration zones, not price predictions. A normal pullback can cascade if leverage is elevated when these levels are breached.*

---

## Layer 4: Monte Carlo Probability Analysis

**Version 3.0 — Regime-Adjusted, Dynamic Parameters**

Every trade setup concludes with a 20,000-path Geometric Brownian Motion simulation. Unlike prior versions, parameters are now dynamically adjusted each session based on current market conditions. The simulation quantifies statistical edge but is interpreted through the Structural Bias lens — the same output number carries different actionability depending on regime.

---

### 4A. Dynamic Model Parameters

**Parameters that update every session:**

#### σ — Realized Volatility (replaces fixed 20%)

Do not use a fixed σ. Calculate the trailing 20-day realized volatility from actual daily returns and use that as the simulation input.

**Calculation:**
`σ_daily = StdDev of log daily returns over the prior 20 sessions`
`σ_annual = σ_daily × √252`

Use this annualized figure as σ in the simulation. As a practical proxy when exact data is unavailable, use: `σ = VIX ÷ √252 × √252 = VIX / 100` (i.e., treat VIX directly as the annualized vol estimate).

| VIX / Realized Vol | σ to Use | Implication |
|---|---|---|
| VIX < 15 / Realized vol ~10–13% | σ = 12–14% | Tight probability bands; small moves dominate |
| VIX 15–20 / Realized vol ~14–18% | σ = 15–18% | Standard framework conditions |
| VIX 20–25 / Realized vol ~18–22% | σ = 20–22% | Widening tails; downside targets closer in time |
| VIX > 25 / Realized vol > 22% | σ = 25–35% | Crisis vol; all technical levels less reliable |

#### μ — Momentum-Adjusted Drift (replaces fixed 8%)

The long-run 8% annual drift is the right anchor for the full cycle. But applying full drift after a large, fast move overstates the probability of continued upside. Adjust μ based on the current premium to the 200-day SMA:

| % Above 200-Day SMA | μ to Use | Rationale |
|---|---|---|
| < 5% | μ = 8–10% | At or near mean; full historical drift applies |
| 5–10% | μ = 6–8% | Moderate extension; slight mean-reversion pressure |
| 10–15% | μ = 4–5% | Elevated extension; drift benefit substantially reduced |
| > 15% | μ = 2–3% | Extreme extension; mean-reversion dominates near-term |
| Below 200-day SMA | μ = 8–12% | Recovery dynamics; higher expected return from depressed base |

> **Rationale:** Markets are not constant-drift processes at the session level. After a +20% move in 6 weeks, the expected short-term drift is materially lower than the 8% long-run average. This adjustment does not change the long-run thesis — it correctly reflects that much of the near-term expected return has already been harvested.

#### Horizon — Fixed at 60 Trading Days
The 60-day horizon remains standard. Do not adjust.

#### Paths — Fixed at 20,000
20,000 paths remain standard.

---

### 4B. Rally Exhaustion Score

Before running the simulation, calculate the Rally Exhaustion Score. This determines whether a discount should be applied to upside-first probabilities when interpreting results.

Compute three inputs:

| Input | How to Compute | Exhaustion Level |
|---|---|---|
| Move Magnitude | % gain from most recent cycle low to current price | < 10%: Low; 10–15%: Moderate; 15–20%: High; > 20%: Extreme |
| Move Velocity | Total % gain ÷ calendar weeks elapsed | < 1%/wk: Low; 1–1.5%/wk: Moderate; 1.5–2.5%/wk: High; > 2.5%/wk: Extreme |
| Vol Compression | Current realized vol vs. prior 60-session average vol | Rising or flat: Low; Contracting: Moderate; Sharply below avg: High/Extreme |

**Score:**
- 0–1 inputs elevated/extreme: **Low Exhaustion** — no adjustment; use simulation outputs at face value
- 2 inputs elevated/extreme: **Moderate Exhaustion** — apply 5-point probability discount to upside-first outputs
- 3 inputs elevated/extreme: **High Exhaustion** — apply 8-point probability discount to upside-first outputs

> **Example:** Simulation outputs 63% upside-first. Rally Exhaustion Score is High (3 of 3 inputs elevated). Effective probability = 63% − 8% = 55%. This falls below the 65% action threshold → correctly classifies as "insufficient edge."

---

### 4C. Regime-Adjusted Action Thresholds

The Structural Bias classification from the Pre-Step sets the Monte Carlo action threshold for the entire session:

| Structural Bias | Base Action Threshold | After Exhaustion Discount Applied |
|---|---|---|
| Early Bull | 65% | Same — no discount typically warranted |
| Mid Bull | 65% | Apply discount if Exhaustion Score is Moderate or High |
| Late Bull / Topping | **70%** | Apply discount — threshold effectively ~75–78% raw before discount |
| Bear Market | **75%** | Apply discount — requires very high raw probability to act |

> **This resolves the core Monte Carlo bias problem.** A raw output of 63% upside-first in an Early Bull regime (PE < 18x, ERP > 2%) is actionable. The same raw output in a Late Bull regime with High Exhaustion Score is not. The same number; different decisions. The framework now distinguishes them explicitly.

---

### 4D. Required Outputs Every Session

| Output | Purpose |
|---|---|
| Current σ (realized vol / VIX-based) | Establishes which vol regime the simulation runs in |
| Current μ (momentum-adjusted drift) | Establishes drift used — report the % above 200-day that drives it |
| Rally Exhaustion Score | Low / Moderate / High — determines probability discount |
| Effective Action Threshold | 65% / 70% / 75% based on Structural Bias |
| First-Hit Probabilities (raw) | P(upside target hit first) vs. P(downside target hit first) |
| First-Hit Probabilities (adjusted) | After applying exhaustion discount |
| Does adjusted probability meet threshold? | Yes / No — state explicitly |
| Conditional Cascade Probabilities | Both directions — upside and downside cascades |
| Median Days to Hit | Timeline for each key level |
| GBM Drift Path | Expected price at 5, 10, 20, 30, 60 days |
| Drift Path Ceiling Check | If 60-day expected return < 2%, flag: "easy gains consumed" |
| Cash Drag | P(primary support never hit within 60 days) — cost of waiting |

---

### 4E. Symmetric Cascade Reporting

Report cascade probabilities in **both directions** every session. Downside cascades are structurally severe by the math of GBM — typically 85–87% continuation to the next level once any support breaks. This is not a bearish bias; it is a structural feature.

State explicitly: *"If [level] breaks, P([next level]) = XX%."* for both upside and downside.

---

### 4F. Annual Parameter Review

At the start of each calendar year (or following a major regime shift):
1. Recalculate the trailing 10-year annualized equity return → update the base μ
2. Recalculate the trailing 252-day realized volatility → validate the VIX proxy approach
3. Review whether the 60-day horizon remains appropriate for the current trading rhythm

This ensures the simulation parameters remain calibrated to current cycle dynamics rather than ossifying into stale constants.

---

## Daily 7-Step Workflow

*Execute in exact order after receiving the closing price, updated chart, and sentiment data. The Structural Regime Classification runs as a Pre-Step before Step 1.*

---

### Pre-Step: Structural Regime Classification

Answer all four questions (Price Extension, ERP Trend, Credit Confirmation, Breadth Confirmation) and assign:
- **Structural Bias:** Early Bull / Mid Bull / Late Bull–Topping / Bear Market
- **Monte Carlo Action Threshold:** 65% / 70% / 75%
- **23.6% Fib Rule:** Regime-appropriate (light re-entry vs. hard pause zone)

State the Structural Bias as the first line of the session analysis.

---

### Step 1: Price Action & Trend Recentering

- Log close, point change, % change
- State % below the 52-week/cycle high (or confirm new ATH)
- Calculate net recovery from the cycle/structural low
- Identify current SMA regime (Golden Cross / Death Cross / Transitional)
- Report **exact premium/discount** to 50-day and 200-day SMA
- Report **intraday close position:** top / middle / bottom third of day's range (with volume qualifier)
- Calculate and record: % above 200-day SMA → feeds momentum-adjusted μ for Step 5

---

### Step 2: Technical & Sentiment Pulse

**Momentum Indicators:**
- RSI-14: exact level; flag overbought (> 70), oversold (< 30), or divergence
- MFI: exact level; flag overbought (> 80), oversold (< 20), or divergence
- **Multi-timeframe context:** Note divergence forming on 1-month, 3-month, or 6-month charts

**Bands & Averages:**
- Bollinger Band position (upper pierce / lower pierce / within band / middle band test)
- Flag if close is above or below the 20-day SMA (middle band) — regime indicator

**Sentiment — All 7 CNN F&G Components:**

| Component | Reading | vs. Prior Session | Signal |
|---|---|---|---|
| Overall F&G | | | |
| Market Momentum (vs. 125-day MA) | | | |
| Stock Price Strength (new highs/lows) | | | |
| Stock Price Breadth (McClellan — vs. cycle low level) | | | |
| Put/Call Ratio | | | |
| Safe Haven Demand (stock/bond 20-day) | | | |
| Junk Bond Demand (spread + vs. 60-session avg) | | | |

Flag any internal divergences (headline vs. breadth, price vs. F&G direction, F&G falling on ATH sessions).

---

### Step 3: Fundamental Valuation & ERP

- **Trailing PE** = Current Close / Trailing 12-Month EPS
- **Forward PE** = Current Close / FactSet Consensus Forward EPS
- **Forward Earnings Yield** = 1 / Forward PE
- **ERP** = Forward Earnings Yield − 10-Year Treasury Yield
- Flag if ERP < 0.5% (fundamental ceiling — trim bias)
- Flag if ERP < 0.0% (negative — trim only)
- Note ERP trend: expanding or contracting vs. prior 20-session average
- State current dip-buying posture from the Forward PE calibration table
- **Calculate the SPX price level where ERP = 0.5%** (ERP-confirmed re-entry floor)

**Dynamic Valuation Ceiling Map** (recalculate each session using current Forward EPS):

| SPX Level | Forward PE | ERP vs. 10-Year | Interpretation |
|---|---|---|---|
| Current | Calculate | Calculate | State posture |
| Trim Wave 1 | 22x | Calculate | First trim trigger |
| Trim Wave 2 | 23x | Calculate | Second trim trigger |
| Trim Wave 3 | 24x | Calculate | Final trim trigger |

---

### Step 4: Leverage & Margin Debt Monitor

- **Margin Debt Divergence:** Note any structural divergence between latest FINRA data and current price action
- **Update Dynamic Liquidation Thresholds** from the current swing high:
  - Caution Zone (−3%): calculated price level
  - Nervous Zone (−5 to −7%): calculated price level
  - First Margin Call Wave (−10%): calculated price level
  - Forced Liquidation Cascade (−15%): calculated price level
- **VIX Catalyst:** Is VIX above 20? Above its own 50-day MA? State the risk implication clearly
- Note if any intraday price action breached a liquidation threshold (even if close recovered)

---

### Step 5: Monte Carlo & Brownian Motion

**Run in sequence:**

**5A — Set Parameters**
1. Calculate σ: use trailing 20-day realized vol (or VIX as proxy)
2. Calculate μ: apply momentum-adjusted drift based on % above 200-day SMA
3. Calculate Rally Exhaustion Score (Move Magnitude + Move Velocity + Vol Compression)
4. Confirm Effective Action Threshold from Pre-Step Structural Bias

**5B — Run 20,000-Path GBM Simulation**
- S₀ = today's close
- μ = momentum-adjusted (from 5A)
- σ = realized volatility (from 5A)
- Horizon = 60 trading days

**5C — Report All Required Outputs**
- σ used / μ used / Exhaustion Score / Effective Threshold
- First-Hit Probabilities (raw and adjusted)
- Does adjusted probability meet the Effective Threshold? **State explicitly: Yes / No**
- Conditional cascade probabilities — both upside and downside
- Median days to each key target
- GBM Drift Path: expected price at 5, 10, 20, 30, 60 days
- Drift Path Ceiling Check: if 60-day expected return < 2% → flag "easy gains consumed"
- Cash Drag: P(primary support never hit within 60 days)

---

### Step 6: Tactical Matrix — Trims & Re-entries

**Trim Ladder** (recalculate each session using current FactSet Forward EPS):

| Trim Wave | Fwd PE Trigger | Implied SPX Level | Suggested Shift |
|---|---|---|---|
| Wave 1 | 22x Forward PE | Calculated | 3–5% equity reduction |
| Wave 2 | 23x Forward PE | Calculated | 3–5% equity reduction |
| Wave 3 | 24x Forward PE | Calculated | 3–5% equity reduction |

**SMA/Fib Re-entry Zones:**
- Calculate Fib retracements (23.6%, 38.2%, 50%, 61.8%) from current cycle peak to cycle low
- Project 50-day SMA's daily rising rate forward
- Identify the exact price and calendar date where the 50-day SMA intersects the 38.2% or 50% Fib → **Primary Re-entry Zone**
- Report the Re-entry Confirmation Checklist status

**Cash Deployment Scale:**

| Fib Level | Deploy % of Trimmed Cash | Regime Condition |
|---|---|---|
| 23.6% | 0% in Mid/Late Bull — Pause zone | 10–15% in Early Bull only (PE < 18x, ERP > 2%) |
| 38.2% | 50% of trimmed cash | All regimes — primary re-entry |
| 50.0% | 25% of trimmed cash | All regimes — if 38.2% failed to hold |
| 61.8% / 50-day SMA convergence | 25% of trimmed cash | All regimes — maximum conviction add |

---

### Step 7: Narrative & Executive Summary

- Synthesize all prior steps into a concise 2–3 paragraph executive narrative
- State current base case (Bull / Bear / Neutral, 30–60 day horizon)
- Note the **single most important risk or opportunity** not captured by technicals alone
- Report the **Scenario Probability Table** (3 scenarios with probability, path, and action)
- **End with the Updated Decision Matrix**

**Updated Decision Matrix — Standard Format:**

| Signal Layer | Current Reading | Signal |
|---|---|---|
| **Structural Bias** | | Early Bull / Mid Bull / Late Bull / Bear |
| **Monte Carlo Threshold** | | 65% / 70% / 75% |
| **σ Used / μ Used** | | Dynamic values this session |
| **Rally Exhaustion Score** | | Low / Moderate / High |
| Trend Regime (SMA state) | | Bull / Bear / Neutral |
| Intraday Close Position | | Top / Mid / Bottom third + Vol |
| RSI / MFI state | | OB / OS / Neutral / Divergence |
| 20-day SMA (Middle Band) | | Above / Below — regime |
| Bollinger Band state | | Upper / Lower / Within |
| ERP state + trend | | Level + Expanding / Contracting |
| Junk Bond Spread | | Level + vs. 60-session avg |
| Leverage Risk state | | Elevated / Moderate / Low |
| McClellan Breadth | | Score + vs. cycle-low level |
| Put/Call Ratio | | Level + Complacency / Fear |
| F&G Overall | | Score + Zone + Direction |
| VIX | | Level + vs. 50-day MA |
| Monte Carlo Edge (adjusted) | | Actionable / Monitor / Insufficient |
| **SCORE** | **X RED / Y CAUTION / Z GREEN** | |
| **RECOMMENDED ACTION** | **[Action]** | **[Exact SCHK directive for next session]** |

---

## Re-entry Confirmation Checklist

Before deploying reserved cash at any Fib/SMA re-entry zone, require **3 of 4** conditions:
1. Close above prior session's high (momentum confirmation)
2. RSI inflection upward from below 35 (momentum turning)
3. McClellan Breadth uptick (broad participation beginning)
4. VIX reversal back below 20 (risk-off abating)

*If only 2 of 4 are met, deploy 50% of the planned tranche and wait for full confirmation before the remainder.*

**Valid re-entry pathways (either is sufficient):**
- **Pathway A (Highest conviction):** VIX spikes above 25–30 then collapses below 22 + 2-of-4 checklist
- **Pathway B (Standard):** Primary Fib/SMA zone reached + 3-of-4 checklist confirmed (VIX spike not required if Structural Bias is Early or Mid Bull)

---

## Risk Management Framework

1. **Never force a signal.** Mixed or ambiguous data → hold and monitor.
2. **Never recommend trimming the entire position.** Remaining equity always participates in unexpected melt-ups.
3. **Scale in, scale out.** Split re-entry across two Fib levels (e.g., 50% at 38.2%, 50% at 50%). Never deploy full cash if the market can fall further.
4. **VIX > 20 = elevated risk flag.** Note reduced reliability of moving averages and increased forced-selling risk. Reduce aggression but do not panic.
5. **Monte Carlo minimum = regime-adjusted threshold.** Below the session threshold (65/70/75%): insufficient edge — do not recommend action.
6. **The re-entry is never guaranteed.** If the market does not pull back to the target, hold cash patiently. Panic-buying at higher prices after trimming is the primary failure mode.
7. **GTC limit orders.** When a Trim Wave price is identified, a GTC limit sell order may be staged at that level. **Explicitly state when to cancel GTC orders** (e.g., when a corrective break below a key structural level invalidates the prior upside thesis).
8. **Defensive tripwire rule.** If price closes below a key structural level without a prior Trim Wave having been executed, a **partial defensive trim of 10–15%** may be executed to reduce exposure. This is capital preservation — distinct from a Trim Wave.
9. **Annual parameter review.** At the start of each calendar year, recalibrate base μ from trailing 10-year returns and validate the σ proxy approach. This prevents parameter drift across market cycles.

---

## Allocation Signal Reference Table

| Condition | Recommended Analysis | Output | Directional Bias |
|---|---|---|---|
| Price at 50-day resistance; RSI > 65; MFI > 70; F&G > 55 | Flag Trim Wave 1 level | Reduce equity | Trim bias |
| Above Trim Wave 1; Fwd PE > 23x; Monte Carlo ≥ threshold | Flag Trim Wave 2 level | Reduce further | Trim bias |
| Above Trim Wave 2; Fwd PE > 24x; ERP < 1% | Flag Trim Wave 3 level | Reduce further | Trim bias |
| 38.2% Fib + 50-day SMA convergence; RSI < 40; F&G < 40; 3-of-4 checklist | Flag Primary Re-entry Zone | Deploy 50% of cash | Re-entry |
| 50% Fib; RSI < 35; MFI divergence; F&G < 30 | Flag Secondary Re-entry Zone | Deploy 25% of remaining cash | Re-entry |
| 61.8% Fib + 50-day SMA convergence | Maximum conviction add | Deploy remaining cash | Re-entry |
| Price in channel between 50-day and 200-day SMA | No actionable setup | Hold and monitor | Neutral |
| Monte Carlo adjusted P < regime threshold | Insufficient edge | Wait for cleaner setup | Hold |
| VIX > 20 | Risk elevated — note implications | Reduce aggression | Caution |
| VIX > 30 then collapses below 22 | Highest-conviction re-entry signal | Deploy aggressively | Re-entry |
| Rally Exhaustion = High + Late Bull Structural Bias | Discount Monte Carlo upside 8 pts; raise threshold to 75% | Extreme caution on longs | Trim bias |

---

## Alpha Accumulation Math

For each trim/re-entry cycle, the additional shares accumulated as a percentage of the trimmed tranche:

**α = (R − S) / S**

Where R = trim/resistance price and S = re-entry/support price.

Executed 3–4 times per year across a meaningful portfolio, this compounds into material long-run outperformance vs. pure buy-and-hold.

---

## Version History & Key Rules Learned from Live Sessions

| Rule | Version Introduced | Source / Basis |
|---|---|---|
| CAPE is never used — only Trailing PE, Forward PE, ERP | V1 | Confirmed April 28, 2026 |
| 20-day SMA close-below = regime shift, not a dip | V2 | Confirmed May 19, 2026 |
| McClellan at cycle-low levels while price is near ATH = breadth capitulation | V2 | Confirmed May 11–19, 2026 |
| F&G falling for 3+ sessions while price makes ATHs = highest-priority topping signal | V2 | Confirmed May 26–June 2, 2026 |
| Intraday close in bottom third of range = distribution (with volume qualifier) | V2 | Confirmed June 3–8, 2026 |
| Junk bond spread widening 50+ bps vs. 60-session avg = warning (cycle-robust form) | V2/V3 | Confirmed June 2–10, 2026 |
| PutCall rising to 0.80+ + F&G Extreme Fear = contrarian bottoming watch | V2 | Confirmed June 10, 2026 |
| ERP < 0.5% = no aggressive longs; calculate SPX level where ERP = 0.5% | V2 | Confirmed May–June 2026 |
| GTC limit orders must be explicitly cancelled when thesis changes | V2 | Confirmed June 5, 2026 |
| 23.6% Fib = pause zone in Mid/Late Bull; light re-entry only in Early Bull | V2/V3 | Confirmed June 5–10, 2026 |
| σ must be dynamic (realized vol / VIX-based), not fixed at 20% | **V3** | Monte Carlo bias analysis June 2026 |
| μ must be momentum-adjusted (reduce drift when > 15% above 200-day) | **V3** | Monte Carlo bias analysis June 2026 |
| Rally Exhaustion Score (3 inputs) discounts upside-first GBM probabilities | **V3** | Monte Carlo bias analysis June 2026 |
| Structural Bias Pre-Step sets regime-adjusted Monte Carlo threshold (65/70/75%) | **V3** | Cycle-robustness analysis June 2026 |
| Relative junk bond spread (vs. 60-session avg) replaces absolute thresholds | **V3** | Cycle-robustness analysis June 2026 |
| McClellan compared to "level at most recent cycle low" replaces fixed threshold | **V3** | Cycle-robustness analysis June 2026 |
| Annual parameter review (μ and σ) at start of each calendar year | **V3** | Cycle-robustness analysis June 2026 |

---

*This is a living document, refined as market conditions evolve and each session generates new data.*
