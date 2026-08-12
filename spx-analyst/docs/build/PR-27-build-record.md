# Build Record — PR-27: Structural-Bias Arc History and Canonical Memory Protection

**Date:** 2026-08-11
**Phase:** PR-27 structural-bias continuity
**Status:** Complete — implemented, corrected, tested, reviewed, and committed
**Cadence:** Daily (unchanged)

---

## 1. What Was Built

PR-27 fixes a continuity problem in the daily LLM context. The model previously
received only six prior daily states, so it could describe a regime as a
short-lived seven-session condition even when the same structural bias had been
active for months.

The phase delivers four connected changes:

1. **Deterministic structural-bias arc projection** — loads the complete valid
   canonical daily-state archive, collapses adjacent identical classifications,
   preserves each arc's actual start date, and counts analyzed sessions.
2. **Compact prompt context** — injects the prior arc into Pass 1 and the arc
   including today's validated classification into Pass 2.
3. **Rolling-summary cleanup** — removes repeated structural-bias labels and the
   six-session regime footer from the detailed posture summary. The dedicated
   arc is now the only bias-history representation in the daily prompts.
4. **Canonical memory protection** — restores the real 2026-06-12 chart-run
   state after a Perplexity backfill had overwritten it, and prevents future
   migrations from silently replacing an existing canonical state.

The LLM still determines today's structural bias from current charts and the
qualitative framework. Python supplies historical facts only; it does not score,
override, or mechanically constrain the classification.

## 2. Key Decisions

| Decision | Choice | Rationale |
|---|---|---|
| History source | Valid `memory/daily_states/*-state.json` files | Daily states are the canonical persisted classification events |
| Projection storage | `memory/rolling/structural_bias_history.json` | Durable and auditable, but fully rebuildable from source states |
| Display window | Trailing 12 calendar months | Matches the chart context while retaining long-running arcs |
| Arc start date | Always preserve the actual classification date, even before the window | Regime age is the information the model needs |
| Arc selection | Display arcs that overlap the window | Avoids truncating a current arc at the window boundary |
| Duration | Count valid analyzed sessions in the complete arc | Weekends, holidays, missing runs, and failed runs do not count |
| Classification authority | LLM judgment from current evidence | The framework contains nuance that should not be reduced to a scoring matrix |
| Prompt context | Compact table only | Keeps the first version self-explanatory and low-bias |
| Pass 1 timing | Prior states only | Today's classification does not yet exist |
| Pass 2 timing | Prior states plus today's validated state | The report writer can describe today's true arc duration |
| Detailed memory | Keep six-session posture summary, remove bias labels/footer | Recent changes and tensions remain useful; bias history has a dedicated source |
| Migration overwrite | Preserve existing canonical state by default; explicit opt-in to replace | Prevents synthetic backfills from silently superseding chart runs |

## 3. Architecture

### 3.1 Daily analysis flow

```text
memory/daily_states/*.json
              │
              ▼
     load_all_states(before_date=date)
              │
              ▼
     build_structural_bias_arcs(...)
              │
              ▼
     structural_bias_arc_prompt(...)
              │
              ├──────────────► Pass 1 prompt: prior completed arc
              │
              ▼
       LLM emits DailyState
              │
              ▼
     append today's validated state in memory
              │
              ▼
     build_structural_bias_arcs(...)
              │
              └──────────────► Pass 2 prompt: current updated arc
              │
              ▼
       successful save_outputs()
              │
              ├─ mirror current state to canonical memory
              ├─ rebuild recent six-session summary
              └─ rebuild structural_bias_history.json
```

### 3.2 Arc construction

`build_structural_bias_arcs()` sorts valid states chronologically, deduplicates
same-date records, groups adjacent equal `structural_bias` values, and creates
one `StructuralBiasArc` per uninterrupted group. An arc is retained when its
last observed session is on or after the display-window start. Its actual first
classification date and full observed-session duration are preserved.

The current archive now resolves to one arc:

```text
2026-06-01 | Late Bull / Topping | 45 sessions, ongoing
```

### 3.3 Canonical-state correction

The actual 2026-06-12 chart run classified the session as `Late Bull / Topping`
with close `7431.46`. A later Perplexity migration had overwritten canonical
memory with a synthetic `Mid Bull` state and close `7450.25`. The canonical
state and report were restored from:

```text
output/2026-06-12/2026-06-12-state.json
output/2026-06-12/2026-06-12-analysis.md
```

The migration path now checks for an existing canonical state before doing LLM
work and raises `MigrationError` unless `overwrite_existing=True` is explicitly
provided. The CLI exposes that opt-in as `--overwrite-existing`.

## 4. Component Relationships

