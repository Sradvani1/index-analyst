# PR-24: Daily Surgical Fixes — Swing-High Re-Anchoring + Probability Regime

**Status:** Implemented (2026-08-04)
**Cadence:** Daily (unchanged). This PR is the surgical extraction of the two cadence-neutral mechanical defects identified during the PR-23 weekly-framework review; the weekly restructuring itself is parked.
**Builds on:** All of PR-1 … PR-22.

---

## 1. Summary

The PR-23 post-mortem identified two mechanical failures in the daily engine's July 2026 sequence:

1. **Reference staleness (data integrity).** On August 3 the report still listed the July 22 swing high (7,525.94) as the active swing high while SPX closed at a new record 7,600.50. The fib ladder and liquidation thresholds stayed anchored to an obsolete swing even as the report described new-high territory. The engine never re-anchored after a decisive new-high close.
2. **Probability-regime label missing.** Monte Carlo output reduced to a binary "actionable / monitor below threshold" signal, discarding the descriptive shape of the probability landscape (balanced / tilt / extreme asymmetry).

Both fixes are mechanical correctness changes in the daily data path — no cadence, mandate, or prompt-framework restructuring. Everything else in the PR-23 plan (weekly cadence, deployment-readiness hierarchy, posture split, weekly memory, trim_core rules) remains parked.

**Guiding principle: smallest possible change set.** Fix 1 adds one persistent state machine + one re-anchor call site; Fix 2 relabels existing Monte Carlo output. No new analytical machinery.

---

## 2. Background

### 2.1 Reference staleness

`compute_structure()` (`src/structure.py:301`) selects the active swing high as the most recent *confirmed* local maximum. Confirmation requires either a 3% pullback (`pullback_3pct`) or 5 consecutive sessions without a higher high (`five_sessions`). A decisive close above the prior confirmed high does not update the anchor, so:

- fib levels, liquidation zones, and the Monte Carlo downside target remain computed from the stale leg;
- `_nearest_resistance_above()` stops treating the old high as resistance once price is above it (falls through to `next_local_max` / `pct_extension`), but the *anchor itself* never moves;
- the report keeps displaying an obsolete anchor date/price in new-high territory.

The existing `reanchor_downside_for_straddle()` (`src/structure.py:345`) handles the fully-retraced *downside* case only; there is no corresponding upside re-anchor.

### 2.2 Probability-regime label

`run_monte_carlo()` (`src/monte_carlo.py:182`) emits `ThresholdEvaluationRow(actionable=prob_up_adj >= threshold)` per threshold gate (65/70/75%). `state_enforcement._mc_edge_signal()` (`src/state_enforcement.py:29`) renders the edge row as `"actionable"` or `"monitor below threshold"`. The gate is a short-horizon sizing artifact; it discards the shape of the asymmetry (e.g., a 90/10 reading and a 72/28 reading both just "meet" or "miss" the threshold).

---

## 3. Scope

### 3.1 Fix 1 — Unified anchor-authority state machine

**Problem:** a fresh marginal high should not hard-reset geometry (one-day new highs are provisional), but a *confirmed* new high must re-anchor the active leg so the report stops using an obsolete high as resistance.

**Architecture — one resolver, not two anchor-publishing functions.**

The existing local-extrema detector (`_confirm_swing_high` via `pullback_3pct` / `five_sessions`) and the new breakout-detection logic are *observation producers* — they emit evidence about what the market did. Neither may independently publish active anchor geometry. A single persistent `StructureAnchorState` resolves those observations into **at most one anchor transition and one `anchor_version` increment per trading session**. Simultaneous conventional-swing confirmation and breakout confirmation are corroborating observations for one transition, never separate resets.

**Design — persistent `StructureAnchorState` (renamed from the earlier `BreakoutState` since it now resolves all anchor authority, not just breakouts):**

```python
@dataclass(frozen=True)
class StructureAnchorState:
    # --- persisted authoritative anchor identity ---
    active_swing_high_price: float | None = None
    active_swing_high_date: str | None = None
    active_swing_low_price: float | None = None
    active_swing_low_date: str | None = None
    active_swing_low_source: str | None = None      # intermediate_confirmed | prior_active_fallback | unavailable

    # --- breakout-sequence tracking ---
    status: str = "none"                             # none | unconfirmed_new_high | confirmed_new_high | failed_breakout
    candidate_high: float | None = None
    candidate_date: str | None = None
    closes_above_reference: int = 0

    # --- version ---
    anchor_version: int = 1
```

