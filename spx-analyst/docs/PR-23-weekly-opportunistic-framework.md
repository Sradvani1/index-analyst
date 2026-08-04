# PR-23: Weekly-First Opportunistic Allocation Framework

**Status:** Parked — daily cadence retained; weekly restructuring shelved. The two cadence-neutral defects this plan identified (swing-high reference staleness, probability-regime labeling) are implemented under [PR-24](PR-24-daily-reanchor-probability-regime.md).
**Framework version:** `daily-2026-06` → `weekly-2026-08` (proposed)
**Builds on:** All of PR-1 … PR-22. This is a **restructuring of scope and mandate**, not an incremental feature. It repurposes the existing two-pass engine and chart infrastructure from a daily tactical-trading system into a quiet, weekly opportunistic-allocation system for long-term capital.

---

## 1. Summary

The engine correctly identified risk through the July 2026 distribution-to-breakdown sequence, but it then **missed the July 30 failed-breakdown reversal** and stayed structurally bearish while SPX rallied to new all-time highs by August 3. A post-mortem — including a "what would Munger buy?" framing exercise — concluded that the strategic call (defensive, no new capital at thin-ERP highs) was **correct for a long-term, opportunistic investor**, and the real defect was narrower: the framework had only one decision axis. It could not say *"the breakdown has failed and the trend is repairing"* without implying *"deploy capital."*

This PR restructures the framework around that distinction:

- **Strategic posture** (governs core capital) and **tactical state** (describes market structure) become independent, first-class outputs.
- **Deployment readiness** replaces the "buy signal" mindset. New core capital is reserved for genuine valuation-plus-drawdown opportunity.
- The cadence moves from **daily to weekly-first**, with event-driven interim runs and a minimal daily data/alert layer. The generic `run` command is **removed**; only `run-weekly` and validated `run-event` can produce an LLM report.
- Trading mechanics (optional starters, 2-of-4 sizing, stops, short-horizon authorization) are **removed**, not added.
- Mechanical correctness fixes are **kept**: swing-high re-anchoring on new highs (with a persistent confirmation state machine), probability-regime labeling in the Monte Carlo output.
- Memory becomes **weekly-first**: a canonical weekly store, an immutable event ledger, and a frozen legacy daily archive excluded from active context.

**Guiding principle: the smallest possible change set.** The engine already computes the raw materials (ERP, structure, Monte Carlo, breadth charts). This PR mostly *re-labels* what the model reports and *de-scopes* what it is allowed to recommend — it does not build new analytical machinery.

---

## 2. Background: the July 2026 sequence

### 2.1 What the framework did

From mid-July, the daily reports tracked a **Late Bull / Topping** structure:

- Around July 21 SPX briefly reclaimed the 20-/50-day and pushed back toward the repeated 7,578 resistance, but breadth sat near cycle lows, ERP remained at the valuation ceiling, and the probability edge was a coin flip — the reclaim was correctly judged not actionable.
- On July 23 the market lost the retracement ladder and the 20-/50-day cluster, converting support into overhead resistance — the structural transition from *range-bound topping* to *short-term breakdown*.
- July 29 SPX closed at 7,316.15 near its lows, below the key averages, with VIX above 20 and momentum/money-flow weakening together. A defensive read that session was reasonable.
- The model showed roughly 22% up-first vs 78% down-first; zero of five buy conditions met; four of five defense/trim conditions met.

### 2.2 The July 30 pivot the system missed

July 30 was the pivot. SPX defended the 7,300 caution shelf, reclaimed the 20-day, closed in the top third of its range, RSI and money flow turned up, VIX fell from 20.66 to 17.09 (below its 50-day average), credit stayed contained, and the probability model flipped to ~62.5% up-first.

The report scored this as only **2 of 4** re-entry conditions and, despite the framework stating that two conditions mean "partial confirmation and reduced aggression," treated it as **no action**. The regime label stayed *Late Bull / Topping* even after the reclaim of the 50-day/fib cluster (July 31) and the new all-time high at 7,600 (August 3) — driven by two slow-moving structural variables (thin ERP, cycle-low breadth) that were treated as absolute vetoes.

### 2.3 The two mechanical failures

1. **Reference staleness (data integrity).** The August 3 report still listed the July 22 swing high of 7,525.94 as the active swing high while SPX closed at a new record 7,600.50. The fib ladder and liquidation thresholds stayed anchored to an obsolete swing even as the report described new-high territory. The old high had become support, not resistance; the engine did not re-anchor.
2. **Single decision axis (mandate defect).** The framework conflated *"the breakdown has failed and the trend is repairing"* with *"deploy capital."* With only one recommended-action output, the model collapsed the repair back into the strategic no-add message instead of explicitly recognizing the reversal.

### 2.4 The Munger question and the mandate

A working session tested the proposed fixes against *"would Charlie Munger buy this market?"* The conclusion reframed the entire problem:

