# PR-3: Memory rollup overhaul

**Status:** Implemented  
**Framework version:** `daily-2026-06`  
**Design plan:** [`.cursor/plans/memory_rollup_overhaul_012f6344.plan.md`](../../.cursor/plans/memory_rollup_overhaul_012f6344.plan.md) (aligned to this record)  
**Backfill:** [PR-3.1](PR-3.1-perplexity-backfill.md) — rebuild early-June memory from Perplexity markdown without chart packs  
**Design review:** [PR-3.2](PR-3.2-memory-design-decision-brief.md) — **Decision: Option B** (no char truncation on selected fields; narrative deferred)

## Summary

Redesigns the rolling operational memory **prompt payload** into a strict posture snapshot: regime continuity, categorical signal labels, normalized action posture, structured deltas, and an unresolved watchlist. Full `DailyState` JSON on disk is unchanged; only the text rollup injected into Pass 1/Pass 2 changes.

Each run remains a **fresh analysis**. `analysis_context` is the sole numeric source of truth for today's session ([PR-1](PR-1-spx-daily-framework-migration.md), [PR-2](PR-2-spx-two-pass-prompt-overhaul.md)).

## Operator contract

| Behavior | When |
|----------|------|
| Mirror `{date}-state.json` and `{date}-analysis.md` to `memory/` | Every successful run |
| `rebuild_rolling_summary()` → `memory/rolling/recent_summary.md` + `recent_memory.json` | Every successful run |
| Inject posture snapshot into Pass 1/Pass 2 | Only when `SPX_INCLUDE_MEMORY=true` |

`SPX_INCLUDE_MEMORY` gates **prompt injection only**, not archival or rolling rebuild.

## Rollup structure

### Per-day block (oldest → newest)

```
### {date}
{structural_bias} | {signal_alignment.overall} | action: {normalized_action}
signals: F&G fear | VIX elevated | RSI neutral | credit wide | vs50d below
changed: {item1}; {item2}; {item3}
tension: {primary_tension}
conflicts: {id} | {layers} | {framework_rule}
```

**Excluded from rollup:** `spx_close`, numeric signals, `narrative_summary`, `base_case`, `trend_regime`, Monte Carlo / Fib / ERP prose, per-day `open_questions`.

### Rollup footer

```
---
Regime arc (N sessions): Late Bull / Topping (held)
Unresolved watchlist: {q1} | {q2}
```

## Categorical signal buckets

Deterministic bucketing from `SignalSet` fields. Internal bucket keys use snake_case for matching; **rendered prompt output uses human-readable labels** (spaces, no floats).

Example rendered line:

```
signals: F&G fear | VIX elevated | RSI neutral | credit wide | vs50d below
```

| Source field | Rendered label (examples) | Bucketing rule |
|--------------|---------------------------|----------------|
| `fear_greed_zone` (fallback: `fear_greed` score) | extreme fear, fear, neutral, greed, extreme greed, unknown | Zone normalized; score bands 0–24 / 25–44 / 45–55 / 56–74 / 75+ |
| `vix_regime` | low, normal, elevated, high, unknown | Keyword parse on regime text (`elevated` before `high` to avoid misbucketing e.g. "highly elevated") |
| `rsi14` | oversold, neutral, overbought, unknown | <30 / 30–70 / >70 |
| `high_yield_spread` | tight, normal, wide, extreme, unknown | <1.0 / 1.0–1.3 / 1.3–1.5 / >1.5 |
| `pct_vs_50dma` | below, near, above, extended, unknown | <-1 / -1..+3 / +3..+8 / >+8 |

No numeric indicator values appear in the `signals:` line.

## Action normalization (closed set)

**Exact emitted tokens** (wording contract):

| Token | Meaning |
|-------|---------|
| `deploy` | Active add / re-entry deployment |
| `light deploy` | Partial / conditional add |
| `hold and monitor` | Default hold; no trim or add edge |
| `trim bias` | Defensive trim posture without full exit |
| `defensive patience` | Capital preservation; no new longs |

**Matching order** (first match wins; legacy `hold_schk_` / `schk_` prefixes stripped first):