**Reference authority:** When `StructureAnchorState` contains a published active anchor, its `active_swing_high_price` is the reference for all breakout and re-anchor transitions. `compute_structure()` supplies local-extrema observations and candidate geometry only; it is **not** the reference authority. This is what makes "sole publisher" real rather than aspirational — the resolver reads its own prior published anchor, not a potentially-stale legacy output.

**Initialization rule (first run / corrupt store):**
- Run `compute_structure()` to derive initial geometry.
- Seed `StructureAnchorState` with that result's active high, active low, and low-source.
- Treat this as **initialization, not an anchor transition** — `anchor_version` stays at 1, no re-anchor event is emitted.
- Emit a precompute warning: *"Anchor state initialized from current structural computation."*

**Breakout state machine** (for the two-close acceptance path; local-extrema confirmation is resolved directly):

Confirmation rule: **two completed daily closes above the former swing high total.** The trigger close itself counts as close #1, so confirmation arrives on the next qualifying session.

| Prior status | Current-session condition | Transition |
|---|---|---|
| any | close == active swing high | no change (pending — neither advance nor failure) |
| `none` | close > active swing high | → `unconfirmed_new_high`; record candidate_high = session high; `closes_above_reference = 1`; **no geometry reset**; provisional warning |
| `unconfirmed_new_high` | close < active swing high | → `failed_breakout`; retain the previously confirmed anchors; no re-anchor |
| `unconfirmed_new_high` | close > active swing high | `closes_above_reference += 1`; **candidate_high ratchets** to the max of current and prior candidate high. On **second** close (count = 2) → `confirmed_new_high`; re-anchor active leg to the highest candidate high observed in the acceptance window + its intermediate low; `anchor_version += 1` exactly once |
| `failed_breakout` | close > active swing high | → `unconfirmed_new_high` (fresh candidate cycle); record new candidate_high = session high, `closes_above_reference = 1`; prior failure archived |
| `confirmed_new_high` | close > active swing high | ratchet: updates published `active_swing_high_price` to max(published, session high) without incrementing `anchor_version`. Same-leg refinement; fib low unchanged. |
| any | close < active swing high (and not `unconfirmed_new_high`) | no change |

**Conventional-swing path (separate from the breakout window):** if `compute_structure()` detects a new confirmed swing high (via `pullback_3pct` / `five_sessions`) whose price is strictly above the persisted `anchor_state.active_swing_high_price`, the resolver publishes that high immediately as the new active anchor, increments `anchor_version` once, and resets breakout status to `none`. No two-close wait applies — the legacy detector already enforced its own confirmation window. Simultaneous conventional-swing and breakout confirmation on the same bar are one transition. If the new confirmed swing is not strictly above the persisted anchor (i.e., `≤`), it is an intra-leg observation and does not trigger.

**Accepted-high ratchet:** During `unconfirmed_new_high`, on each qualifying close (`close > reference`), `candidate_high` and `candidate_date` update whenever the current session establishes a higher session high. On the second qualifying close, `resolve_structure_anchors()` publishes the highest candidate high observed in the two-close acceptance window. After confirmation, a higher session high ratchets the published `active_swing_high_price` and recomputes high-only liquidation zones without incrementing `anchor_version` — `anchor_version` represents a new structural leg, not each incremental record high. The associated fib low remains unchanged until a new structural leg is resolved. A later session whose high is below the published high never reduces the active high.

**Anchor-authority contract (adopted verbatim):**

> Local-extrema detection and breakout confirmation are observations consumed by one persistent `StructureAnchorState`; neither may independently publish a new active anchor. The persisted authoritative anchor in `StructureAnchorState.active_swing_high_price` is the reference for all breakout and re-anchor transitions. `compute_structure()` supplies local-extrema observations and candidate geometry only; it is not the reference authority. `resolve_structure_anchors()` — the sole resolver — determines the published active geometry. At most one anchor transition and one `anchor_version` increment may occur per trading session. Simultaneous conventional-swing confirmation and breakout confirmation are corroborating observations for one transition, never separate resets.