- Munger does not time the macro. He owns understood, high-quality assets and waits for clear price-to-value mismatches. He would distinguish **staying invested** (hold core) from **putting incremental capital to work at an extended, thin-ERP high** (do not).
- Under that lens, the July 30 decision was **not a failed investment decision**. It was a correctly recognized technical repair that did not meet the bar for new long-term capital: drawdown was shallow, ERP was still in the ceiling band, and breadth had not confirmed.
- The actual defect is that the system could not **label** the repair independently of its **allocational** verdict. It should have been able to state: *"Strategic: hold / no new core capital. Tactical: repair underway; the breakdown is invalidated."*

**Confirmed mandate (drives every decision in this PR):**

> Remain invested through normal drawdowns. Deploy incremental cash only when expected return and downside protection become unusually compelling. Do not chase repairs, breakouts, or short-term reversals.

---

## 3. Restructuring scope

Tiers 1–2 are kept, Tier 3 is removed, Tier 4 is the cadence pivot.

### 3.1 Tier 1 — Keep (data integrity; no trading opinion)

| Change | Decision | Why |
|--------|----------|-----|
| Swing/fib/liquidation re-anchoring on a new high | **Keep** | Mechanical correctness. After SPX accepted above 7,525.94, that level became support, and the report must not still use it as resistance. |
| Monte Carlo `probability_regime` label | **Keep** | Replaces the binary "actionable / monitor" signal with a descriptive label (balanced / upside_tilt / downside_tilt / extreme_upside_asymmetry / extreme_downside_asymmetry — direction is included inside the extreme case). Contextual only — it does not authorize deployment. |

### 3.2 Tier 2 — Keep (structural accuracy; no trading permission)

| change | Decision | Why |
|--------|----------|-----|
| Two-tier posture model (strategic + tactical) | **Keep** | Resolves the July defect directly: a market can be technically repairing while strategic deployment remains unavailable. |
| `PostureState` schema object | **Keep, stripped** | Structured, enforceable contract. Includes strategic posture, tactical state, deployment readiness, structured deployment zones, and invalidation conditions. **Excludes** trade-authorization/sizing fields (see Tier 3). |
| ERP 0.0%–0.5% band language | **Keep** | Reframe from "no aggressive adds" (a trading veto) to "strategic adds on hold" (an allocation constraint). |
| Breadth-lag protocol | **Keep, descriptive** | Weak breadth explains lower conviction and restricts new allocation; it does not trigger a trade and is not a veto on recognizing a repair. |


### 3.3 Tier 3 — Remove (trading mechanics)

| change | Decision | Why |
|--------|----------|-----|
| Failed-Breakdown Reversal Setup as an entry trigger | **Remove** | Tactical entry mechanism; invites activity where the mandate wants patience. |
| 2-of-4 / 3-of-4 / 4-of-4 execution sizing | **Remove** | Entry mechanics for a tactical sleeve, not a value-oriented allocation system. |
| Optional 1/3 tactical starter | **Remove** | Same reason. |
| Monte Carlo 60–69% → "reduced tactical risk" authorization | **Remove** | A short-horizon first-hit probability must not decide whether long-term cash goes to work. |
| Daily stop / invalidation levels around reversal lows or the 20-day | **Remove** | Long-term capital is not governed by one- or two-day price moves. |

### 3.4 Tier 4 — Pivot: weekly-first cadence

| change | Decision |
|--------|----------|
| Framework document: daily → weekly workflow | **Yes** |
| Remove intraday close position, daily SMA breaks, next-session targeting | **Yes** — daily noise for this mandate. |
| Add deployment-readiness hierarchy, cash-deployment zones, invalidation conditions | **Yes** — replaces the "Recommended Action for next session" as the primary output. |
| Keep Monte Carlo as strategic context only | **Yes** — see §5.2 / §4.5. |
| Daily data collection stays as a data/alert layer | **Yes** — `prepare`/`import-run` continue; LLM reports are weekly/event only. |
| New `run-weekly` entrypoint | **Yes** — scheduled Friday decision run. |
| New `run-event --trigger` entrypoint | **Yes** — validated interim exception review. |
| Legacy generic `run` | **Removed entirely** from the CLI — LLM analysis is inaccessible without a cadence contract. |

### 3.5 The three governing edits (from design review)

1. **4-of-4 does not make strategic eligible.** A perfect technical reversal after a shallow decline can still be an unattractive place for long-term capital. `4-of-4` = *tactical repair fully confirmed; it may improve deployment readiness, but strategic allocation always remains independently governed by valuation, ERP trend, breadth, credit, drawdown depth, and long-term trend.*
2. **Drawdown depth is a mandatory readiness input.** Readiness is not merely a technical-repair ladder. Shallow corrections with thin ERP cannot qualify as `partial_opportunity` regardless of technical repair quality. The 3% "caution zone" remains an alert, not an opportunity.
3. **`trim_core` is rare and portfolio-level.** Trimming because of an upper-band walk, short-term MFI, or routine close behavior is exactly the behavior being removed. `trim_core` requires strict `ERP-and-extension` or `breadth-AND-credit` deterioration from 4-week baselines, or the portfolio above intended risk. Otherwise `hold_core` is correct even when readiness is `not_ready`. "No add" and "sell what you own" are different decisions.

