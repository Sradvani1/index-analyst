# Build Record — PR-24: Daily Surgical Fixes (Swing-High Re-Anchoring + Probability Regime)

**Date:** 2026-08-04
**Phase:** PR-24 daily surgical fixes
**Status:** Complete — implemented, tested, reviewed, committed
**Cadence:** Daily (unchanged)

---

## 1. What was built

Two cadence-neutral mechanical fixes extracted from the PR-23 weekly-framework review:

1. **Swing-high re-anchoring with a persistent anchor-authority state machine** — fixes the "reference staleness" defect where the report kept an obsolete swing high (July 22: 7,525.94) as the active anchor while price made a new record high (Aug 3: 7,600.50).
2. **Monte Carlo probability-regime label** — replaces the binary "actionable / monitor below threshold" edge signal with a descriptive, threshold-independent label of the probability distribution shape.

The weekly restructuring (PR-23) remains parked; only the two cadence-neutral defects crossed over.

## 2. Key decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Anchor authority | One resolver (`resolve_structure_anchors`) is the sole publisher of active anchor geometry; `compute_structure` remains an observation producer only | Prevents two competing anchor-setters from racing on the same session |
| Confirmation rule | **Two completed daily closes above the former swing high total**; trigger close counts as close #1 | Filters single-session noise while not leaving geometry stale an extra day |
| Breakout status machine | `none → unconfirmed_new_high → confirmed_new_high \| failed_breakout`; failed breakout restarts a fresh candidate cycle on a later qualifying close | Idempotent, persistent across runs |
| Accepted-high ratchet | `candidate_high` ratchets to the highest session high in the acceptance window; after confirmation, higher highs update `active_swing_high_price` **without** incrementing `anchor_version` | `anchor_version` marks a new structural leg, not each incremental record high |
| Reference authority | Persisted `StructureAnchorState.active_swing_high_price` is the reference for transitions — not the (potentially stale) legacy observation | Solves "persistence over legacy staleness": a stale 7,526 observation cannot supersede a published 7,600 anchor |
| Fib-low selection | Three-tier fallback: `intermediate_confirmed` → `prior_active_fallback` → `unavailable` (ladder suppressed with warning) | Re-anchor the high always; never block on a missing low; never manufacture a low |
| Initialization | First run / corrupt store: seed from `compute_structure()` at `anchor_version = 1`, emit warning, no re-anchor event | Deterministic cold start |
| Regime label semantics | Regime **supplements** the `actionable` bool, never replaces it | Framework requires reporting whether the probability clears the structural-bias threshold |
| Regime thresholds | extreme ≥ 0.85 (directional), tilt ≥ 0.70, else `balanced`; extreme checked first | A 90/10 reading reads as extreme, not a mere tilt |

## 3. Architecture

### 3.1 Anchor authority (Fix 1)

```
market bars / sma50 / pct_above_200dma
            │
            ▼
   compute_structure()          ← observation producer (unchanged; local-extrema detection)
            │  StructureResult (observations)
            ▼
   resolve_structure_anchors()  ← SOLE PUBLISHER
   (result, bars, anchor_state, sma50, *, pct_above_200dma)
            │
            ├─ conventional-swing path: legacy detector confirms a higher swing high → immediate publish, version+1
            ├─ breakout machine: two-close acceptance (unconfirmed → confirmed | failed), ratchet, re-attempt
            └─ emits geometry via _result_from_anchor_state() on EVERY path (no stale observation leakage)
            │
            ▼
   StructureResult (authoritative) + StructureAnchorState (persisted)
```

- **Observation producers:** `compute_structure` local-extrema detection (`pullback_3pct` / `five_sessions`) and the two-close breakout logic. Neither independently publishes anchors.
- **Sole publisher:** `resolve_structure_anchors()` resolves all observations into at most one anchor transition and one `anchor_version` increment per trading session.
- **Simultaneous confirmation:** conventional-swing and breakout confirmation on the same bar = one transition (corroborating evidence), never separate resets.
- **Result/state sync invariant:** returned `StructureResult` and `StructureAnchorState` agree on active high/low price, low source, and `anchor_version`. `_structure_to_schema()` maps only the final `StructureResult`.
- **Atomic output:** on a true transition the resolver constructs a fresh `StructureResult` from the resolved high/low tuple and recomputes fib, liquidation, and MC targets together — no mixed old-leg/new-leg geometry.

