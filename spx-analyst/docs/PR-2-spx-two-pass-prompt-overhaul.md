# PR-2: SPX Two-Pass Prompt Overhaul

**Status:** Complete  
**Framework version:** `daily-2026-06`  
**Test suite:** 77 tests passing (`pytest`)  
**Builds on:** [PR-1: SPX Daily Framework Engine Migration](PR-1-spx-daily-framework-migration.md)

---

## Summary

PR-1 moved all numerics to Python (Step 0 precompute) and added deterministic
post-Pass-1 enforcement (`state_enforcement.py`), but the prompt text still carried
pre-migration instructions telling the model to compute or transcribe numbers the
engine now owns and overwrites. This PR reconciles the two-pass prompts with the
PR-1 architecture and closes the fidelity gaps that prompt wording alone cannot fix.

It does four things:

1. **Removes conflicting / redundant prompt instructions** so Pass 1 spends effort on
   the qualitative reads it uniquely owns (chart evidence + `structural_bias`) instead
   of numbers the engine re-derives.
2. **Fixes a live enforcement bug** — an inverted ERP signal mapping in
   `state_enforcement.py` that wrote the wrong `ERP State and Trend` into the decision
   matrix on every expanding/contracting day.
3. **Adds an always-on Pass 2 contradiction gate** so a report that diverges from the
   validated state fails validation, not just prompt wording.
4. **Aligns the prompt-cache prefix across both passes** (the only cross-pass reuse the
   forced-tool design allows) and adds request-snapshot instrumentation.

Scope is intentionally broader than a prompt refactor: a prompt-and-client-only change
could not claim the fidelity conflicts were resolved while `state_enforcement.py` still
emitted an inverted signal. The canonical framework markdown and the `DailyState` schema
are **left untouched**.

---

## Motivation

| Problem (before) | Solution (after) |
|------------------|------------------|
| Framework "Calculate ..." verbs conflicted with the wrapper's "do not recalculate" (C1) | Precompute-authority preamble reframes every "Calculate" as "interpret the precomputed value" |
| Pass 1 elaborately copied Monte Carlo numbers that enforcement overwrites wholesale (C2, R1–R2) | One line states the engine re-derives them; the injected threshold JSON and `spx_close` step are removed |
| 7 of 18 matrix rows were reasoned out by the model, then overwritten (R3) | Model emits `(engine-filled)` placeholders for those 7; focuses on the 11 qualitative rows |
| Pass 2 declared the state immutable yet said "re-open charts", risking silent drift (C3) | Explicit exposition-only lock; chart re-reading bounded to descriptive color + reconciliation |
| `_erp_signal` mapped `expanding → caution`, `contracting → attractive` — inverted vs the framework (C5) | Swapped to `expanding → attractive`, `contracting → caution`, `stable → neutral` |
| State/report contradictions only caught on mixed/hold days | Always-on `_validate_state_consistency` runs whenever a `daily_state` is supplied |
| Float32 noise (`7266.990234375`) cluttered prompt echoes (C4, Q6) | Prompt-only `_round_floats`; persisted `analysis_context.json` unchanged |
| Pass 2 reused nothing from Pass 1 (mismatched tool sets invalidated the whole cache) | Both passes send byte-identical `tools`; Pass 2 reuses the framework + tool-schema cache prefix |

---

## Issue → Solution map

### Conflicts
- **C1 — Framework "Calculate" vs wrapper "do not recalculate."** Precompute-authority
  preamble in `HARD_CONSTRAINTS` / `load_system_role` reframes every framework
  "Calculate" as "interpret the precomputed value"; `analysis_context` is declared the
  sole numeric source of truth.
- **C2 — Pass 1 copied Monte Carlo numbers that enforcement overwrites.** Condensed to a
  single line stating the engine re-derives `spx_close`, the Monte Carlo block, and the
  numeric matrix rows; effort redirected to qualitative reads.
- **C3 — Pass 2 immutability vs "re-open charts."** Added an explicit exposition-only
  lock and bounded chart re-reading to descriptive detail + reconciliation only.
- **C4 — Two close values in-prompt** (`7266.99` vs `7266.990234375`). Float rounding
  (Q6) makes echoes visually consistent; the "validation only" label is retained.
- **C5 — Inverted ERP signal in enforcement (live bug).** `_erp_signal` mapped
  `expanding → "caution"` and `contracting → "attractive"`, the opposite of the
  framework (expanding ERP = structural support improving; contracting = weakening).
  The synced `ERP State and Trend` matrix signal was inverted on every
  expanding/contracting day. Fixed to `expanding → "attractive"`,
  `contracting → "caution"`, `stable → "neutral"`. The sample fixture used
  `erp_trend="stable"`, so no prior test exercised the inverted branches; new regression
  tests now cover both.