---

## 4. Target architecture

### 4.1 Decision hierarchy

| layer | inputs | valid outputs |
|-------|--------|---------------|
| **Strategic posture** (core capital) | ERP level/trend, breadth trend, credit trend, valuation, long-term trend, drawdown depth | `add_core` / `hold_core` / `trim_core` / `defensive` |
| **Tactical state** (structure) | support/reclaim, weekly trend (10-/20-week, 50-/200-day lines), close quality, RSI/MFI turn, VIX direction, credit stability | `repairing` / `intact` / `extended` / `correcting` / `breaking_down` |
| **Deployment readiness** (new capital) | drawdown depth, ERP band, breadth stabilization, credit containment, weekly base/reclaim | `not_ready` / `watch` / `partial_opportunity` / `compelling_opportunity` |
| Execution authorization | predefined account/risk rules outside the engine | **Out of scope** — the engine reports posture and zones; it does not issue trade orders |

### 4.2 Strategic posture definitions

| posture | meaning |
|---------|---------|
| `add_core` | incremental long-term capital may be deployed (rare; requires compelling valuation + structure). |
| `hold_core` | maintain existing exposure; no new capital; no trims. **The default.** |
| `trim_core` | reduce core exposure. **Rare.** Requires at least one of: ERP materially deteriorated **and** price materially extended on a weekly basis; breadth **and** credit both materially deteriorated from their 4-week baselines; or the portfolio above its intended risk allocation. Never driven by short-term overboughts or by a single weak internal — that scenario is `hold_core` with lower readiness, not `trim_core`. |
| `defensive` | build cash; core at minimum; long-term trend/structure concerns dominate. |

### 4.3 Deployment readiness hierarchy (with drawdown depth)

Starting hypotheses to test — **not** permanent mechanical triggers:

| readiness | minimum context | meaning |
|-----------|-----------------|--------------------------|
| `not_ready` | new highs or shallow pullback (<5% from cycle high close), ERP below 0.5%, or price materially extended | hold core; no new capital |
| `watch` | roughly 5%–10% correction, or valuation improving | candidate zones; retain cash |
| `partial_opportunity` | meaningful drawdown **plus** ERP at/above 0.5%, credit contained, breadth no longer worsening | consider a measured core tranche |
| `compelling_opportunity` | deep drawdown/washout **plus** ERP at/above 1.0% or clearly improving, credit stabilization, broad fear, and an established weekly base/reclaim | scale planned cash into tranches |

### 4.4 Cadence and event triggers

**Scheduled:** one report after Friday's close. "Hold and wait" is the normal, correct output; the system is quiet by default and loud only when opportunity or risk materially changes.

**Event-driven runs** (same report engine, same LLM mandate, run only through a validated trigger):

| event | immediate behavior |
|-------|--------------------|
| 5% drawdown from cycle high | alert; refresh drawdown + candidate zones |
| 10% / 15% drawdown | alert; refresh valuation/credit/breadth; produce full report |
| VIX > 25 | alert; monitor persistence; report only alongside 5%+ drawdown or credit/breadth stress |
| ERP band crossing | alert + full report at the 0.5% or 1.0% thresholds; alert only at the 2.0% band |
| completed-Friday close through/reclaim of 50- or 200-day | trigger full report |
| major credit or EPS/yield shift | trigger full report |
| breadth reversal after washout | trigger full report |

**The event run is provisional for week-scale triggers.** A non-Friday reclaim of the 50- or 200-day cannot confirm a *week* on the daily price bar; when `week_sma_reclaim` is requested outside a scheduled run it is labeled **provisional — awaiting Friday confirmation** and cannot write weekly memory.

This separation removes the generic daily run and prevents a recreated daily system through event-trigger overuse. The new system is **intentionally difficult to activate**.

### 4.5 Monte Carlo placement

Keep the simulation, but move it **out of the decision gate**. It answers:

- Is downside asymmetry rising?
- Is the market's path unusually compressed or volatile?
- Is waiting likely to have a high or low opportunity cost?

It must **not** determine `add_core` or `trim_core`. A representative weekly output: *"Probability regime: Balanced / short-horizon upside tilt. Strategic relevance: low — it does not improve deployment readiness because ERP is thin and breadth remains unsettled."*

---

## 5. Implementation plan (per file)

**Scope discipline:** This is the *minimal* change set. Each listed change is required to produce the Tier 1/2 outcomes and the weekly-first pivot; nothing is additive. Where a change is optional or deferrable, it is marked **(defer)**.

### 5.0 `Step 0 — Memory migration` (before any schema change)

