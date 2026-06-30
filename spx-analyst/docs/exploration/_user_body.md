## Precomputed analysis context (immutable numeric truth for this run)
Use these values for ERP, structure, and Monte Carlo. Do not recalculate.
```json
{
  "date": "2026-06-29",
  "market_data": {
    "spx_close": 7440.4302,
    "vix": 17.65,
    "us10y": 4.374,
    "as_of_date": "2026-06-29",
    "pct_above_200dma": 7.373,
    "realized_vol_20d": 0.1753,
    "sma_50": 7371.4124,
    "sma_200": 6929.515,
    "precompute_warnings": []
  },
  "valuation": {
    "forward_pe": 20.11,
    "trailing_pe": 25.66,
    "forward_earnings_yield": 0.0497,
    "erp": 0.006,
    "erp_trend": "stable",
    "erp_reentry_floor_at_0_5pct": 7591.3
  },
  "structure": {
    "active_swing_high_date": "2026-06-15",
    "active_swing_high_price": 7577.9199,
    "swing_high_confirmation": "five_sessions",
    "active_swing_low_date": "2026-06-09",
    "active_swing_low_price": 7237.8501,
    "swing_low_confirmation": "above_50dma",
    "fib_236": 7497.66,
    "fib_382": 7448.01,
    "fib_500": 7407.89,
    "fib_618": 7367.76,
    "liquidation_caution": 7350.58,
    "liquidation_nervous": 7199.02,
    "liquidation_margin_call": 6820.13,
    "liquidation_cascade": 6441.23,
    "upside_target": 7577.92,
    "upside_target_rule": "active_swing_high",
    "downside_target": 7407.89,
    "downside_target_rule": "fib_500"
  },
  "monte_carlo": {
    "sigma": 0.1753,
    "mu": 0.07,
    "rally_exhaustion_score": "Low",
    "exhaustion_discount": 0.0,
    "upside_target": 7577.9199,
    "downside_target": 7407.885,
    "upside_target_rule": "active_swing_high",
    "downside_target_rule": "fib_500",
    "prob_up_first_raw": 0.3406,
    "prob_down_first_raw": 0.6594,
    "prob_up_first_adjusted": 0.3406,
    "prob_down_first_adjusted": 0.6594,
    "cascades": "If 7408 breaks, P(7368)=94%; If 7578 breaks, P(7673)=88%",
    "median_days": "upside 7d / downside 2d",
    "drift_path": "5d=7448.50; 10d=7456.58; 20d=7472.76; 30d=7488.98; 60d=7537.84",
    "cash_drag_prob": 0.1273,
    "threshold_evaluation": {
      "65": {
        "adjusted_prob_up_first": 0.3406,
        "actionable": false
      },
      "70": {
        "adjusted_prob_up_first": 0.3406,
        "actionable": false
      },
      "75": {
        "adjusted_prob_up_first": 0.3406,
        "actionable": false
      }
    }
  }
}
```

## EPS inputs (resolved from master history)
```json
{
  "forward_eps": 370.0,
  "trailing_eps": 290.0,
  "effective_from": "2026-06-10",
  "source": "master"
}
```

## Pass 2 chart pack
Date: 2026-06-29 | Index: SPX | Reference close (validation only): 7440.43017578125

Attached images (9) — inspectable evidence:
  1. SPX intraday price (1-day) [intraday] (01_spx_intraday.png)
  2. SPX 5-day with SMA 50/200, Bollinger Bands, RSI-14, MFI [5day] (02_spx_5day.png)
  3. SPX 1-month with SMA 50/200, Bollinger Bands, RSI-14, MFI [1month] (03_spx_1month.png)
  4. SPX 3-month with SMA 50/200, Bollinger Bands, RSI-14, MFI [3month] (04_spx_3month.png)
  5. Fear & Greed market momentum: S&P 500 vs 125-day MA [1year] (09_fear_greed_momentum.png)
  6. Stock price strength: net new 52-week highs/lows on NYSE [1year] (10_breadth_52wk_highs_lows.png)
  7. Stock price breadth: McClellan Volume Summation Index [1year] (11_breadth_mcclellan.png)
  8. Safe haven demand: difference in 20-day stock vs bond returns [1year] (14_safe_haven_demand.png)
  9. Junk bond demand: yield spread junk vs investment grade [1year] (15_junk_bond_spread.png)