**New-high anchor and fib-low selection (three-tier explicit fallback):**

Confirming a new high always updates the active high anchor; it is **never** blocked by absence of an intermediate confirmed swing low. Fib-low selection is, in order:

1. the lowest confirmed intermediate swing low between the prior active high and the new high;
2. the prior published `active_swing_low` from `StructureAnchorState`;
3. no fib ladder, with an explicit warning ("Fib ladder unavailable: no confirmed structural low").

In case (3), preserve the new active high and compute high-only liquidation zones; do not manufacture a low from an arbitrary lookback or retain an obsolete fib ladder.

A `source` field tracks which tier was used: `active_swing_low_source: str` = `"intermediate_confirmed"` | `"prior_active_fallback"` | `"unavailable"`. This field is surfaced in the `StructureContext` schema and the report so the LLM and human reader can distinguish a newly-formed leg from a re-anchor that carried the prior low forward.

**Implementation:**

1. `src/structure.py`
   - Add `StructureAnchorState` dataclass.
   - Add `"unconfirmed_new_high"` to the `SwingConfirmation` literal (both `structure.py` and `schemas.py`).
   - Add `_find_intermediate_swing_low()`: lowest confirmed local minimum in the bar range strictly between the persisted old active-high date and the final candidate-high date (reuse `_candidate_local_minima()` + `_confirm_swing_low()`); `None` if none exists. Never scan beyond the candidate bar.
   - Add `resolve_structure_anchors(result, bars, anchor_state, sma50) -> tuple[StructureResult, StructureAnchorState, list[str]]` — the sole publishing resolver. Patterned on the existing `reanchor_downside_for_straddle` shape:
     - `anchor_state.active_swing_high_price` is the authoritative reference for breakout-close comparison (not `result.active_swing_high_price` from the legacy detector);
     - consumes the observation `result` from `compute_structure()` for conventional-swing evidence + bar data;
     - applies the state machine above; local-extrema confirmation (a new swing high emerged through the normal pullback/5-session path) is resolved as a conventional-path transition; the breakout machine determines unconfirmed/confirmed/failed for the two-close path;
     - simultaneous conventional-swing confirmation and breakout confirmation on the same bar = one transition, one `anchor_version` increment, one warning/event record;
     - on confirmation recomputes fib ladder, liquidation zones, MC targets from the new candidate + the resolved fib-low (per the three-tier fallback), then writes the new anchors back into `anchor_state.active_swing_high_*/low_*` and updates `active_swing_low_source`;
      - guardrail: never overwrite historical levels — output carries `prior_swing_high_*`, new active anchors, `anchor_version`, and `active_swing_low_source`.
   - **Atomic-output construction rule:** on a true anchor transition (conventional or breakout confirmation), the resolver constructs a fresh `StructureResult` from the resolved high/low tuple and recomputes fib levels, liquidation zones, and MC targets together — so no caller sees mixed old-leg/new-leg geometry. `replace()`-based field patching is appropriate only for the same-leg high ratchet (update `active_swing_high_price` in place) and is explicitly documented as such.
   - `StructureResult` receives optional tail fields matching the `StructureContext` additions below: `prior_swing_high_price: float | None = None`, `prior_swing_high_date: str | None = None`, `active_swing_low_source: str | None = None`, `anchor_version: int = 1`. The resolver populates these on every call (non-None on transitions; stays `None` on no-ops where the fields have no meaningful value).
   - `compute_structure()` remains unchanged as the observation producer (returns `StructureResult` from local-extrema detection); it does **not** call the resolver — the resolver is a separate, subsequent call from `run_precompute`.
   - **Result/state synchronization invariant:** after every resolver call, the returned `StructureResult` and `StructureAnchorState` agree on active swing high/low price, active swing low source, and `anchor_version`. `_structure_to_schema()` maps only the final `StructureResult`, never reads `StructureAnchorState` directly.
2. `src/schemas.py`
    - `StructureContext` (line 137) tail-append optional fields: `prior_swing_high_price: float | None = None`, `prior_swing_high_date: str | None = None`, `active_swing_low_source: str | None = None`, `anchor_version: int = 1`.
   - Optional-with-default keeps previously stored `analysis_context.json` / state files parseable.