1. **Archive legacy daily artifacts.** Move `memory/daily_reports/`, `memory/daily_states/`, `memory/rolling/` under `memory/legacy_daily/…`. No copying, no rewriting — read-only historical artifacts. The web viewer and chat may still read `legacy_daily/` on demand, but analysis prompts never receive it.
2. **Create empty weekly stores.** `memory/weekly/` (canonical weekly entries) and `memory/events/` (immutable event ledger). Add the matching `Settings` path properties (`weekly_dir`, `events_dir`, `breakout_state_path`).
3. **Seed the first canonical baseline** from the 2026-08-03 run (`report_type: scheduled_weekly`), built **only** from durable data: cycle high + drawdown depth, ERP and trend, credit/breadth state, long-term bias, extension vs 200d, risk regime, strategic/tactical postures, deployment readiness, deployment zones. Explicitly exclude: intraday behavior, next-session calls, short-horizon targets, stale swing references, old trim instructions.
4. **Exclude legacy narrative summaries from active context.** The weekly loader (§5.10) never injects `legacy_daily` text or `recent_summary.md` into a prompt.

### 5.1 `src/schemas.py`

1. **`SwingConfirmation`** (line 39): add `"unconfirmed_new_high"` to the literal.
2. **New `DeploymentZone` model** (after `Divergence`):
   ```python
   class DeploymentZone(BaseModel):
       model_config = ConfigDict(extra="forbid")
       label: Literal["watch", "partial", "compelling"]
       low: float
       high: float
       rationale: list[str]
       required_confirmations: list[str] = []
   ```
   `required_confirmations` must be **long-horizon** conditions ("ERP at least 0.5%", "weekly breadth stabilization", "credit not widening") — not daily RSI or reversal-candle criteria.
3. **New posture literals + `PostureState`** (after `DeploymentZone`):
   ```python
   StrategicPosture = Literal["add_core", "hold_core", "trim_core", "defensive"]
   TacticalPosture = Literal["repairing", "intact", "extended", "correcting", "breaking_down"]
   DeploymentReadiness = Literal["not_ready", "watch", "partial_opportunity", "compelling_opportunity"]

   class PostureState(BaseModel):
       model_config = ConfigDict(extra="forbid")
       strategic_posture: StrategicPosture
       tactical_posture: TacticalPosture
       deployment_readiness: DeploymentReadiness
       deployment_zones: list[DeploymentZone]
       invalidation_conditions: list[str]
   ```
   **No** trade-authorization, risk-cap, or sizing fields — those are Tier 3 removals.
4. **New `BreakoutState`** (config-driven store):
   ```python
   class BreakoutState(BaseModel):
       candidate_high: float | None = None
       candidate_date: date | None = None
       reference_high: float | None = None
       status: Literal["none", "unconfirmed_new_high", "confirmed_new_high", "failed_breakout"] = "none"
       closes_above_reference: int = 0
       anchor_version: int = 1
   ```
5. **New `WeeklyMemoryEntry`** (the persistent weekly record):
   ```python
   class WeeklyMemoryEntry(BaseModel):
       as_of_date: date
       report_type: Literal["scheduled_weekly", "event_review"]
       strategic_posture: StrategicPosture
       tactical_posture: TacticalPosture
       deployment_readiness: DeploymentReadiness
       spx_close: float
       cycle_high: float
       drawdown_from_cycle_high_pct: float
       extension_vs_200d_pct: float
       erp: float | None
       erp_trend: str
       breadth_state: str
       credit_state: str
       probability_regime: str
       deployment_zones: list[DeploymentZone]
       upgrade_conditions: list[str]
       downgrade_conditions: list[str]
       changed_since_prior_week: list[str]
       supersedes_weekly_entry_id: str | None = None
       report_path: str
   ```
   `supersedes_weekly_entry_id` is set only on versioned interim `event_review` records (§5.10).
6. **`structure` migration to `schemas.py`**: `breakout_*` fields on `StructureContext` (from `BreakoutState`), plus `probability_regime` on `ThresholdEvaluationRow` and `MonteCarloDetail`.
7. **`DailyState`** (line 406): add required `posture: PostureState`.
8. **`EmitDailyStateInput`** (line 307): add `posture_strategic_posture / posture_tactical_posture / posture_deployment_readiness / posture_deployment_zones / posture_invalidation_conditions` and `mc_probability_regime`.
9. **`flat_to_nested()`** (line 366): route `posture_*` prefixed fields into a nested `posture` dict (same pattern as `signals_`/`mc_`).

### 5.2 `src/monte_carlo.py`