Reference only (not attached) — filename visible, not visually inspectable:
  - SPX 6-month with SMA 50/200, Bollinger Bands, RSI-14, MFI [6month] (05_spx_6month.png)
  - SPX 1-year with SMA 50/200, Bollinger Bands, RSI-14, MFI [1year] (06_spx_1year.png)
  - SPX 3-year with SMA 50/200, Bollinger Bands, RSI-14, MFI [3year] (07_spx_3year.png)
  - CNN Fear & Greed Index overview [1year] (08_fear_greed_index.png)
  - 5-day average put/call ratio [1year] (12_put_call_ratio.png)
  - Market volatility: VIX and its 50-day MA [1year] (13_vix_volatility.png)

Authority: Attached images may be used for descriptive detail and conflict reconciliation.
Reference-only charts may be cited by filename and explained using validated state only.
Do NOT infer fresh numeric values, new divergences, or pixel-level observations from reference-only charts.

## Read-only fact snippets (Python injects these under sections 5–7 — do not duplicate numerics in prose)

**Valuation and ERP (section 5):**
- Forward P/E: 20.11x | Trailing P/E: 25.66x
- Forward earnings yield: 4.97%
- 10-year Treasury: 4.374%
- ERP: 0.60% (stable)
- ERP re-entry floor at 0.5% ERP: 7,591.30

**Risk and Monte Carlo (section 6):**
- σ (20d realized vol): 0.1753 | μ (drift): 0.0700
- Raw up-first: 34.1% | Raw down-first: 65.9%
- Adjusted up-first: 34.1% | Adjusted down-first: 65.9%
- Rally exhaustion: Low (discount 0%)
- Upside target: 7,577.92 (active_swing_high)
- Downside target: 7,407.89 (fib_500)
- Median days: upside 7d / downside 2d | Cascades: If 7408 breaks, P(7368)=94%; If 7578 breaks, P(7673)=88%

**Tactical levels (section 7):**
- Active swing high: 7,577.92 (2026-06-15)
- Active swing low: 7,237.85 (2026-06-09)
- Fib 23.6%: 7,497.66 | 38.2%: 7,448.01 | 50%: 7,407.89 | 61.8%: 7,367.76
- Liquidation caution: 7,350.58 | nervous: 7,199.02
- Margin call: 6,820.13 | cascade: 6,441.23