### Redundancy (no-ops because enforcement overwrites the output)
- **R1** — The 65/70/75 threshold map appeared up to 4×, including injected JSON in the
  Pass 1 task. Injected JSON removed.
- **R2** — "Set `spx_close` from analysis_context" was overwritten downstream. Removed as
  a numbered step.
- **R3** — 7 of 18 matrix rows were model-built then overwritten by
  `sync_matrix_precomputed_rows`. Reframed: the model emits schema-valid
  `(engine-filled)` placeholders for those rows and focuses on the 11 qualitative rows.

### Quality / fidelity
- **Q3** — Elevated `structural_bias` to the explicit primary Pass-1 task (it is the one
  high-leverage, non-overwritten output and selects the Monte Carlo threshold),
  justified against extension, ERP, credit, and breadth.
- **Q4** — Pass 2 exposition-only lock forbids introducing readings that contradict the
  validated state.
- **Q5** — Evidence Reconciliation must address each listed divergence by `id`
  (`DIV-1`, …). Because `div.id` lowercases to `div-1`, this makes the existing
  `_conflict_addressed` token match fire for the right reason.
- **Q6** — Prompt-only rounding of `analysis_context` floats for cleaner echoes;
  persisted `analysis_context.json` is unchanged.

### Token optimization / observability
- **O1 (revised) — Cross-pass tools+system caching.** Image caching across passes is
  **not achievable** here. Anthropic's cache prefix order is `tools → system → messages`;
  images live in the messages layer. Pass 1 forces the tool (`tool_choice: tool`) while
  Pass 2 must not, and a differing `tool_choice` invalidates the messages-layer cache, so
  the image prefix can never be read across the two passes (an image breakpoint would only
  add a ~1.25× write surcharge on the largest segment). What **is** reusable: when both
  passes send byte-identical `tools`, Pass 2 reads the framework + tool schema
  (tools+system layer, ~6k tokens) from Pass 1's cache despite the different
  `tool_choice`. Implementation: a shared `_state_tool()` on both passes; Pass 2 uses
  `tool_choice: {"type": "none"}` so it still returns markdown. **No image cache
  breakpoint is added.** Net saving is modest, not the order-of-magnitude image reduction
  originally assumed.
- **O5 (verify)** — Confirm `SPX_PROMPT_CACHE_ENABLED=true` in the run environment (the
  `prompt_cache_enabled` default is `True`, but the 2026-06-10 snapshot showed
  `framework_cached: false`).
- **O6 (observability)** — `_snapshot` records `framework_cached` and `image_count`. The
  `images_cached` flag was dropped (images are not cached, so it would always be false);
  actual reuse is verified from `response.usage.cache_read_input_tokens`.

### Clarifications
1. **Divergence-id coverage scope.** The Pass 2 prompt asks the model to address *every*
   listed divergence by id (all weights). The validation gate stays weight-tiered to
   avoid false failures: high-weight conflicts are a hard requirement
   (`missing_high_weight_conflict`, escalated from warning to **error** on mixed days);
   medium/low remain advisory.
2. **Precompute-owned matrix rows in Pass 1.** Schema + `_validate_decision_matrix`
   require all 18 rows with exact `signal_layer` labels and a non-empty Recommended
   Action; `sync_matrix_precomputed_rows` then overwrites 7 (Structural Bias, Monte Carlo
   Threshold, Volatility Input, Drift Input, Rally Exhaustion Score, Monte Carlo Edge, ERP
   State and Trend). The prompt instructs the model to emit all 18 rows with correct
   labels and a brief `(engine-filled)` placeholder in the 7 owned rows — preserving
   schema validity while removing wasted prompt budget.

---

## Changes by file

| File | Change |
|------|--------|
| `src/prompts.py` | Precompute-authority `HARD_CONSTRAINTS` (C1/C2); new `PRECOMPUTE_OWNED_MATRIX_ROWS`; `build_state_prompt` drops threshold JSON + `spx_close`, elevates `structural_bias`, uses `(engine-filled)` placeholders (R1–R3, Q3); `build_report_prompt` exposition lock + per-divergence-id coverage (C3, Q4, Q5); new `_round_floats` applied in `_analysis_context_block` (Q6) |
| `src/state_enforcement.py` | `_erp_signal` mapping corrected (C5) |
| `src/validation.py` | New always-on `_validate_state_consistency` (bias present / no contradicting bias / recommended-action echoed); `missing_high_weight_conflict` escalated to error on mixed days; whitespace/slash-tolerant bias matching |
| `src/anthropic_client.py` | Shared `_state_tool()`; Pass 2 sends identical `tools` with `tool_choice: none` (O1); image cache breakpoint removed; `_snapshot` records `image_count`, drops `images_cached` (O6) |
| `tests/test_prompt_builder.py` | Preamble, reduced Pass-1 numeric load, exposition lock + divergence ids, float rounding |
| `tests/test_state_enforcement.py` | ERP expanding→attractive, contracting→caution regressions |
| `tests/test_validation.py` | Contradicting bias, missing bias, high-weight conflict escalation |
| `tests/test_anthropic_caching.py` (new) | Framework cache markup, `_state_tool()` byte-stability, snapshot fields |