1. **New `_probability_regime()`** (after `select_sigma`). Extreme-asymmetry is checked **first**, with a directional label, so a 90/10 reading reads as extreme, not as a simple tilt:
   ```python
   def _probability_regime(prob_up_adj: float, prob_down_adj: float) -> str:
       if max(prob_up_adj, prob_down_adj) >= 0.85:
           return "extreme_upside_asymmetry" if prob_up_adj >= prob_down_adj else "extreme_downside_asymmetry"
       if prob_up_adj >= 0.70:
           return "upside_tilt"
       if prob_down_adj >= 0.70:
           return "downside_tilt"
       return "balanced"
   ```
2. **`run_monte_carlo()`** (line 182): compute once from adjusted probabilities and populate `probability_regime` on each `ThresholdEvaluationRow` (threshold-independent label) and on the returned `MonteCarloDetail`.

**No change** to `THRESHOLDS`, `select_mu`, `select_sigma`, exhaustion logic, or the simulation.

### 5.3 `src/structure.py`

1. **`SwingConfirmation`** (line 39): add `"unconfirmed_new_high"`.
2. **`StructureResult`** (line 78): add optional `prior_swing_high_price`, `prior_swing_high_date`, `reclaimed_breakout_support`, and `anchor_version: int = 1`.
3. **New `_find_intermediate_swing_low()`**: the lowest confirmed local minimum between the prior swing-high bar and the end of the window (reuse `_candidate_local_minima()` + `_confirm_swing_low()`); `None` if none exists.
4. **New `reanchor_on_new_high()`** (patterned on `reanchor_downside_for_straddle`, line 345):
   - Takes the current `StructureResult`, the bar sequence, and the previous `BreakoutState`.
   - **Owner:** called exactly once inside `compute_structure()`; it is core swing geometry. `run_precompute()` **consumes the result and persists the new `BreakoutState`** — it never calls this function itself.
   - On a close above the old reference high: record candidate + reference, mark **unconfirmed_new_high**, and flag the fib/liquidation map provisional **without** re-anchoring geometry from a one-day marginal high.
   - On each qualifying close ≥ reference: increment `closes_above_reference`; at the second close (or a retest that holds above reference) flip to **confirmed_new_high**, re-anchor the active leg once to the new candidate and its intermediate low, and increment `anchor_version` exactly once.
   - If price closes back below the reference before confirmation: mark **failed_breakout**; retain the previously confirmed anchors and do not re-anchor.
   - Once confirmed, do not increment `anchor_version` again unless a genuinely new structural leg begins.
   - Returns `(StructureResult, BreakoutState, warnings)`. **Guardrail:** never overwrite historical levels in place — keep `prior_swing_high_*`, `reclaimed_breakout_support`, new active anchors, and `anchor_version` in the output so the model sees both the new geometry and the old breakout level now acting as support.
5. **`compute_structure()`** (line 301): accept optional `breakout_state`, run `reanchor_on_new_high()` as the final step, and return both the result and the (possibly transitioned) breakout state.

### 5.4 `src/precompute.py`

1. **`run_precompute()`** (line 58):
   - Load persisted `BreakoutState` from `data/master/breakout_state.json` (mirror the `eps_history.json` pattern) before structure detection.
   - Call `compute_structure()` with that breakout state (which internally applies the re-anchor machine). **Do not** call `reanchor_on_new_high()` at this layer.
   - Immediately after structure resolution, apply `reanchor_downside_for_straddle()` so the straddle guard sees the freshest geometry.
   - Append both sets of warnings to `market.precompute_warnings` and the log; persist the returned `BreakoutState` back to `breakout_state.json` (atomic write).
2. **`_structure_to_schema()`** (line 35): map the new `StructureResult` fields (including `anchor_version` and the re-anchor provenance) into `StructureContext`.

### 5.5 `src/state_enforcement.py`

1. **`_mc_edge_signal()`** (line 29): return the `probability_regime` label instead of `"actionable" / "monitor below threshold"`.
2. **`sync_matrix_precomputed_rows()`** (line 45): update the `Monte Carlo Edge` row to carry the regime label.
3. **New `sync_posture_matrix_rows()`**: deterministically fill the `Strategic Posture`, `Tactical State`, and `Deployment Readiness` decision-matrix rows **from `state.posture`** (reading + signal rendered from the enum values). The LLM cannot freely write these rows.
4. **Posture is LLM-owned.** `apply_precomputed_fields()` (line 94) **must not overwrite `state.posture`** — it validates schema only. Precompute ownership extends only to ERP, drawdown, breadth, credit, and `probability_regime`.

### 5.6 Framework documents

- **Keep `framework/SPX-Daily-Analysis-Framework.md` immutable on disk.** It is the reproducible source for `legacy_daily` reports that store `framework_version = "daily-2026-06"`. Reproduce mode: the version resolver serves the archived doc when a stored version matches.
- **New `framework/SPX-Weekly-Analysis-Framework.md`** — the weekly rulebook. The default `SPX_FRAMEWORK_PATH` flips to this file; the existing daily path remains valid and explicit via `SPX_FRAMEWORK_PATH`.
- Every `DailyState` already stores `framework_version`; extend `run_log`/`DailyState` to store the **literal framework path used**, so reproducibility never depends on current workspace state.

