# SPX Daily Analysis Framework

This framework governs a single daily analysis run for the S&P 500 Index. It is designed for use with a complete daily chart pack and a fully populated structured context payload for that run. The goal is to produce a disciplined, repeatable market-structure analysis that supports capital protection, tactical trims at resistance, and high-probability re-entry identification during pullbacks.

This is a daily analysis framework even when runs are performed intermittently. Every run must be treated as a fresh analysis of the current market state using the full evidence set provided for that date.

---

## Purpose

The framework is built to answer five questions on every run:

1. What is the current structural market regime?
2. Is the market extended, balanced, or under pressure?
3. Is valuation supportive, neutral, or restrictive?
4. Does the evidence support action, patience, or defense?
5. What is the exact tactical posture for the next session?

The framework is not designed to force trades. Its job is to organize the evidence, weigh signal quality, and translate the full market structure into a clear tactical posture.

---

## Analytical Layers

Every daily run uses five analytical layers:

| Layer | Frequency | Purpose |
|---|---|---|
| Structural Regime Classification | Every run, before Step 1 | Establish the master market context |
| Fundamental Valuation | Every run | Define the valuation floor and ceiling |
| Technical Structure | Every run | Map trend, extension, support, resistance, and momentum |
| Sentiment and Leverage | Every run | Measure psychology, breadth, credit, and forced-selling risk |
| Monte Carlo Probability Analysis | Every run | Quantify edge using dynamic, regime-aware parameters |

---

## Core Principles

- Signals are only actionable when multiple independent indicators align.
- Mixed or ambiguous evidence does not justify action.
- The framework favors disciplined scaling over all-in or all-out decisions.
- Tactical trims and re-entries must be tied to price structure, valuation context, and confirmation signals.
- The framework is sequence-dependent: the Structural Regime Classification must be completed first, and the seven workflow steps must then be executed in order.
- Every run must end with a complete Updated Decision Matrix.

---

## Structural Regime Classification

Complete this section before Step 1. It establishes the master context for the entire run and determines how later signals should be weighted.

Answer all four questions:

### 1. Price Extension vs. 200-Day SMA

| % Above 200-Day SMA | Interpretation |
|---|---|
| Below 5% | Normal extension |
| 5% to 10% | Moderate extension |
| 10% to 15% | Elevated extension |
| Above 15% | Extreme extension |
| Below the 200-day SMA | Recovery or bearish regime context |

### 2. Equity Risk Premium Trend

Evaluate both the current ERP level and its direction versus the prior 20-session average.

| ERP Condition | Interpretation |
|---|---|
| Expanding | Structural support improving |
| Stable | Neutral backdrop |
| Contracting | Structural support weakening |


### 3. Credit Confirmation

Use junk bond spread direction, not just the absolute level.

| Spread Trend | Interpretation |
|---|---|
| Tightening | Credit confirms equity strength |
| Flat | Neutral |
| Widening | Credit diverges from equity strength |

### 4. Breadth Confirmation

Use both the McClellan trend and the new highs/new lows context.

| Breadth Condition | Interpretation |
|---|---|
| Rising breadth and expanding participation | Broad participation |
| Flat breadth | Mixed backdrop |
| Falling breadth and contracting participation | Narrow or deteriorating market |

### Structural Bias Output

Assign one regime:

| Regime | Typical Conditions | Monte Carlo Threshold | 23.6% Fib Rule |
|---|---|---|---|
| Early Bull | Price not extended, ERP supportive, breadth improving, credit confirming | 65% | Light re-entry can be valid |
| Mid Bull | Healthy trend, moderate extension, mixed but intact internals | 65% | Pause zone, monitor only |
| Late Bull / Topping | High extension, low ERP, breadth divergence, credit warning | 70% | Hard pause zone, no deployment |
| Bear Market | Trend deterioration, poor breadth, weak credit, unstable valuation support | 75% | Reset pullback logic from fresh lows |

State the Structural Bias explicitly before continuing.

---