---

## Caching reality (O1)

```
Cache prefix order (Anthropic):  tools → system → messages
                                 └──── reusable ────┘   └── per-pass ──┘

Pass 1   tools=[emit_daily_state]   system=[role, framework*]   tool_choice=tool    images + body
Pass 2   tools=[emit_daily_state]   system=[role, framework*]   tool_choice=none    images + body
         └─────────────── identical → cache READ on Pass 2 ───────────┘            └─ fresh both passes ─┘
* cache breakpoint
```

- A differing **tool set** invalidates *all* cache levels — so before this PR, Pass 2
  (no tools) reused nothing. Sending identical `tools` is what unlocks reuse.
- A differing **`tool_choice`** invalidates only the messages layer — so the
  framework + tool schema (tools+system) is still reused on Pass 2, but the **images
  cannot be** (they sit in the messages layer, and Pass 1 forces the tool while Pass 2
  does not). Adding an image breakpoint would only cost a ~1.25× write with no read.
- The real lever for the image tokens (the dominant cost) is **pruning the Pass 2 chart
  subset**, tracked as a follow-up below.

---

## Validation behavior changes

`_validate_state_consistency(report_md, daily_state)` runs whenever a `daily_state` is
provided:

- **error** `contradicting_structural_bias` — the report asserts a different regime than
  the validated `structural_bias`.
- **error** `missing_structural_bias` — the validated bias does not appear in the report
  (matching is whitespace/slash-tolerant, e.g. `Late Bull / Topping` vs `Late Bull/Topping`).
- **warning** `recommended_action_not_echoed` — the validated recommended action is not
  echoed near the Updated Decision Matrix.

`missing_high_weight_conflict` is escalated from warning to **error** on mixed-signal
days (clarification 1).

---

## Acceptance criteria

**Functional**
- ERP matrix signal matches the framework on expanding (`attractive`) and contracting
  (`caution`) days — covered by regression tests.
- A report contradicting the validated `structural_bias` fails `validate_report` with an
  error — covered by regression tests.
- Full `pytest` green (77 tests).

**Efficiency** (measured on one representative live `run`, caching enabled, from
`response.usage`)
- Pass 1: `cache_creation_input_tokens > 0` on the tools+system (framework) prefix;
  functional output unchanged.
- Pass 2: `cache_read_input_tokens` covers the framework + tool schema (~6k tokens).
  Images remain fresh input on both passes by design.
- `output/<date>/request_snapshot.json` shows `framework_cached: true` on both passes.

> The live before/after token capture (O5/acceptance) is the one remaining manual step;
> it requires an API run and does not change code behavior.

---

## Risks and mitigations

- **Cache prefix hit** requires byte-identical tools+system within the 5-min TTL — both
  hold (sequential passes, `_state_tool()` is byte-stable). If caching is disabled,
  behavior is unchanged (graceful no-op).
- **Reduced Pass-1 numeric instruction** could in theory yield a less-tuned
  `monte_carlo`, but enforcement overwrites it entirely, so output fidelity is unaffected.
- **C5 ERP fix** changes the synced `ERP State and Trend` signal on expanding/contracting
  days — the intended correction, flagged for any historical-comparison consumers.
- **Always-on Pass 2 checks** risk false failures if a report legitimately omits the
  literal bias label; mitigated by whitespace/slash normalization and keeping the
  recommended-action check a warning.
- **Escalating `missing_high_weight_conflict` to error** could fail previously-passing
  mixed-day reports; acceptable because the Pass 2 prompt now explicitly requires
  divergence-id coverage.

---

## Out of scope / follow-ups

- **Pass 2 reduced chart subset** — the only real lever for image tokens (caching cannot
  reuse images across the two passes). Tracked as the next PR; Pass 2 already has the
  validated state + conflict checklist and needs charts only for descriptive/reconciliation
  detail.
- Editing the framework markdown (handled via the wrapper preamble).
- Any `DailyState` / schema change.