**Keep (with edits):**
- Purpose — reframed for weekly cadence and long-term allocation.
- Required Regime Classification — unchanged (regime is a weekly-scale concept).
- Fundamental Valuation Framework — unchanged; refreshed weekly.
- Technical Structure Framework — **remove** Intraday Structure and daily SMA breaks; keep the weekly RSI/MFI zones; Bollinger Bands become broader trend context, not a trim trigger.
- Fibonacci framework — reframed from "re-entry zones" to **deployment-zone inputs**; the 23.6% rule becomes monitoring context, not a buy trigger.

**Rewrite:**
- "Daily Seven-Step Workflow" → "Weekly Analysis Workflow" with fewer, broader steps.
- "Re-entry Confirmation Checklist" → **Deployment Conditions**: the four conditions become tactical repair evidence, **not** a sizing ladder. State explicitly: *"4-of-4 tactical repair fully confirmed; it may improve deployment readiness, but strategic allocation remains independently governed by valuation, ERP trend, breadth, credit, drawdown depth, and long-term trend."*
- "Risk Management Rules" → **Allocation Governance Rules** (§5.7).
- "Updated Decision Matrix" — add rows for `Strategic Posture`, `Tactical State`, `Deployment Readiness`; `Recommended Action` becomes a synthesis of the posture fields, not an independent trading call.

**Add:**
- **Strategic vs Tactical Posture** section: full definitions from §4.1–4.2.
- **Deployment Readiness Framework** section: the drawdown/ERP band table from §4.3, framed as testable hypotheses.
- **Breadth-Lag Protocol** (descriptive): weak breadth restricts new allocation and caps confidence; it does not veto recognizing a repair, and it does not trigger a trade.
- **Weekly Change Log** output requirement: what improved / deteriorated / stayed unchanged across price, valuation/ERP, breadth, credit, and risk.

**Required language (verbatim intent):**

> **`trim_core` is rare.** It requires at least one of: *ERP materially deteriorated **and** price materially extended on a weekly basis; breadth **and** credit both materially deteriorated from their 4-week baselines; or the portfolio above its intended risk allocation*. Otherwise `hold_core` is correct even when deployment readiness is `not_ready`. "No add" and "trim what you own" are different decisions.

> **Drawdown depth from the cycle extreme is a mandatory input to deployment readiness.** A shallow correction with thin ERP cannot qualify as `partial_opportunity` regardless of the quality of the technical repair.

> **Reference-level reset:** On a decisive, confirmed close above the active swing high, the engine re-anchors swing references (see `reanchor_on_new_high()`). The report must display the active/current swing anchor date + price and must not use a prior high as resistance once price has accepted above it. A single new-high session is provisional until confirmed.

### 5.7 Role block: `framework/SPX-Claude-Role-Block.md`

Rewrite the "For each run" list (lines 7–14) to add:

> Output two independent postures on every run:
> - Strategic posture (add_core / hold_core / trim_core / defensive): governed by ERP, breadth, credit, valuation, long-term trend, drawdown depth. `trim_core` is rare — do not act on short-term overboughts or a single weak internal. "No add" and "trim what you own" are different decisions.
> - Tactical state (repairing / intact / extended / correcting / breaking_down): governed by price structure, weekly trend, and volatility regime. A tactical repair does not imply a strategic buy; a strategic hold/no-add does not imply the tactical picture remains broken.
> Deployment readiness (not_ready / watch / partial_opportunity / compelling_opportunity) governs whether new core capital is warranted, using valuation, drawdown depth, breadth, credit, and long-term trend — not short-term technical reversals.

### 5.8 `src/prompts.py`

1. **`HARD_CONSTRAINTS`** (lines 80–93): replace daily/trading phrasing with weekly + posture rules. Keep the numeric-truth and engine-enforcement constraints; remove "*signals actionable only when aligned*" (trading gate) and "*mixed data means hold and monitor*". Add posture-separation constraints from §5.6/§5.7.
2. **`DECISION_MATRIX_ROWS`** (lines 22–41): add `Strategic Posture`, `Tactical State`, `Deployment Readiness`.
3. **New `POSTURE_RENDERED_MATRIX_ROWS`** — the three posture rows. These are **not** added to `PRECOMPUTE_OWNED_MATRIX_ROWS` (they are rendered from `state.posture`, not `analysis_context` facts). Update `pass2_images.ALL_QUALITATIVE_MATRIX_ROWS` (line 57) to subtract both sets so the model treats posture rows as placeholders.
4. **Pass 1 task directive** (lines 268–322): add priorities for emitting `posture_*`, deriving deployment zones from the drawdown+ERP+breadth+credit combination, and validating that structure references are not stale. Replace next-session framing with the Friday/weekly framing.
5. **`_investor_fact_snippets()`** (lines 212–245): add prior swing high / reclaimed breakout support and `probability_regime` when present.
6. **`_conflict_block()`** (lines 48–265): surface strategic vs tactical tension plus readiness state.