### 3.2 Probability regime (Fix 2)

```
run_monte_carlo()
   └─ _probability_regime(prob_up_adj, prob_down_adj) → str   (extreme-first, directional)
        ├─ populate MonteCarloContext.probability_regime      (source of truth)
        └─ populate each ThresholdEvaluationRow.probability_regime (matching copy for display)
apply_precomputed_fields()
   └─ MonteCarloDetail.probability_regime ← context-level value (enforcement source)
sync_matrix_precomputed_rows()
   ├─ Monte Carlo Threshold row: reading = effective threshold %, signal = "passes"/"fails"
   └─ Monte Carlo Edge row:      reading = adjusted probability %, signal = regime label
```

`actionable` bool stays on `ThresholdEvaluationRow` and continues to feed the effective-threshold gate; `EmitDailyStateInput` is unchanged (regime is engine-governed, not LLM-authored).

## 4. Component relationships

| Component | Role | Depends on |
|-----------|------|-----------|
| `src/structure.py` | `StructureAnchorState`, `_find_intermediate_swing_low`, `_result_from_anchor_state`, `resolve_structure_anchors` | numpy, dataclasses |
| `src/precompute.py` | `run_precompute` wiring: load/seed state → `compute_structure` → `resolve_structure_anchors` → straddle guard → persist | structure, schemas, config |
| `src/schemas.py` | `StructureContext` tail fields, `ActiveSwingLowSource`, `probability_regime` fields, `SwingConfirmation` literal | pydantic |
| `src/config.py` | `anchor_state_path` (default `data/master/anchor_state.json`) | pydantic-settings |
| `src/monte_carlo.py` | `_probability_regime` + populate context/rows | schemas |
| `src/state_enforcement.py` | Threshold/Edge row signals, `MonteCarloDetail.probability_regime` enforcement | prompts, schemas |
| `src/report_assembly.py` | Tactical-levels block (prior swing high as reclaimed support, fib-ladder suppression), MC facts block | schemas |
| `src/prompts.py` | `_investor_fact_snippets`: regime, prior swing high, fib-low source, unavailable messaging | schemas |
| `src/prepare_run.py` | `prepare` CLI summary: regime label + threshold result | schemas |
| `src/validation.py` | `_matrix_uniformly_directional` bullish-token list (`upside`, `extreme`) | — |

## 5. API contracts

### 5.1 Resolver

```python
def resolve_structure_anchors(
    result: StructureResult,
    bars: Sequence[PriceBar],
    anchor_state: StructureAnchorState,
    sma50: np.ndarray,
    *,
    pct_above_200dma: float,
) -> tuple[StructureResult, StructureAnchorState, list[str]]
```

**Breakout state machine transitions** (reference = `anchor_state.active_swing_high_price`):

| Prior status | Condition | Transition |
|---|---|---|
| any | close == reference | no change (pending) |
| `none` | close > reference | → `unconfirmed_new_high`; candidate_high = session high; closes = 1; provisional warning |
| `unconfirmed_new_high` | close < reference | → `failed_breakout`; prior anchors retained |
| `unconfirmed_new_high` | close > reference | closes += 1; candidate ratchets on strictly-higher session high; on closes == 2 → `confirmed_new_high`, version +1 |
| `failed_breakout` | close > reference | → `unconfirmed_new_high` (fresh candidate cycle, closes = 1) |
| `confirmed_new_high` | close > reference | ratchet high without version increment |

**Conventional-swing path:** if `result.active_swing_high_price > reference`, publish immediately, version +1, reset status to `none` (no two-close wait).

### 5.2 Probability regime

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