3. `src/precompute.py` — `run_precompute()` (line 58):
   - Load persisted `StructureAnchorState` from `data/master/anchor_state.json` before structure detection.
   - **Missing/corrupt file → initialization:** run `compute_structure()`, seed `StructureAnchorState` with its active high, active low, and low-source; `anchor_version` stays 1; emit warning *"Anchor state initialized from current structural computation"* (not an anchor-transition event).
    - **Normal path:** call `compute_structure()` to produce the observation `result`; then call `resolve_structure_anchors(result, bars, anchor_state, sma50)` to get the authoritative `(final_result, new_anchor_state, warnings)`.
   - Immediately after, apply `reanchor_downside_for_straddle()` so the straddle guard sees the freshest geometry.
   - Append re-anchor warnings to `market.precompute_warnings` and the log; persist `new_anchor_state` back (atomic write via `files.write_json`).
4. `src/config.py` — add `anchor_state_path_raw: str = "data/master/anchor_state.json"` (+ `anchor_state_path` property), mirroring `eps_history_path`.
5. `src/prompts.py` — `_investor_fact_snippets()`: surface the active anchor date/price, prior swing high, `active_swing_low_source`, and a provisional-breakout flag when present.

### 3.2 Fix 2 — Probability-regime label

The regime label **supplements** the existing actionable gate, not replaces it. The framework explicitly requires every run to report whether the adjusted probability clears the active structural-bias threshold. The two outputs serve different purposes:

- **Regime label** (engine-derived): describes the shape of the probability distribution — balanced, upside tilt, downside tilt, or extreme directional asymmetry. Threshold-independent.
- **`actionable` bool** (unchanged): threshold-gated mechanical eligibility — whether adjusted upside-first probability passes the active Structural Bias threshold. Still feeds effective-threshold mechanics.

1. `src/monte_carlo.py` — new `_probability_regime(prob_up_adj, prob_down_adj) -> str`, **extreme checked first** with direction:

   ```python
   if max(prob_up_adj, prob_down_adj) >= 0.85:
       return "extreme_upside_asymmetry" if prob_up_adj >= prob_down_adj else "extreme_downside_asymmetry"
   if prob_up_adj >= 0.70:
       return "upside_tilt"
   if prob_down_adj >= 0.70:
       return "downside_tilt"
   return "balanced"
   ```

   Populate on each `ThresholdEvaluationRow` (threshold-independent label) and on the returned context.
2. `src/schemas.py`
   - `ThresholdEvaluationRow` (line 160): add `probability_regime: str = "balanced"`.
   - `MonteCarloContext` (line 167): add `probability_regime: str = "balanced"` (source of truth, set once by `run_monte_carlo`).
   - `MonteCarloDetail` (line 285): add `probability_regime: str = "balanced"`.
   - `actionable` bool on `ThresholdEvaluationRow` stays (feeds effective-threshold gate); defaults keep stored artifacts parseable.
 3. `src/state_enforcement.py`
    - `_mc_edge_signal()` (line 29) → return the regime label.
    - `apply_precomputed_fields()` (line 118): set `probability_regime` on the enforced `MonteCarloDetail` from `analysis_context.monte_carlo.probability_regime` (the context-level source of truth). Each threshold row holds a matching copy for display in the matrix but is not the enforcement source.
   - `sync_matrix_precomputed_rows()` (line 69):
     - **Monte Carlo Threshold** row: reading = effective threshold %, signal = `"passes"` or `"fails"` based on `meets_threshold` (the actionable gate stays visible).
     - **Monte Carlo Edge** row: reading = adjusted probability %, signal = regime label.
4. `src/report_assembly.py` (line 102) — display both: the regime label and whether the threshold was met.
5. `src/prepare_run.py` (lines 166–188) — summary line prints the regime label and the 65% threshold result.
6. `src/validation.py` (line 224) — `_matrix_uniformly_directional()` bullish-token list: add `"upside"` and `"extreme"` so the heuristic scores when the edge row carries a regime label.