## Validated daily state (immutable)
```json
{
  "date": "2026-06-29",
  "framework_version": "daily-2026-06",
  "spx_close": 7440.43017578125,
  "structural_bias": "Late Bull / Topping",
  "base_case": "Over the next 30-60 days the base case is choppy, range-bound consolidation beneath the 7,578 swing-high resistance band, with price oscillating between the 38.2%/50% fib zone (~7,408-7,448) and the 23.6% fib (~7,498), while breadth and credit divergences keep a structural lid on durable upside. A clean reclaim of the 23.6% fib with breadth confirmation would re-open the highs; a daily close back below the 50% fib (7,408) re-arms the 94% conditional cascade toward the 61.8% fib (7,368) and the 7,351 caution/liquidation zone.",
  "trend_regime": "50-day SMA (7,371) above 200-day SMA (6,930) \u2014 mechanically bullish but the 50-day is flattening; price +7.4% over the 200-day (moderate-to-elevated extension) and reclaimed back above the 50-day on this bounce.",
  "valuation_bucket": "Forward PE 20.1x (cautious buying only at strong confluence); ERP 0.01% \u2014 valuation ceiling, trim bias, no aggressive adds.",
  "signals": {
    "pct_vs_50dma": 0.94,
    "pct_vs_200dma": 7.373,
    "bollinger_position": "Mid-to-upper band; price recovered off the lower-band region toward the middle band on the 5-day chart",
    "rsi14": 55.0,
    "mfi": 72.0,
    "vix_regime": "Standard operating regime: VIX 17.65, just below its 50-day MA (17.81); benign and below the 20 risk threshold.",
    "fear_greed": 27,
    "fear_greed_zone": "Fear",
    "put_call": 0.85,
    "high_yield_spread": 1.37,
    "intraday_close_position": "Top third of range \u2014 strong intraday close on the bounce day",
    "middle_band_regime": "Reclaimed and holding above the 20-day SMA after the late-June breakdown"
  },
  "what_changed_today": [
    "RECOVERY SNAP-BACK: close 7,440.43 (~+1.2% from prior ~7,354) reclaimed the flattening 50-day SMA (now +0.94% cushion vs prior -0.13% discount), the 50% fib (7,408) and the 38.2% fib (7,448 contested) \u2014 reversing the late-June breakdown into a fresh bounce attempt.",
    "MONTE CARLO STILL DOWN-FIRST BUT EASED: prob_down_first 65.9% (vs ~80% prior), prob_up_first 34.1%; fails all regime thresholds (65/70/75) but the down-skew is materially less extreme than the prior six sessions.",
    "ERP COLLAPSED TO ~0.01%: with price rallying into a static 10y (4.37%) and forward PE 20.1x, the valuation cushion is essentially zero; the 0.5% ERP re-entry floor (7,591) now sits well above spot.",
    "VIX COOLED BACK BELOW ITS 50-DAY MA: VIX 17.65 vs 50-day MA 17.81 \u2014 the late-June uptick reversed, volatility benign with no forced-selling pressure.",
    "BREADTH/CREDIT STILL REFUSE TO CONFIRM: McClellan ~900 (Extreme Fear, near lows), net new highs +1.46% (Fear), junk spread 1.37% (Extreme Fear, elevated) \u2014 the divergence vs the price bounce persists into a 12+ session streak."
  ],
  "narrative_summary": "A mechanically intact bull skeleton (50d > 200d, price +7.4% over the 200-day, benign sub-18 VIX) staged a sharp snap-back today, reclaiming the 50-day SMA, the 50% fib and the 38.2% fib on a strong top-third close. But the bounce runs straight into a zero-cushion ERP (~0.01%) pinned at the valuation ceiling, 12+ sessions of Extreme Fear breadth and widening credit that still refuse to confirm, and a Monte Carlo edge that \u2014 while less extreme than recent sessions \u2014 remains 65.9% down-first and fails every threshold. With sentiment at 27 (Fear) and the swing-high band (7,578) overhead, the justified posture is trim bias into strength, not chasing the bounce.",
  "open_questions": [
    "Can the reclaim of the 50-day SMA and 50% fib hold on a closing basis and extend to the 23.6% fib (7,498), or does the bounce fade back below 7,408 and re-arm the 94% cascade toward 7,368?",
    "Will breadth (McClellan ~900) and credit (junk spread 1.37%) finally turn up to confirm the price bounce, or does their 12+ session divergence cap the rally and presage another leg lower?",
    "Does the zero-cushion ERP (~0.01%) cap upside near the swing-high band, given valuation support sits far above spot at the 7,591 re-entry floor?"
  ],
  "decision_matrix": {
    "rows": [
      {
        "signal_layer": "Structural Bias",
        "current_reading": "Late Bull / Topping",
        "signal": "Late Bull / Topping"
      },
      {
        "signal_layer": "Monte Carlo Threshold",
        "current_reading": "70%",
        "signal": "70%"
      },
      {
        "signal_layer": "Volatility Input",
        "current_reading": "0.1753",
        "signal": "\u03c3=0.1753"
      },
      {
        "signal_layer": "Drift Input",
        "current_reading": "0.0700",
        "signal": "\u03bc=0.0700"
      },
      {
        "signal_layer": "Rally Exhaustion Score",
        "current_reading": "Low",
        "signal": "Low"
      },
      {
        "signal_layer": "Trend Regime",
        "current_reading": "50d (7,371) > 200d (6,930), 50d flattening; price +7.4% over 200d, reclaimed 50d",
        "signal": "Bullish but maturing"
      },
      {
        "signal_layer": "Intraday Close Position",
        "current_reading": "Top third of range \u2014 strong close on bounce day",
        "signal": "Bullish near-term"
      },
      {
        "signal_layer": "RSI / MFI State",
        "current_reading": "RSI ~55 (neutral, turning up); MFI ~72 (caution/approach trim)",
        "signal": "Neutral-to-caution"
      },
      {
        "signal_layer": "20-Day SMA Status",
        "current_reading": "Reclaimed and holding above 20-day SMA after late-June breakdown",
        "signal": "Short-term structure improving"
      },
      {
        "signal_layer": "Bollinger Band State",
        "current_reading": "Recovered off lower-band region toward middle/upper band",
        "signal": "Neutral, regime test passed near-term"
      },
      {
        "signal_layer": "ERP State and Trend",
        "current_reading": "ERP 0.60% / stable",
        "signal": "neutral"
      },
      {
        "signal_layer": "Credit Condition",
        "current_reading": "Junk spread 1.37%, elevated/widening (Extreme Fear)",
        "signal": "Credit warning \u2014 diverging"
      },
      {
        "signal_layer": "Breadth Condition",
        "current_reading": "McClellan ~900 near lows; net new highs +1.46% (Fear)",
        "signal": "Narrow/deteriorating \u2014 diverging"
      },
      {
        "signal_layer": "VIX Regime",
        "current_reading": "VIX 17.65, just below 50-day MA (17.81); standard regime, below 20",
        "signal": "Benign"
      },
      {
        "signal_layer": "Leverage Risk State",
        "current_reading": "Price reclaimed 50d; caution zone 7,351, nervous 7,199; no thresholds breached on close",
        "signal": "Contained"
      },
      {
        "signal_layer": "Monte Carlo Edge",
        "current_reading": "34%",
        "signal": "monitor below threshold"
      },
      {
        "signal_layer": "Overall Signal Balance",
        "current_reading": "Bounce reclaim and benign VIX vs zero-cushion ERP, diverging breadth/credit, down-first MC",
        "signal": "Mixed, trim-biased"
      },
      {
        "signal_layer": "Recommended Action",
        "current_reading": "Trim bias into strength toward the 23.6% fib / swing-high band; do not chase the bounce; re-entry requires breadth/credit confirmation",
        "signal": "Defensive \u2014 trim bias"
      }
    ]
  },
  "signal_alignment": {
    "trim_signals_met": 3,
    "buy_signals_met": 1,
    "overall": "aligned_trim"
  },
  "confirming_evidence": [
    "50d SMA (7,371) remains above 200d SMA (6,930); price +7.4% over the 200-day \u2014 bull skeleton mechanically intact (charts 06, 07).",
    "Strong snap-back today reclaimed the 50-day SMA, 50% fib (7,408) and 38.2% fib (7,448) on a top-third close (charts 01, 02, 03).",
    "VIX 17.65 sits just below its 50-day MA (17.81) and below the 20 risk threshold \u2014 benign volatility, no forced-selling pressure (chart 13).",
    "Reclaim of the 20-day SMA marks a short-term structural improvement after the late-June breakdown (chart 02).",
    "Monte Carlo down-first skew eased to 65.9% from ~80% in recent sessions \u2014 less extreme bearish tilt."
  ],
  "conflicting_evidence": [
    {
      "id": "breadth_credit_vs_bounce",
      "layers": [
        "Sentiment and Leverage",
        "Technical Structure"
      ],
      "bullish_read": "Price snapped back above the 50-day and mid-fib band on a strong close, suggesting buyers are defending the trend.",
      "bearish_read": "McClellan (~900, near lows) and net new highs (+1.46%, Fear) remain in divergence while junk spreads (1.37%) stay elevated/widening \u2014 12+ sessions of breadth and credit refusing to confirm the price bounce signals narrow leadership.",
      "framework_rule": "When breadth and credit both diverge from price, elevate caution even if price has not yet broken down.",
      "weight": "high",
      "chart_refs": [
        "10_breadth_52wk_highs_lows.png",
        "11_breadth_mcclellan.png",
        "15_junk_bond_spread.png"
      ]
    },
    {
      "id": "erp_ceiling_vs_rally",
      "layers": [
        "Fundamental Valuation",
        "Technical Structure"
      ],
      "bullish_read": "The rally reclaimed key fib and SMA structure with momentum turning up.",
      "bearish_read": "ERP collapsed to ~0.01% as price rallied into a static 4.37% 10y \u2014 a zero valuation cushion with the 0.5% re-entry floor (7,591) sitting above spot caps durable upside and argues for trimming, not adding.",
      "framework_rule": "ERP 0.0-0.5% = valuation ceiling, trim bias, no aggressive adds.",
      "weight": "high",
      "chart_refs": [
        "09_fear_greed_momentum.png",
        "14_safe_haven_demand.png"
      ]
    },
    {
      "id": "mc_downfirst_vs_intact_skeleton",
      "layers": [
        "Monte Carlo Probability Analysis",
        "Technical Structure"
      ],
      "bullish_read": "Intact 50d > 200d skeleton, reclaimed 50-day and benign VIX support continued recovery.",
      "bearish_read": "Monte Carlo remains 65.9% down-first and fails all regime thresholds (65/70/75); if 7,408 breaks, P(7,368)=94% \u2014 the probability edge does not support adding into the bounce.",
      "framework_rule": "Never use Monte Carlo in isolation; if adjusted probability does not meet the regime threshold the setup is not actionable.",
      "weight": "medium",
      "chart_refs": [
        "02_spx_5day.png",
        "04_spx_3month.png"
      ]
    }
  ],
  "primary_tension": "A sharp mechanical snap-back \u2014 reclaim of the flattening 50-day SMA, the 50% and 38.2% fibs on a strong top-third close with a benign sub-18 VIX \u2014 is colliding with a zero-cushion ERP (~0.01%) pinned at the valuation ceiling, 12+ sessions of Extreme Fear breadth and widening credit that still refuse to confirm, and a Monte Carlo edge that remains 65.9% down-first and fails every threshold, leaving trim bias into strength rather than chasing the bounce as the justified posture.",
  "monte_carlo": {
    "effective_threshold": 70,
    "meets_threshold": false,
    "prob_up_first_raw": 0.3406,
    "prob_down_first_raw": 0.6594,
    "prob_up_first_adjusted": 0.3406,
    "prob_down_first_adjusted": 0.6594,
    "sigma": 0.175317,
    "mu": 0.07,
    "upside_target": 7577.919921875,
    "downside_target": 7407.885009765625,
    "rally_exhaustion_score": "Low",
    "conditional_cascade": "If 7408 breaks, P(7368)=94%; If 7578 breaks, P(7673)=88%",
    "median_days": "upside 7d / downside 2d",
    "drift_path": "5d=7448.50; 10d=7456.58; 20d=7472.76; 30d=7488.98; 60d=7537.84",
    "cash_drag_prob": 0.1273
  }
}
```