### 5.9 `src/report_assembly.py`

1. **`_posture_display()`** (line 21): pull from `PostureState` — e.g. `"Strategic: Hold Core | Tactical: Extended | Deployment: Not Ready"`.
2. **`render_header_snapshot()`** (line 32): use the new display.
3. **New `render_deployment_zones_block()`**: render the `DeploymentZone` list (label, range, rationale, required confirmations) as a markdown table; inject after the tactical-levels section.

### 5.10 `src/memory.py` — weekly-first

1. **Keep** daily roll-up helpers only for the archived/legacy and chat paths; they no longer feed analysis prompts.
2. **`_normalize_action()`** (lines 101–151): the recommended-action text becomes a posture synthesis ("Hold core; deployment not ready; tactical repairing"); extend pattern matching to normalize to `hold_core`-type tokens rather than `deploy`/`trim` tokens.
3. **New weekly store + loader** (replacing `build_recent_summary` as the memory source):
   - `write_weekly_entry(entry, settings)` → one JSON per scheduled/provisional canonical entry under `memory/weekly/`.
   - `write_event_ledger(record, settings)` → append-only immutable ledger under `memory/events/` (timestamped, never rewritten).
   - `build_weekly_memory(settings, before_date)` → canonical block constructed from: the current run's posture + precompute truth, **prior 8–12 `scheduled_weekly` entries**, and **only material `event_review`/ledger records since the last scheduled Friday**. No daily narrative summaries, next-session calls, short-horizon targets, intraday observations, or stale swing references.
4. **Event write rule (enforced by the runner):**
   - **No material strategic change:** write a ledger entry only; do not touch weekly memory.
   - **Material strategic change:** write a ledger entry *and* create a versioned interim `WeeklyMemoryEntry` (`report_type="event_review"`, `supersedes_weekly_entry_id=<prior baseline id>`) that identifies the Friday baseline it temporarily replaces.
   - **Next scheduled run** reconciles ledger entries into the new canonical weekly entry.
5. **Roll-up summary** for chat/viewer (`recent_summary.md`) is **sourced from weekly entries**, not daily states.

**Do not** bolt the three posture fields onto the legacy daily rollup and call the job done — that would carry old intraday practice into the new weekly context. The weekly memory is a **different schema and store**, architected above.

### 5.11 Web viewer + chat preload

1. **`src/web/models.py`** — `RunSummary` (line 18): add `strategic_posture`, `tactical_posture`, `deployment_readiness`.
2. **`src/web/service.py`** — `_state_to_summary()` (line 52): populate from `state.posture`.
3. **`src/chat_preload.py`** — `CurrentBrief` + posture answer helpers: include the posture fields. **(defer)** if chat is not a priority; when enabled, chat context must also prefer the weekly store over `legacy_daily`.

### 5.12 `src/analysis_engine.py`

**`_fallback_state()`** (lines 350–396): add a `PostureState` default (`hold_core` / `correcting` / `not_ready` / empty zones / empty invalidations); keep the compatibility name — see the naming note in §7.

### 5.13 CLI and cadence

| Command | Behavior |
|---------|----------|
| `prepare --date D` / `import-run --date D` | Daily ingress only; **no LLM**, **no memory writes**. |
| `run-weekly --date <Fri>` | Canonical scheduled run. Must be a Friday (or `--force`). Writes a canonical `WeeklyMemoryEntry` after success. |
| `run-event --date D --trigger <type> --trigger-date <D>` | **Validated** interim review. Trigger type must be in the closed enum (`drawdown_5pct`, `drawdown_10pct`, `drawdown_15pct`, `vix_25`, `erp_crossing`, `week_sma_reclaim`, `credit_shift`, `point_breadth_washout`). The runner validates the trigger against stored/manifest data before any LLM call; missing/invalid trigger → rejected without an API call. Non-Friday `week_sma_reclaim` outputs are **provisional** and cannot write weekly memory. |
| `run` | **Removed from the CLI.** There is deliberately no generic full-pipeline run that can be manually invoked on any ordinary day. Engine entry (e.g., `run_daily_analysis`) remains internal for `migrate_perplexity`, tests, and the weekly/event commands. |

- **Trigger validation data:** `run-event` reads the precomputed `analysis_context.json` + market snapshot for the dated run (drawdown from cycle high, VIX close, ERP band, 50/200-day weekly close) and fails fast if the requested trigger is not borne out by the data.
- **Framework/format selection:** `run-weekly` and `run-event` share the full engine pipeline; the differences are framework version/prompt (weekly doc), memory (weekly + ledger), and cadence metadata.
- **`scripts/daily-run.sh`** rewrite:
  - Monday–Friday: `prepare` (and chart capture) only — no LLM calls.
  - Friday: `prepare` + `run-weekly` + `export-report` + iCloud copy.
  - Event monitoring is deferred to a follow-up alert script (§9); the framework doc defines the triggers; v1 events are manual `run-event`.

