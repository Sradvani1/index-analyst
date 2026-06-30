# Pass 2 payload — current assembled example (2026-06-29)

Annotated reconstruction of what `AnthropicClient.run_markdown_report()` sends.
Large JSON blocks are truncated; full text is in sibling files in this folder.

---

## Request metadata

```json
{
  "date": "2026-06-29",
  "system_role_chars": 2204,
  "framework_chars": 16645,
  "body_chars": 23066,
  "tool_schema_chars": 7018,
  "pass2_attached_images": [
    "01_spx_intraday.png",
    "02_spx_5day.png",
    "03_spx_1month.png",
    "04_spx_3month.png",
    "09_fear_greed_momentum.png",
    "10_breadth_52wk_highs_lows.png",
    "11_breadth_mcclellan.png",
    "14_safe_haven_demand.png",
    "15_junk_bond_spread.png"
  ],
  "pass2_reference_only": [
    "05_spx_6month.png",
    "06_spx_1year.png",
    "07_spx_3year.png",
    "08_fear_greed_index.png",
    "12_put_call_ratio.png",
    "13_vix_volatility.png"
  ]
}
```

---

## `system` — block 1: role + hard constraints

> Source: `framework/SPX-Claude-Role-Block.md` + `HARD_CONSTRAINTS` in `src/prompts.py`

```markdown
# SPX Claude Role Block

You are a technical, fundamental, quantitative, and sentiment analyst focused on tactical S&P 500 index analysis.

Your job is to apply the SPX Daily Analysis Framework exactly as written, using the full evidence set supplied for the current run, and produce a disciplined market-structure assessment that supports capital protection, tactical trims at resistance, and high-probability re-entry identification during pullbacks.

For each run:
- Complete the Structural Regime Classification first.
- Execute the seven analysis steps in exact order.
- Use the full chart pack and structured context for the current run.
- Treat the analysis as a single daily assessment of current market structure.
- Weigh confirming and conflicting evidence fairly.
- Prefer patience over forced conclusions when evidence is mixed.
- End with the completed Updated Decision Matrix.

The framework is the governing methodology. Follow it precisely and keep the final analysis clear, decisive, and internally consistent.

Non-negotiable constraints (from the framework):
- Complete Structural Regime Classification before Step 1; assign exactly one structural_bias.
- Signals are actionable only when multiple independent indicators align; mixed data means hold and monitor.
- Never use Monte Carlo output in isolation — interpret it through structural_bias and chart evidence.
- analysis_context is the sole numeric source of truth. Wherever the framework says "Calculate" (ERP, Fibonacci, drawdown/liquidation zones, volatility, drift, Monte Carlo), read and interpret the precomputed value instead — never recompute or adjust it. Chart labels never override analysis_context numerics.
- The engine deterministically re-derives spx_close, the Monte Carlo block, and the numeric decision-matrix rows after Pass 1, so spend your effort on the qualitative chart reads and structural_bias, not on transcribing numbers precisely.
- Pass 1: emit decision_matrix.rows with all 18 framework rows via emit_daily_state.
- Pass 2: prose only — eight ## sections ending with Evidence and Tensions; do not emit a # title, injected fact blocks, or Updated Decision Matrix (Python assembles those for publish).
```

**Note:** Block 1 still says “Execute the seven analysis steps” and “End with the Updated Decision Matrix” — Pass 2-specific overrides only appear in the last bullet of `HARD_CONSTRAINTS`.

---

## `system` — block 2: full framework (cached)

> Source: `framework/SPX-Daily-Analysis-Framework.md` (~16,645 chars, 491 lines)
>
> Full verbatim copy: [`_framework.md`](_framework.md)

Opening excerpt:

```markdown
# SPX Daily Analysis Framework

This framework governs a single daily analysis run for the S&P 500 Index. ...

## Purpose

The framework is built to answer five questions on every run:
1. What is the current structural market regime?
2. Is the market extended, balanced, or under pressure?
...

## Core Principles
- Signals are only actionable when multiple independent indicators align.
...
- Every run must end with a complete Updated Decision Matrix.

## Structural Regime Classification
Complete this section before Step 1. ...
```

The framework includes Step 1–7 workflow, valuation tables, Monte Carlo rules, trim/buy ladders, and the empty Decision Matrix template. **This is the main source of internal/methodology voice** competing with the brief “investor-facing” line in the Task block.

---

## `tools` — emit_daily_state (present but not invoked)

Pass 2 includes the same tool definition as Pass 1 so the cached system prefix matches. `tool_choice: none` prevents a tool call.

```json
{
  "name": "emit_daily_state",
  "description": "Emit the structured daily analysis state for the session.",
  "input_schema": { "$ref": "DailyState JSON Schema — 7018 chars" }
}
```

---

## `messages[0].content` — multimodal user turn

### Part A: images (9 × PNG, base64)

Order matches attached list in chart pack. Resized to `SPX_PASS2_IMAGE_MAX_DIMENSION` (default 1092px).

```
[image] 01_spx_intraday.png
[image] 02_spx_5day.png
[image] 03_spx_1month.png
[image] 04_spx_3month.png
[image] 09_fear_greed_momentum.png
[image] 10_breadth_52wk_highs_lows.png
[image] 11_breadth_mcclellan.png
[image] 14_safe_haven_demand.png
[image] 15_junk_bond_spread.png
```

### Part B: text body (`bundle.body`)

> Full verbatim copy: [`_user_body.md`](_user_body.md)

Sections in order:

#### 1. `## Precomputed analysis context` — JSON (~2.5k chars)

Immutable numerics: market_data, valuation, structure, monte_carlo.

```json
{
  "date": "2026-06-29",
  "market_data": { "spx_close": 7440.43, "vix": 17.65, "us10y": 4.374, ... },
  "valuation": { "forward_pe": 20.11, "erp": 0.006, ... },
  "structure": { "fib_500": 7407.89, "liquidation_caution": 7350.58, ... },
  "monte_carlo": { "prob_down_first_adjusted": 0.6594, ... }
}
```

#### 2. `## EPS inputs` — JSON

```json
{ "forward_eps": 370.0, "trailing_eps": 290.0, "effective_from": "2026-06-10", "source": "master" }
```

#### 3. `## Pass 2 chart pack`

Attached vs reference-only charts + authority rules (no pixel reads from reference-only).

#### 4. `## Read-only fact snippets`

Pre-rendered bullets for sections 5–7 (valuation, Monte Carlo, tactical levels). Model told **not to duplicate** these in prose.

#### 5. `## Validated daily state (immutable)` — JSON (~12k chars)

Full `DailyState` after Pass 1 + enforcement: signals, matrix rows, divergences, narrative fields.

#### 6. `## Conflict checklist (from validated state)`

```
Primary tension: ...
Structural bias: Late Bull / Topping
Signal alignment: trim 3/5, buy 0/5, overall mixed
Confirming evidence: ...
Conflicting evidence: [ JSON array of 3 divergences with chart_refs ]
```

#### 7. `## Task` — **this is where presentation/tone lives today**

```markdown
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
```

---

## Expected model output (Pass 2)

Eight `##` sections only → stored as `response_raw.report_pass_prose` → Python assembles final `{date}-analysis.md` with header, fact blocks, matrix.

---

## What is *not* in the payload

- Prior posture snapshot (`memory/rolling/recent_summary.md`) — omitted when `SPX_INCLUDE_MEMORY=false` (this example)
- The published report markdown
- Post-assembly divergence title rewrites (Python does this in `report_assembly.py`)