## Conflict checklist (from validated state)
Primary tension: A sharp mechanical snap-back — reclaim of the flattening 50-day SMA, the 50% and 38.2% fibs on a strong top-third close with a benign sub-18 VIX — is colliding with a zero-cushion ERP (~0.01%) pinned at the valuation ceiling, 12+ sessions of Extreme Fear breadth and widening credit that still refuse to confirm, and a Monte Carlo edge that remains 65.9% down-first and fails every threshold, leaving trim bias into strength rather than chasing the bounce as the justified posture.

Structural bias: Late Bull / Topping
Signal alignment: trim 3/5, buy 1/5, overall aligned_trim

Confirming evidence:
- 50d SMA (7,371) remains above 200d SMA (6,930); price +7.4% over the 200-day — bull skeleton mechanically intact (charts 06, 07).
- Strong snap-back today reclaimed the 50-day SMA, 50% fib (7,408) and 38.2% fib (7,448) on a top-third close (charts 01, 02, 03).
- VIX 17.65 sits just below its 50-day MA (17.81) and below the 20 risk threshold — benign volatility, no forced-selling pressure (chart 13).
- Reclaim of the 20-day SMA marks a short-term structural improvement after the late-June breakdown (chart 02).
- Monte Carlo down-first skew eased to 65.9% from ~80% in recent sessions — less extreme bearish tilt.