### 5.14 Framework version resolution

- New `framework_version = "weekly-2026-08"` (replacing `"daily-2026-06"`).
- Memory/state consumers that branch on framework version must use a small resolver: legacy daily reports keep the archived doc for reproduction, weekly runs only use the weekly doc. `DailyState`/`run_log` store both the version and the framework path used.
- Names in prompts that currently freeze `"daily-2026-06"` become versioned by the resolver in the builder.

---

## 6. Verification

- **`pytest`** — full suite green. Update fixtures that construct `DailyState` for required `posture` + `probability_regime`.
- **New tests.**
  - `tests/test_structure.py`: `reanchor_on_new_high` — no-op below swing high; unconfirmed (no geometry reset) on first close above reference; confirm only on 2nd qualifying close / retest; `failed_breakout` retains prior anchors; `anchor_version` increments once and only on confirmation; provisional-flag persists.
  - `tests/test_monte_carlo.py`: `_probability_regime` — extreme-first ordering (90/10 → `extreme_upside_asymmetry`), tilt labels, balanced.
  - `tests/test_cadence.py`: `run-event` on non-trigger data → rejected before LLM; non-Friday `week_sma_reclaim` → provisional label; `run-weekly` non-Friday without `--force` → rejected; `run` command no longer exists in the app command list.
  - `tests/test_weekly_memory.py`: seed produces 1 canonical entry; 2 no-material event runs write ledger entries only; 1 material event writes an interim entry with `supersedes_weekly_entry_id`; next scheduled run reconciles.
  - `tests/test_state_enforcement.py`: posture rows rendered from `state.posture`; free-written posture rows overwritten from `state.posture`; `state.posture` itself never overwritten by `apply_precomputed_fields`.
- **Serialization test**: `DailyState` round-trips with `PostureState` + deployment zones + `probability_regime`.
- **Weekly smoke**: one Friday run + one validated event run produce valid state + report with all three posture outputs and the deployment-zones block.
- **Regression expectation for July sequence**: July 30 → *Strategic: hold_core / Tactical: repairing / Deployment: not_ready*; Aug 3 → *Strategic: hold_core / Tactical: extended / Deployment: not_ready* — without any trade-authorization output.

---

## 7. What this explicitly is not

- **Not a muted daily trading engine.** No generic run; no next-session actions. Reports posture/readiness/zones on a weekly-to-event cadence.
- **Not a tactical sleeve.** No STARTERS/sizing ladders/stops. All Tier 3 mechanics are removed.
- **Not a mandate to stay permanently cautious.** Readiness activates at genuine valuation-plus-drawdown opportunity.
- **Not new analytical machinery.** The only new computation is the small deterministic breakout state machine and the probability-regime label.

**Naming note:** `DailyState` is retained as the state schema for scheduled weekly and event runs during this surgical PR — it is a *compatibility name*, not endorsement of daily analysis. A follow-on rename to `AnalysisState` is tracked (deferred) so the schema mirrors the weekly mandate.

---

## 8. Migration and sequencing

1. **Step 0 — memory migration** (before anything else): archive to `legacy_daily/`, create weekly + event stores, seed first canonical baseline with durable data only (2026-08-03).
2. **Schema first** (`schemas.py`): new types (`PostureState`, `DeploymentZone`, `BreakoutState`, `WeeklyMemoryEntry`) + `posture` field + breakout fields + `probability_regime`. This forces every constructor/fixture change.
3. **Engine mechanics**: `monte_carlo.py` regime label → `structure.py` re-anchor + breakout state machine → `precompute.py` wiring/persistence → `state_enforcement.py`.
4. **Cadence**: CLI `run-weekly` + `run-event` (with trigger validation), remove `run`, `daily-run.sh` rewrite.
5. **Memory**: weekly loader + ledger writes + write rule.
6. **Framework + prompts**: new framework file, role block, `HARD_CONSTRAINTS`, tasks, `POSTURE_RENDERED_MATRIX_ROWS`.
7. **Outputs**: report assembly, web viewer, chat preload, fallback state.
8. **Tests** + weekly smoke.
9. **Framework version resolver** + report path/version stamping.

## 9. Open questions / follow-ups (not blocking)

- **Automated trigger monitoring** (drawdown / VIX / ERP / SMA alert script calling `run-event`) — deferred.
- **`probability_regime` band thresholds** — starting hypotheses (§5.2); tune against weekly data.
- **Readiness bands** (drawdown %, ERP ≥0.5/1.0%) — explicitly framed as testable hypotheses.
- **`DailyState`→`AnalysisState` rename** — follow-on migration; documented in §7.
- **README update** — required for this substantial scope change; produce in the implementation PR, not the plan.

---

_End of document. Revisions tracked vs. the original PR-23 draft in git history._