## Fundamental Valuation Framework

### Equity Risk Premium

Calculate:
- Forward PE
- Forward Earnings Yield
- 10-Year Treasury Yield
- Equity Risk Premium

Use the following posture guide:

| ERP Level | Interpretation | Posture |
|---|---|---|
| Above 2.0% | Strong valuation cushion | Aggressive dip-buying supported |
| 1.0% to 2.0% | Moderate cushion | Standard dip-buying posture |
| 0.5% to 1.0% | Thin cushion | Reduced aggression |
| 0.0% to 0.5% | Valuation ceiling | Trim bias, no aggressive adds |
| Below 0.0% | Equities worse than risk-free yield | Trim only |

Also calculate the SPX price level at which ERP would rise back to 0.5%. This becomes the ERP-confirmed re-entry floor for the run.

### Forward PE Calibration

| Forward PE | Posture |
|---|---|
| Below 18x | Aggressive buying at support |
| 18x to 20x | Moderate buying at support |
| 20x to 22x | Cautious buying only at strong confluence |
| 22x to 24x | Conservative posture, trim bias increasing |
| Above 24x | Trim ladder fully active |

---

## Technical Structure Framework

### SMA Trend Regime

Report the exact premium or discount of price to the 50-day and 200-day SMA on every run.

| Condition | Interpretation |
|---|---|
| 50-day above 200-day and stable | Healthy bullish regime |
| 50-day above 200-day but flattening | Bullish, but maturing |
| 50-day weakening toward 200-day | Caution |
| 50-day below 200-day | Bearish regime |

Also track the 125-day moving average because it provides an additional trend check and momentum context.

### Bollinger Bands

| Condition | Interpretation |
|---|---|
| Upper band pierce | Extension / possible trim window |
| Walking upper band | Strong but extended trend |
| Lower band pierce | Oversold / possible re-entry watch |
| Middle band test | Regime test |

A close below the 20-day SMA after an extended advance is a regime shift, not just a normal dip. A close back above the 20-day SMA after a breakdown is a meaningful improvement in short-term structure.

### RSI and MFI

Evaluate RSI and MFI across the supplied timeframes.

| Signal Zone | RSI | MFI |
|---|---|---|
| Trim zone | Above 70 | Above 80 |
| Caution / approach trim | 65 to 70 | 70 to 80 |
| Neutral | 45 to 55 | 45 to 55 |
| Buy watch | 30 to 35 | 20 to 30 |
| Buy zone | Below 30 | Below 20 |

High-conviction interpretation rules:
- Bearish divergence: price makes a higher high while MFI or RSI makes a lower high.
- Bullish divergence: price makes a lower low while MFI or RSI makes a higher low.
- MFI falling below 50 during a decline confirms institutional selling pressure.

Longer timeframe divergences carry more weight than short-term ones.

### Intraday Structure

Do not analyze only the close. Report where the close occurred within the daily range.

| Close Position | Interpretation |
|---|---|
| Top third of range | Strong close |
| Middle third | Neutral close |
| Bottom third | Weak / distribution-style close |


---

## Fibonacci and Re-entry Framework

Use the most recent meaningful swing high and swing low provided by the current setup.

Calculate:
- 23.6% retracement
- 38.2% retracement
- 50.0% retracement
- 61.8% retracement

Use the following framework:

| Fib Level | Interpretation | Typical Use |
|---|---|---|
| 23.6% | Shallow pullback | Pause zone, not the default buy point |
| 38.2% | Healthy correction | Primary re-entry zone |
| 50.0% | Deeper correction | Secondary re-entry zone |
| 61.8% | Deep correction | Maximum-conviction re-entry zone |

### 23.6% Rule

The 23.6% retracement is not a standard re-entry trigger. In Early Bull conditions it can support a light re-entry only when valuation and breadth are supportive. In Mid Bull and Late Bull conditions it is a pause zone and monitoring level, not a deployment level.

### SMA / Fib Convergence