Labels: `balanced`, `upside_tilt`, `downside_tilt`, `extreme_upside_asymmetry`, `extreme_downside_asymmetry`.

## 6. Data models

### 6.1 `StructureAnchorState` (persisted to `data/master/anchor_state.json`)

```python
@dataclass(frozen=True)
class StructureAnchorState:
    active_swing_high_price: float | None = None
    active_swing_high_date: str | None = None
    active_swing_low_price: float | None = None
    active_swing_low_date: str | None = None
    active_swing_low_source: str | None = None   # intermediate_confirmed | prior_active_fallback | unavailable
    swing_high_confirmation: str | None = None
    swing_low_confirmation: str | None = None
    status: str = "none"                          # none | unconfirmed_new_high | confirmed_new_high | failed_breakout
    candidate_high: float | None = None
    candidate_date: str | None = None
    closes_above_reference: int = 0
    anchor_version: int = 1
```

Persisted via `json.dumps(dataclasses.asdict(state))`; gitignored (runtime state, not committed). Missing/corrupt file → re-initialized from `compute_structure` at version 1.

### 6.2 `StructureContext` / `StructureResult` tail fields (optional, backward compatible)

```python
prior_swing_high_price: float | None = None
prior_swing_high_date: str | None = None
active_swing_low_source: Optional[ActiveSwingLowSource] = None
anchor_version: int = 1
```

### 6.3 Probability-regime schema additions (all defaulted `"balanced"` → stored artifacts parse unchanged)

- `ThresholdEvaluationRow.probability_regime: str = "balanced"`
- `MonteCarloContext.probability_regime: str = "balanced"` (source of truth)
- `MonteCarloDetail.probability_regime: str = "balanced"`

### 6.4 New/updated literals

- `SwingConfirmation` += `"unconfirmed_new_high"`
- `ActiveSwingLowSource = Literal["intermediate_confirmed", "prior_active_fallback", "unavailable"]`

## 7. Test coverage

`tests/test_structure_resolver.py` (21 tests): state-machine transitions, ratchet behavior, no-downgrade, persistence-over-legacy-staleness, no-op-after-breakout, conventional path, fib-low fallback tiers, simultaneous confirmation, initialization semantics, candidate-date preservation, fib-unavailable downside target, `reference=None` safety, no-future-fib-leakage.

`tests/test_monte_carlo.py`: `_probability_regime` ordering + population. `tests/test_state_enforcement.py`: Threshold/Edge row signals, `probability_regime` enforcement. `tests/test_precompute_integration.py`: anchor-state persistence + reuse of a persisted anchor. `tests/conftest.py`: hermetic `anchor_state_path` in test settings.

**Full suite:** 415 passed, 2 failed (both `test_chat_preload`, pre-existing/unrelated).

## 8. Persistence and runtime behavior

- `data/master/anchor_state.json` is **not currently seeded** (file absent). The next `prepare` or `run` (via `run_precompute`) initializes it from `compute_structure` at `anchor_version: 1` and emits the warning *"Anchor state initialized from current structural computation."*
- The 07-29 → 08-03 backfill smoke test confirmed: Aug 3 (close 7,600.50 > 7,525.94) now emits `unconfirmed_new_high` + provisional warning instead of silently retaining the stale anchor.

## 9. Context for the next phase

- **PR-23 (weekly framework)** is parked and marked as such; the cadence-neutral defects from its review were extracted here.
- The anchor-authority model (`resolve_structure_anchors`) is the foundation for any future weekly or event-driven cadence — the persistent state already generalizes beyond daily.
- `StructureAnchorState` intentionally carries the authoritative anchor identity (not just breakout status) so the reference never regresses to a stale legacy observation — this design is what makes the whole mechanism deterministic and replayable.
- Follow-up candidates from the PR-24 review that were intentionally **not** built: posture split (strategic/tactical), weekly memory store + event ledger, cadence contract (`run-weekly`/`run-event`), `trim_core` rule, framework version resolver — all remain in the parked PR-23 scope.