Conflicting evidence (re-examine cited charts for each):
```json
[
  {
    "id": "breadth_credit_vs_bounce",
    "layers": [
      "Sentiment and Leverage",
      "Technical Structure"
    ],
    "bullish_read": "Price snapped back above the 50-day and mid-fib band on a strong close, suggesting buyers are defending the trend.",
    "bearish_read": "McClellan (~900, near lows) and net new highs (+1.46%, Fear) remain in divergence while junk spreads (1.37%) stay elevated/widening \u2014 12+ sessions of breadth and credit refusing to confirm the price bounce signals narrow leadership.",
    "framework_rule": "When breadth and credit both diverge from price, elevate caution even if price has not yet broken down.",
    "weight": "high",
    "chart_refs": [
      "10_breadth_52wk_highs_lows.png",
      "11_breadth_mcclellan.png",
      "15_junk_bond_spread.png"
    ]
  },
  {
    "id": "erp_ceiling_vs_rally",
    "layers": [
      "Fundamental Valuation",
      "Technical Structure"
    ],
    "bullish_read": "The rally reclaimed key fib and SMA structure with momentum turning up.",
    "bearish_read": "ERP collapsed to ~0.01% as price rallied into a static 4.37% 10y \u2014 a zero valuation cushion with the 0.5% re-entry floor (7,591) sitting above spot caps durable upside and argues for trimming, not adding.",
    "framework_rule": "ERP 0.0-0.5% = valuation ceiling, trim bias, no aggressive adds.",
    "weight": "high",
    "chart_refs": [
      "09_fear_greed_momentum.png",
      "14_safe_haven_demand.png"
    ]
  },
  {
    "id": "mc_downfirst_vs_intact_skeleton",
    "layers": [
      "Monte Carlo Probability Analysis",
      "Technical Structure"
    ],
    "bullish_read": "Intact 50d > 200d skeleton, reclaimed 50-day and benign VIX support continued recovery.",
    "bearish_read": "Monte Carlo remains 65.9% down-first and fails all regime thresholds (65/70/75); if 7,408 breaks, P(7,368)=94% \u2014 the probability edge does not support adding into the bounce.",
    "framework_rule": "Never use Monte Carlo in isolation; if adjusted probability does not meet the regime threshold the setup is not actionable.",
    "weight": "medium",
    "chart_refs": [
      "02_spx_5day.png",
      "04_spx_3month.png"
    ]
  }
]
```