Project the rising rate of the 50-day SMA forward and identify whether it converges with the 38.2% or 50% retracement. That convergence zone is the highest-priority re-entry structure in the framework.

---

## Sentiment and Leverage Framework

### Fear and Greed Structure

Review the full sentiment complex, not just the headline reading. Use the supplied sentiment components to identify whether internal conditions confirm or contradict the headline score.

Important patterns:
- Headline strength with weak breadth indicates narrow leadership.
- Falling sentiment during or near new highs is a topping warning.
- Fast collapses in sentiment can create re-entry watch conditions, but only with technical confirmation.

### Put / Call Context

| Put / Call Condition | Interpretation |
|---|---|
| Deep complacency | Trim warning |
| Rising fear from low levels | Early bottoming watch |
| Heavy hedging | Contrarian buy watch |

A rising put/call ratio from complacent levels matters more than the number in isolation.

### Credit Context

Use junk bond spreads in both absolute and relative terms. Relative widening versus the recent average is the more robust signal.

| Credit Condition | Interpretation |
|---|---|
| Tightening spreads | Risk appetite confirming |
| Flat spreads | Neutral |
| Widening spreads | Credit warning |
| Sustained widening well above recent average | Escalating caution or alarm |

### VIX Regime

| VIX Zone | Interpretation |
|---|---|
| Below 15 | Complacent regime |
| 15 to 20 | Standard operating regime |
| Above 20 | Elevated risk; moving averages less reliable |
| Above 30 | Crisis regime |

A VIX spike into the 25 to 30+ zone followed by a reversal lower is a high-quality re-entry signal. A correction that unfolds without that volatility spike should be treated as orderly rather than capitulative.

### Margin and Liquidation Structure

Calculate dynamic drawdown thresholds from the most recent swing high.

| Zone | Drop from Swing High | Interpretation |
|---|---|---|
| Caution Zone | 3% | Early warning |
| Nervous Zone | 5% to 7% | Late buyers go underwater |
| First Margin Call Wave | 10% | Forced selling risk rises sharply |
| Forced Liquidation Cascade | 15% | Systematic unwind risk increases |

These are acceleration zones, not predictions.

---

## Monte Carlo Probability Framework

The Monte Carlo layer is used to quantify edge, not to define the market structure by itself. It must always be interpreted through the Structural Bias and the other analytical layers.

### Dynamic Inputs

#### Volatility Input

Do not use a fixed volatility assumption. Use the supplied realized volatility or VIX-based volatility input for the current run.

| Volatility Condition | Use |
|---|---|
| Low realized volatility / low VIX | Tighter probability ranges |
| Moderate volatility | Standard simulation conditions |
| Elevated volatility | Wider tails and greater caution |
| Crisis volatility | Technical levels less reliable |

#### Drift Input

Do not use a static bullish drift after a highly extended rally. Adjust drift based on price extension versus the 200-day SMA.

| % Above 200-Day SMA | Drift Guidance |
|---|---|
| Below 5% | Full long-run drift can apply |
| 5% to 10% | Slightly reduced drift |
| 10% to 15% | Meaningfully reduced drift |
| Above 15% | Minimal drift benefit; mean reversion pressure elevated |
| Below 200-day SMA | Recovery dynamics can justify fuller drift |

### Rally Exhaustion Score

Before interpreting the simulation, classify the move using three inputs:
- Move magnitude from the latest structural low
- Move velocity over calendar time
- Volatility compression relative to the recent baseline

| Exhaustion Score | Interpretation |
|---|---|
| Low | Use probabilities at face value |
| Moderate | Discount upside probabilities modestly |
| High | Discount upside probabilities materially |

### Required Monte Carlo Outputs

Every run must report:
- Volatility input used
- Drift input used
- Rally Exhaustion Score
- Effective action threshold based on Structural Bias
- First-hit probabilities
- Conditional cascade probabilities in both directions
- Median days to key levels
- Drift path expected levels
- Whether the adjusted probability meets the action threshold