| Step | Pattern | Token |
|------|---------|-------|
| 1 | `partial trim`, `defensive trim`, `wave 1`, then bare `trim` | `trim bias` |
| 2 | literal `light deploy` | `light deploy` |
| 3 | `deploy`, `reentry`, `re-entry`, **`add tranche`** | `deploy` |
| 4 | `partial`, `25%`, `light`, bare **`tranche`** (excludes strings containing `add tranche`) | `light deploy` |
| 5 | `defense`, `defensive`, `patience`, `capital preservation`, `protect` | `defensive patience` |
| 6 | `hold`, `monitor`, `wait`, `gtc` | `hold and monitor` |
| 7 | (no match) | `hold and monitor` |

`add tranche` always resolves to `deploy` because step 3 runs before the bare-`tranche` rule in step 4.

Final token capped at 60 characters (pathological matrix strings only).

## Selection limits (PR-3.2 Option B)

Per-day rollup uses **selection limits** only — no character truncation on selected text.

| Field | Selection limit | Truncation |
|-------|-----------------|------------|
| Normalized action | closed set | 60 chars only for unmapped matrix strings |
| `what_changed_today` | **3 items** | **None** — full text each |
| `primary_tension` | 1 | **None** — full text |
| `conflicting_evidence` | **2** (weight order) | **None** — full `framework_rule` |
| Unresolved watchlist | **2 questions** (eligibility rules) | **None** — full text |

**Excluded from rollup:** `narrative_summary` (deferred), `spx_close`, numeric signals, `base_case`, `trend_regime`, Monte Carlo / Fib / ERP prose, per-day `open_questions`.

Typical 6-day rollup: ~2,000–2,500 tokens (~8–10k chars) with real states; still well below pre-PR-3 ~3,700-token narrative replay.

## Truncation caps (superseded)

~~PR-3.1 char caps (60/120/90/80)~~ removed in PR-3.2 Option B. See [PR-3.2 decision brief](PR-3.2-memory-design-decision-brief.md).

## Unresolved watchlist

Derived from `open_questions` across loaded states (newest-first):

1. **Eligible** if in the most recent state **or** normalized text matches in ≥2 of the last 3 sessions
2. **Expired** after 2 consecutive most-recent sessions without a normalized match
3. **Ordering** by most recent qualifying session date (newest first)
4. **Wording** exact string from the newest qualifying state (normalization for dedupe only)
5. **Cap** 2 items × 80 chars display truncation

## Load observability

`load_recent_states()` — unchanged signature; returns `list[DailyState]`.

`load_recent_states_with_stats()` — new companion returning `(states, MemoryLoadStats)` with:

- `requested`, `loaded`, `skipped_invalid`, `skipped_before_date`

When `SPX_INCLUDE_MEMORY=true`, the run artifact `output/{date}/run_log.json` includes a top-level `memory_load` object with those counts. Warnings emit **only** when `skipped_invalid > 0` (young archives with zero invalid skips do not warn).

## Prompt wrapper

```
## Prior posture snapshot (continuity only — not authoritative for today's numerics)
Each run is a fresh analysis. Use this block only to track regime shifts, action posture,
day-over-day changes, and unresolved tensions. All calculations, thresholds, targets, and
price levels come from today's analysis_context and charts — never from prior sessions.
```

**Omitted entirely** when either:

- `SPX_INCLUDE_MEMORY=false` (engine passes `recent_summary=None`), or
- `recent_summary is None` for any other caller (e.g. prompt builders with no prior states)

When memory is enabled but the archive is empty, the block is still injected with `No prior sessions on record.` (within spec).

## Before / after

| Dimension | Before | After |
|-----------|--------|-------|
| Purpose | Narrative replay | Strict posture snapshot |
| Historical numerics | close + prose | **None** (categorical only) |
| ~Tokens (6 days) | ~3,700 | ~550–650 |
| Rolling rebuild | Coupled to `include_memory` | Every successful run |
| Invalid skip visibility | Silent | Logged; warn on invalid |

## Files changed

- `src/memory.py` — formatter rewrite, `MemoryLoadStats`, categorical labels
- `src/analysis_engine.py` — unconditional rebuild, `memory_load` logging
- `src/prompts.py` — posture snapshot header
- `tests/test_memory_rollup.py`, `test_prompt_builder.py`, `test_engine.py`
- `README.md` — operator contract