| Component | Role | Depends on |
|---|---|---|
| `src/memory.py` | State archive loading, arc grouping, prompt rendering, projection persistence, rolling summary formatting | `Settings`, `DailyState`, `files` |
| `src/analysis_engine.py` | Builds Pass 1 prior arc, Pass 2 current arc, and persists the projection after success | `memory`, prompt builders, state enforcement |
| `src/prompts.py` | Accepts and inserts the compact arc block into both prompt builders | `DailyState`, analysis context |
| `src/config.py` | Exposes `structural_bias_history_path` under `memory/rolling/` | `Settings` |
| `src/migrate_perplexity.py` | Protects canonical states and rebuilds the bias projection after migration | `files`, `memory` |
| `src/cli.py` | Adds `rebuild-bias-history` and migration `--overwrite-existing` operator controls | `memory`, `migrate_perplexity` |
| `memory/daily_states/` | Canonical source events | Successful daily or intentional migration writes |
| `memory/rolling/structural_bias_history.json` | Rebuildable compact arc projection | Canonical daily states |

## 5. API Contracts

### 5.1 Arc model

```python
@dataclass(frozen=True)
class StructuralBiasArc:
    classified_on: str
    structural_bias: StructuralBias
    duration_sessions: int
    ended_on: str | None
```

`StructuralBias` remains the existing closed set:

```text
Early Bull
Mid Bull
Late Bull / Topping
Bear Market
```

### 5.2 Arc functions

```python
def load_all_states(
    *, before_date: str | None = None,
    settings: Settings | None = None,
) -> list[DailyState]

def build_structural_bias_arcs(
    states: list[DailyState],
    *,
    display_from: str | None = None,
) -> list[StructuralBiasArc]

def structural_bias_arc_prompt(
    arcs: list[StructuralBiasArc],
) -> str

def rebuild_structural_bias_history(
    *,
    as_of_date: str,
    settings: Settings | None = None,
) -> tuple[list[StructuralBiasArc], Path]
```

### 5.3 Prompt contract

Pass 1 and Pass 2 accept an optional rendered block:

```python
structural_bias_arc: str | None = None
```

The rendered block is intentionally minimal:

```text
## Structural Bias Arc

| Classified on | Structural bias | Duration |
|---|---|---:|
| 2026-06-01 | Late Bull / Topping | 45 sessions, ongoing |
```

Pass 1 excludes the current date. Pass 2 adds the validated current state in
memory before rendering. The arc is injected regardless of
`SPX_INCLUDE_MEMORY`; that setting controls only the detailed posture summary.

### 5.4 Persisted projection contract

```json
{
  "as_of_date": "2026-08-11",
  "window_start": "2025-08-11",
  "arcs": [
    {
      "classified_on": "2026-06-01",
      "structural_bias": "Late Bull / Topping",
      "duration_sessions": 45,
      "ended_on": null
    }
  ]
}
```

The projection is written atomically through `write_json_atomic()` after a
successful canonical state save. Historical rebuilds use `--date` as an
exclusive upper bound, so future states cannot contaminate a past projection.

### 5.5 Operator commands

```bash
python -m src.cli rebuild-bias-history --date YYYY-MM-DD
python -m src.cli migrate-perplexity --history <path> --overwrite-existing
```

Migration without `--overwrite-existing` refuses to replace an existing
canonical state for the session date.

## 6. Data and Persistence Behavior

- Valid canonical states are loaded from the full archive, not limited by the
  six-session prompt-memory setting.
- Invalid state files are skipped using the existing memory-loader behavior.
- Same-date state files are deduplicated by date during arc construction.
- Failed daily runs do not mirror placeholder states into canonical memory and
  therefore do not affect future arc durations.
- Missing trading days do not split an arc; duration counts observed valid
  analysis sessions, not calendar gaps.
- The six-session summary now contains alignment, action, categorical signals,
  changes, tensions, conflicts, and the unresolved watchlist, but no structural
  bias labels or short regime footer.

## 7. Test and Verification Record

Added coverage for:

- Arc grouping and actual start-date preservation.
- Full-duration calculation across the display-window boundary.
- Compact prompt rendering and singular/plural session wording.
- Projection persistence.
- Future-state exclusion during historical rebuilds.
- Removal of bias from detailed rolling summaries.
- Arc injection into both prompt builders.
- Arc injection when detailed memory is disabled.
- Migration refusal when canonical state already exists.

Verification completed:

```text
443 passed, 1 warning
git diff --check: passed
python -m compileall: passed
rebuild-bias-history --date 2026-08-11: passed
```

The one test warning is the existing Starlette/httpx deprecation warning and is
unrelated to this phase.

## 8. Context for the Next Phase

- The structural-bias arc is historical context, not a deterministic
  classification matrix. Future prompt changes should preserve the LLM's
  current-chart judgment as the classification authority.
- `memory/daily_states/` is the source of truth. The rolling JSON projection can
  always be deleted and rebuilt.
- The current corrected history shows `Late Bull / Topping` continuously from
  2026-06-01. The prior one-session `Mid Bull` arc was an artifact of an
  overwriting Perplexity backfill, not a genuine chart-run classification.
- The migration overwrite flag is intentionally explicit. If an operator wants
  to replace a chart-run state, they must do so knowingly and should rebuild the
  arc afterward.
- Chat preload still has its own compact arc brief based on the configured recent
  window. This phase changes the daily analysis prompts and canonical bias
  projection only; extending the 12-month bias table into chat is a separate
  decision.
- Existing unrelated deployment/UI and EPS work should remain independently
  reviewable.