### Threshold Rules

| Structural Bias | Action Threshold |
|---|---|
| Early Bull | 65% |
| Mid Bull | 65% |
| Late Bull / Topping | 70% |
| Bear Market | 75% |

If the adjusted probability does not meet the threshold for that regime, the setup is not actionable.

---

## Daily Seven-Step Workflow

Execute in this exact order after the Structural Regime Classification is complete.

### Step 1: Price Action and Trend Recentering

Report:
- Current close
- Point change and percentage change
- Distance from the cycle or 52-week high
- Recovery from the latest structural low
- SMA regime
- Exact premium or discount to 50-day and 200-day SMA
- Intraday close position within the daily range
- % above or below the 200-day SMA

### Step 2: Technical and Sentiment Pulse

Report:
- RSI and MFI readings across supplied timeframes
- Any bullish or bearish divergences
- Bollinger Band position
- 20-day SMA regime status
- Sentiment complex interpretation
- Breadth confirmation or divergence
- Credit confirmation or divergence

### Step 3: Fundamental Valuation and ERP

Report:
- Trailing PE
- Forward PE
- Forward Earnings Yield
- 10-year Treasury Yield
- ERP
- ERP trend versus the recent average
- ERP-confirmed re-entry floor
- Current valuation posture

### Step 4: Leverage and Liquidation Structure

Report:
- Credit and leverage warning state
- Dynamic drawdown thresholds from the current swing high
- VIX regime and implications
- Whether any risk thresholds were breached

### Step 5: Monte Carlo and Brownian Motion

Report:
- Dynamic volatility input
- Dynamic drift input
- Rally Exhaustion Score
- Regime-specific threshold
- Raw and adjusted probabilities
- Conditional cascade probabilities
- Median days to key levels
- Drift path expectations
- Whether the setup is actionable

### Step 6: Tactical Matrix

Report:
- Current trim posture
- Current re-entry posture
- Fibonacci levels
- SMA / Fib convergence zone
- Which level is primary, secondary, and maximum-conviction support
- Whether current conditions justify action, patience, or defense

### Step 7: Narrative and Executive Summary

Synthesize the full market structure into a concise final readout that states:
- The Structural Bias
- The base case over the next 30 to 60 days
- The strongest confirming signal
- The biggest unresolved risk
- The exact tactical posture for the next session

End with the Updated Decision Matrix.

---

## Re-entry Confirmation Checklist

Before treating a pullback zone as an actionable re-entry, require at least three of the following four conditions unless the broader structure is unusually favorable:

1. Close above the prior session's high
2. RSI turning up from a depressed reading
3. Breadth improving
4. VIX reversing lower from an elevated reading

If only two conditions are satisfied, treat the setup as partial confirmation and reduce aggression.

---

## Risk Management Rules

- Never force a signal.
- Never treat a mixed setup as a green light.
- Never use the Monte Carlo output in isolation.
- When VIX is above 20, reduce confidence in moving-average support.
- When structural conditions are late-cycle or topping, require a higher bar for bullish action.
- When breadth and credit both diverge from price, elevate caution even if price has not yet broken down.
- When re-entry conditions are incomplete, patience is the default posture.

---

## Updated Decision Matrix

Every run must end with this table completed using the current session's evidence.

| Signal Layer | Current Reading | Signal |
|---|---|---|
| Structural Bias | | |
| Monte Carlo Threshold | | |
| Volatility Input | | |
| Drift Input | | |
| Rally Exhaustion Score | | |
| Trend Regime | | |
| Intraday Close Position | | |
| RSI / MFI State | | |
| 20-Day SMA Status | | |
| Bollinger Band State | | |
| ERP State and Trend | | |
| Credit Condition | | |
| Breadth Condition | | |
| VIX Regime | | |
| Leverage Risk State | | |
| Monte Carlo Edge | | |
| Overall Signal Balance | | |
| Recommended Action | | |

The Recommended Action must express the tactical posture clearly and unambiguously for the next session.