## Task
Pass 1 already completed in a separate API call — structured state was emitted via `emit_daily_state`. Do NOT call tools or emit JSON in this pass. Your entire response must be markdown prose only.

Write investor-facing narrative for an already-decided posture. The validated state is final: do not introduce or imply signal readings that contradict its structural_bias, signal_alignment, decision_matrix, or recommended action. Your job is exposition and reconciliation, not re-deciding.

Recommended action (verbatim): 'Defensive — trim bias'.

Re-open charts only to add descriptive detail and to reconcile the conflicts already listed in the conflict checklist — not to form new conclusions.

Output exactly these eight `##` sections in order — nothing else:
1. `## Today's Posture`
2. `## Market Regime`
3. `## Price and Trend`
4. `## Technicals and Sentiment`
5. `## Valuation and ERP`
6. `## Risk and Monte Carlo`
7. `## Tactical Levels and Next Session Plan`
8. `## Evidence and Tensions`

Do NOT emit:
- A `#` title line or Header Snapshot (Python assembles the preamble)
- Injected numeric fact blocks under sections 5–7 (Python inserts them during assembly)
- `## Updated Decision Matrix` (Python renders the matrix from validated state)

Tone: write for market participants, not internal framework review. No methodology meta-commentary (e.g. 'Step 2 requires…'). Do not regenerate numerics in prose where Python injects a facts block — interpret the read-only snippets instead.

Section budgets: Today's Posture 150–250 words (lead with action); Market Regime 200–300; Price and Trend through Tactical Levels 150–350 each; Evidence and Tensions ≥100 words when no divergences remain.

`## Evidence and Tensions` is required every run. For each item in conflicting_evidence from the conflict checklist, give the bullish read, the bearish read, and how the framework rule resolves it. On zero-divergence days, cover primary_tension and confirming evidence explicitly.

Pass 2 chart authority:
- Attached images: reconciliation and descriptive detail for listed conflicts only where cited.
- Reference-only charts: workflow citations from validated state / conflict checklist text only.
- Do not contradict validated state.
- Prior-run posture block (if present): continuity only — not today's chart evidence.
- When attached-image impressions, prompt wording, and validated daily state differ, validated daily state is authoritative.