**Not changed:** `THRESHOLDS`, `select_mu`, `select_sigma`, exhaustion logic, the simulation, `actionable` bool (feeds threshold gate, now also displayed in the Threshold row's signal), `EmitDailyStateInput` (regime is engine-governed, not LLM-authored).

### 3.3 Explicitly out of scope (parked with PR-23)

Weekly cadence / `run-weekly` / `run-event` / `run` removal, deployment-readiness hierarchy, strategic/tactical posture split, weekly memory store + event ledger + legacy archive, `trim_core` rule, `DailyState` rename, framework version resolver. The daily framework document keeps its daily workflow; only the reference-reset paragraph (below) is added.

---

## 4. Framework documentation (two edits)

**Edit 1 — Reference-level reset.** Add to `framework/SPX-Daily-Analysis-Framework.md` (technical structure section):

> **Reference-level reset:** On a confirmed close above the active swing high, the engine re-anchors swing references via `resolve_structure_anchors`. A single new-high session is provisional until confirmed (two qualifying closes total). The report must display the active swing anchor date and price, and must not use a prior high as resistance once price has accepted above it. A failed breakout (close back below the former high before confirmation) retains the previously confirmed anchors.

**Edit 2 — Probability-regime label.** In the Monte Carlo / Step 5 section:

> **Keep:** "Whether the setup is actionable" (the adjusted probability must clear the Structural Bias threshold).

> **Add:** "Probability-regime label, describing the adjusted upside/downside asymmetry independently of the regime-specific action threshold."

The Decision Matrix treatment:

- **Monte Carlo Threshold:** retains the effective threshold and whether it passes.
- **Monte Carlo Edge:** shows probability regime in the signal field and adjusted probability in the reading.
- **Step 5 narrative:** report both, e.g. *"Upside tilt (72% adjusted upside probability); actionable at the active 70% Late Bull threshold."*

---

## 5. Verification

- **New unit tests.**
  - `tests/test_structure.py`:
    - no-op below active swing high (state and anchors unchanged);
    - first close above active swing high → `unconfirmed_new_high`, candidate recorded, `closes_above_reference = 1`, **no** fib/liquidation reset;
    - second qualifying close → `confirmed_new_high`, active leg re-anchored to candidate + intermediate low, `anchor_version` increments from 1 → 2 (two closes total);
    - close below active swing high before confirmation → `failed_breakout`, prior anchors retained, no re-anchor;
    - `failed_breakout` + later close above active swing high → `unconfirmed_new_high` (fresh candidate cycle, `closes_above_reference = 1`);
    - candidate-high ratchet: Day 1 session high = 7,590 (candidate recorded); Day 2 session high = 7,620, close qualifies → confirmation publishes 7,620 (the highest candidate in the window), not 7,590;
    - post-confirmation ratchet: after confirmation publishes 7,620, a Day 3 session high of 7,650 updates `active_swing_high_price` to 7,650, preserves the same fib low and `active_swing_low_source`, and does **not** increment `anchor_version`;
    - no downgrade: after a published active high of 7,650, a subsequent session high of 7,620 does **not** reduce the active high;
    - exact-reference retest: close == active swing high during `unconfirmed_new_high` → status stays `unconfirmed_new_high`, candidate and count unchanged (pending, no advance, no failure);
    - false intraday breakout: session high exceeds the candidate but close finishes below reference → `failed_breakout`, candidate not updated;
    - no future fib leakage: a lower confirmed local minimum after the final candidate-high bar date is not selected by `_find_intermediate_swing_low` (the scan ends at the candidate bar);
    - result-to-schema propagation: resolved `active_swing_low_source` and `anchor_version` travel from `final_result` through `_structure_to_schema()` into `StructureContext`, without separately injecting state fields from `StructureAnchorState`;
    - simultaneous conventional-swing confirmation and breakout confirmation on the same bar → one published geometry, one warning/event record, one `anchor_version` increment;
    - no further `anchor_version` increments on subsequent sessions within a confirmed leg;
    - `compute_structure()` unchanged (returns observations); `resolve_structure_anchors` is the sole publisher.
    - persistence over legacy staleness: after the resolver publishes a breakout at 7,600, provide a later `compute_structure()` observation whose legacy active high is still 7,526; confirm the resolver uses 7,600 (its own persisted anchor) as reference and does not start a breakout based on the stale 7,526.
    - state initialization: with no `anchor_state.json`, initialize from the computed structure; verify active geometry is persisted, `anchor_version == 1`, and no re-anchor event/version increment occurs.
  - `tests/test_structure.py` — fib-low fallback:
    - intermediate swing low found → `active_swing_low_source = "intermediate_confirmed"`, standard fib ladder;
    - no intermediate low, prior low available → `active_swing_low_source = "prior_active_fallback"`, fib ladder uses the prior published low;
    - no intermediate low, no prior low → `active_swing_low_source = "unavailable"`, fib ladder suppressed with warning, high-only liquidation zones preserved.
  - `tests/test_monte_carlo.py`: `_probability_regime` ordering — 90/10 → `extreme_upside_asymmetry`; 10/90 → `extreme_downside_asymmetry`; 72/28 → `upside_tilt`; 30/70 → `downside_tilt`; 55/45 → `balanced`.
  - `tests/test_state_enforcement.py`: `Monte Carlo Edge` row carries the regime label; `Monte Carlo Threshold` row shows pass/fail; `MonteCarloDetail.probability_regime` enforced from `analysis_context.monte_carlo.probability_regime` (context-level source of truth).
- **Fixture updates**: `tests/sample_analysis_context.py` and any fixtures constructing `ThresholdEvaluationRow` / `MonteCarloDetail` / `StructureContext` (new fields defaulted, so most pass unchanged).
- **Full suite**: `pytest` green.
- **Backfill smoke**: re-run `2026-07-29` → `2026-08-03` (data already prepared) and confirm: re-anchor state transitions appear in `run_log.json` warnings; August 3 output shows the new anchor + `anchor_version`; no regression in validation PASS.

---

## 6. Sequencing

1. `src/structure.py` (StructureAnchorState, `_find_intermediate_swing_low`, `resolve_structure_anchors`, `compute_structure` stays as observation-producer) + `src/schemas.py` (fields, literals, `active_swing_low_source`).
2. Persistence: `src/config.py` (anchor_state_path) + `src/precompute.py` wiring.
3. Fix 2: `src/monte_carlo.py` + `src/schemas.py` fields.
4. Consumers: `state_enforcement.py`, `report_assembly.py`, `prepare_run.py`, `validation.py`, `prompts.py`.
5. Tests + fixture updates; full `pytest`; backfill smoke.
6. Docs: framework paragraphs (§4), this PR record, PR-23 status already marked Parked.

---

## 7. Edge cases and contracts

- **Simultaneous confirmation:** if conventional swing detection and the breakout machine both fire on the same session, they are one anchor transition — one `anchor_version` increment, one event record, one published geometry. The resolver treats them as corroborating evidence for the same structural event.
- **First run / corrupt store:** missing or unparseable `anchor_state.json` → initialization path: run `compute_structure()`, seed `StructureAnchorState` with its active high/low and low-source, `anchor_version = 1`, warning *"Anchor state initialized from current structural computation."* Never raises; never emits a re-anchor event.
- **Persistence over legacy staleness:** after a confirmed breakout publishes a new high (e.g. 7,600), the legacy `compute_structure()` may still return the old high (e.g. 7,526) on subsequent runs because no pullback/5-session confirmation has occurred. The resolver uses its own persisted `active_swing_high_price` (7,600) as reference — the stale legacy output is only one observation input among others.
- **Weekends/holidays:** the machine transitions on trading sessions present in the bar window; gaps are irrelevant.
- **Schema compatibility:** all new schema fields are optional-with-default; previously stored contexts and states parse unchanged. `run_log.json` gains the re-anchor warning lines — additive only.
- **Straddle guard ordering:** `resolve_structure_anchors` runs first, then `reanchor_downside_for_straddle` — the straddle guard always sees the freshest geometry; the reverse order is never taken.
- **Validation heuristic:** the bullish-token additions (`"upside"`, `"extreme"`) keep `_matrix_uniformly_directional` scoring after the edge row carries a regime label instead of `"actionable"`.
- **Fib-ladder suppression:** when `active_swing_low_source = "unavailable"`, the fib ladder is replaced with text "Fib ladder unavailable: no confirmed structural low" — not blank fields that could be misread as a data failure. Liquidation zones are computed from the new swing high alone.
