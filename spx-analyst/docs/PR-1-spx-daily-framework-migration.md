# PR-1: SPX Daily Framework Engine Migration

**Status:** Complete  
**Framework version:** `daily-2026-06`  
**Test suite:** 62 tests passing (`pytest`)

---

## Summary

This PR rebuilds the `spx-analyst` engine around the **SPX Daily Analysis Framework** and **SPX Claude Role Block**. It replaces the legacy S&P 500 / SCHK V1/V3 methodology at runtime with a three-stage pipeline:

1. **Step 0 — Python precompute** (yfinance + manual EPS → `analysis_context.json`)
2. **Pass 1 — Structured state** (charts + precompute → `DailyState` JSON)
3. **Pass 2 — Markdown report** (validated state + charts → daily analysis)

Monte Carlo, ERP, structural levels, and SPX close are **owned by Python**. The LLM interprets charts for qualitative signals and narrative; it does not recalculate GBM or ERP.

---

## Motivation

| Problem (before) | Solution (after) |
|------------------|------------------|
| LLM estimated Monte Carlo probabilities in Pass 1 | Deterministic 20k-path GBM in `monte_carlo.py` |
| `external_context.json` duplicated chart data (VIX, F&G, spreads) | EPS-only manual input; charts supply sentiment |
| SCHK / V1 8-row matrix wired through prompts and web | SPX-only, 18-row Daily matrix |
| No numeric source of truth per run | `analysis_context.json` written before Pass 1 |
| `manifest.close` could drift from market reality | yfinance `^GSPC` sole math source; manifest warns only |

---

## Architecture

```
Run inputs                    Step 0 (Python)                 Two-pass LLM
─────────────                 ───────────────                 ────────────
charts/ (15 images)    →     market_data.py (^GSPC/^VIX/^TNX)
manifest.json          →     structure.py   (swing/Fib/MC targets)
external_context.json  →     valuation.py   (ERP, P/E)
                             monte_carlo.py (GBM + thresholds)
                                    ↓
                             analysis_context.json  ──────→  Pass 1: emit_daily_state
                                    │                        Pass 2: markdown report
                                    ↓
                             state_enforcement.py (post-Pass 1)
                                    ↓
                             output/ + memory/ artifacts
```

### Data authority (DL-2)

| Field | Precompute / math | Report / qualitative |
|-------|-------------------|---------------------|
| SPX close | yfinance `^GSPC` | Cite `analysis_context` |
| VIX | yfinance `^VIX` | Chart 13 for regime geometry |
| 10Y yield | yfinance `^TNX` | Charts for context only |
| Forward/trailing EPS | `external_context.json` | Precomputed P/E in matrix |
| RSI, MFI, F&G, breadth | — | Charts only |
| Monte Carlo | `analysis_context.json` | Immutable in Pass 1/2 |
| Structural bias | Pass 1 LLM (charts) | Selects MC threshold row |

`manifest.close` is validation-only (warn if drift > 0.15%). Never used in calculations.

---

## New modules

| Module | Responsibility |
|--------|----------------|
| `src/market_data.py` | yfinance fetch; cache `market_history.json`; build `MarketDataContext` |
| `src/structure.py` | DL-3 swing detection, Fib levels, liquidation zones, MC targets |
| `src/valuation.py` | Forward/trailing P/E, ERP, 20-session ERP trend, re-entry floor |
| `src/monte_carlo.py` | Seeded GBM (20k paths, 60d); exhaustion discount; `threshold_evaluation` at 65/70/75 |
| `src/precompute.py` | Step 0 orchestrator |
| `src/state_enforcement.py` | Post-Pass 1: enforce `spx_close`, `monte_carlo`, precompute-owned matrix rows |

---

## Monte Carlo target straddle guard (Option A)

The framework requires Monte Carlo to report actionable probabilities, key levels,
and drift-path expectations for the **current** market state. The engine therefore
must never simulate with targets that fail to straddle spot.

`structure.reanchor_downside_for_straddle()` runs after structure + valuation and
before Monte Carlo. It enforces the invariant:

```
downside_target < spx_close < upside_target
```

When the close has fully retraced (and broken below) the active swing low, the prior
H→L Fibonacci ladder sits entirely above spot and the resolved downside target is
`>= close`. In that case the downside is **re-anchored to the nearest structurally
valid level strictly below spot**, in priority order:

1. nearest liquidation level strictly below spot (`reanchor_liquidation`),
2. ERP re-entry floor, if strictly below spot (`reanchor_erp_floor`),
3. 200-day SMA, if strictly below spot (`reanchor_sma200`),
4. margin-call zone (`reanchor_margin_call`),
5. deterministic −1.25% fallback only if no structural level is below spot
   (`reanchor_fallback_pct`; catastrophic >15% break).

`fib_618` is intentionally **not** a fallback: once price is below the whole leg,
the Fib retracement ladder is no longer a valid downside map. Any re-anchor writes a
`precompute_warning` to `market_data.precompute_warnings` so `analysis_context.json`
stays traceable. The MC downside cascade level is derived from liquidation zones
below the (re-anchored) target so cascades also stay below spot.

**Not yet implemented (deferred, Option B):** formal down-leg re-anchoring — treating
a fully-retraced-and-broken leg as a new governing down-leg with its own swing
high/low and Fib construction. That is a framework-methodology decision (the Daily
framework still describes Step 6 as Fib/leverage/support from the current swing high)
and should be specified before implementation.

---

## Schema changes

### `external_context.json` (input) — **strict breaking change**

The schema accepts **only** these three fields. Any additional key causes Pydantic
validation to fail (`extra="forbid"`) and the run aborts before precompute.

```json
{
  "date": "YYYY-MM-DD",
  "forward_eps": 354.0,
  "trailing_eps": 220.0
}
```

| Removed field (legacy) | Where that data lives now |
|------------------------|---------------------------|
| `us10y` | yfinance `^TNX` in Step 0 precompute |
| `fear_greed_index` | Chart 08 (CNN Fear & Greed) |
| `fear_greed_components` | Charts 09–15 (sentiment/breadth/credit) |

**Tester action:** Before running, strip all keys other than `date`, `forward_eps`,
and `trailing_eps` from every `data/runs/*/external_context.json`. A file that
still contains `us10y` or `fear_greed_*` is not a warning — it is a hard failure.

`forward_eps` and `trailing_eps` may be `null` (run continues with valuation
warnings); unknown top-level fields may not.

### `analysis_context.json` (engine-written)

Sections: `market_data`, `valuation`, `structure`, `monte_carlo` (with `threshold_evaluation` for 65/70/75).

Does **not** contain `structural_bias`, `effective_threshold`, or `meets_threshold` — those live on `DailyState` after Pass 1.

### `DailyState` (output)

- Added: `structural_bias`, expanded `monte_carlo` (`MonteCarloDetail`)
- `decision_matrix`: `{ rows: [{ signal_layer, current_reading, signal }] }` (18 rows)
- Removed: `schk_close`, `instrument_symbol` from manifest
- `framework_version`: `daily-2026-06`

### `DailyManifest`

- Removed `instrument_symbol`
- `close` is reference-only for drift validation

---

## Artifact locations and authority

Testers should use this table when deciding which path to inspect or why a file
might appear in two places.

| File | Primary location | Also written to | Authoritative for |
|------|------------------|-----------------|-------------------|
| `analysis_context.json` | `data/runs/<date>/` | `output/<date>/` (mirror at end of `run`) | **Run dir** while preparing or re-running; **output** for auditing a completed run bundle |
| `market_history.json` | `data/runs/<date>/` | — | yfinance cache for that run only |
| `external_context.json` | `data/runs/<date>/` | — | Manual EPS inputs (user-edited) |
| `*-state.json` / `*-analysis.md` | `output/<date>/` | `memory/` (mirror) | **output** + **memory** for viewer/history |

### `analysis_context.json` — two paths, one payload

1. **Step 0** (`run_precompute`) writes `data/runs/<date>/analysis_context.json`
   first. This is the working copy alongside charts, manifest, and EPS inputs.
2. **`setup-run --precompute`** writes only the run-dir copy (no `output/` yet).
3. **Full `run`** re-writes the same object to the run dir and **mirrors** an
   identical copy to `output/<date>/analysis_context.json` when persisting artifacts.

After a successful `run`, both files should be byte-identical. If they differ,
treat **`data/runs/<date>/analysis_context.json`** as the live input-side copy
and **`output/<date>/analysis_context.json`** as the archived reproducibility
snapshot for that execution.

**Not a test failure:** seeing `analysis_context.json` under both directories
after `run`. **Is a test failure:** `analysis_context.json` missing from
`data/runs/<date>/` after precompute, or missing from `output/<date>/` after a
completed `run`.

---

## Pipeline details

### Step 0 — `run_precompute()`

1. Load/fetch `^GSPC` (~300d), `^VIX` (~60d), `^TNX` (~25 sessions)
2. Compute structure → MC targets → GBM
3. Write `data/runs/<date>/analysis_context.json` (see [Artifact locations](#artifact-locations-and-authority))
4. On full `run`, mirror the same file to `output/<date>/analysis_context.json`
5. Warn on `as_of_date != run_date` or manifest close drift
6. On yfinance failure: raise `InputError` with cache hint

### Pass 1

- System role: `framework/SPX-Claude-Role-Block.md` + hard constraints
- Framework: `framework/SPX-Daily-Analysis-Framework.md`
- Injects full `analysis_context` JSON (immutable)
- Optional memory when `SPX_INCLUDE_MEMORY=true` (narrative only)

### Post-Pass 1 enforcement (`apply_precomputed_fields`)

Overwrites from `analysis_context`:

- `spx_close`
- All `monte_carlo` fields (threshold from `structural_bias` → 65/70/75)
- Decision matrix rows: Structural Bias, Monte Carlo Threshold, Volatility Input, Drift Input, Rally Exhaustion Score, Monte Carlo Edge, ERP State and Trend

Audit trail written to:

- `run_log.json` → `precompute_enforcement`
- `validation_report.json` → `precompute_enforcement` issues
- `state_validation` warnings appended

### Pass 2

- Receives enforced `DailyState` + `analysis_context`
- MC and matrix numerics treated as immutable

---

## CLI

| Command | Purpose |
|---------|---------|
| `setup-run --date YYYY-MM-DD` | Scaffold run dir, EPS template, placeholder manifest/chart |
| `setup-run --precompute` | Step 0 preview (requires EPS + manifest) |
| `run --date YYYY-MM-DD` | Full pipeline |
| `validate --date YYYY-MM-DD` | Re-check outputs |
| `rebuild-summary` | Rolling memory markdown |

---

## Configuration (`.env`)

| Variable | Default | Notes |
|----------|---------|-------|
| `SPX_INCLUDE_MEMORY` | `false` | Prior runs optional in prompt only |
| `SPX_FRAMEWORK_PATH` | `framework/SPX-Daily-Analysis-Framework.md` | |
| `SPX_ROLE_PATH` | `framework/SPX-Claude-Role-Block.md` | |
| `SPX_TICKER` / `SPX_VIX_TICKER` / `SPX_TREASURY_TICKER` | `^GSPC` / `^VIX` / `^TNX` | |

---

## Web viewer (Phase 2)

Updated for SPX-only schema:

- `web/lib/types.ts` — `DailyState`, 18-row `DecisionMatrix`, `effective_threshold: 65 | 70 | 75`
- `decision-matrix.tsx` — renders structured rows (not parsed markdown tables)
- `signal-grid.tsx` — uses `monte_carlo.prob_up_first_adjusted`
- `run-header.tsx` — structural bias, SPX branding

---

## Tests

| Area | Files |
|------|-------|
| Structure DL-3 | `tests/test_structure.py`, `tests/fixtures/structure/*.json`, `tests/test_structure_fixtures.py` |
| Monte Carlo | `tests/test_monte_carlo.py` (reproducibility, adjusted prob semantics) |
| Valuation | `tests/test_valuation.py` |
| Precompute integration | `tests/test_precompute_integration.py` (mocked yfinance series) |
| State enforcement | `tests/test_state_enforcement.py` |
| Engine E2E | `tests/test_engine.py` (mocked Anthropic + precompute; enforcement + prompt audit) |
| Validation | `tests/test_validation.py`, `tests/test_validation_matrix.py` |
| Scaffold | `tests/test_scaffold.py` |
| Market data warnings | `tests/test_market_data.py` |
| Web API | `tests/test_web_api.py` |

---

## Breaking changes

1. **`external_context.json` (strict)** — Only `date`, `forward_eps`, `trailing_eps`
   are allowed. Legacy keys (`us10y`, `fear_greed_index`, `fear_greed_components`,
   etc.) cause a **hard validation error**, not a warning. See
   [external_context.json](#external_contextjson-input--strict-breaking-change).
2. **Old `memory/daily_states/*.json`** — incompatible schema; skipped when unreadable
3. **Decision matrix shape** — `{ rows: [...] }` not `{ headers, cells }`
4. **Runtime frameworks** — V1/V3 SCHK files remain in repo but are **not loaded**

### One-time migration

```bash
# Archive legacy memory (optional)
mv memory memory-archive-v1

# Fresh run after updating EPS-only external_context.json
python -m src.cli setup-run --date 2026-06-12
python -m src.cli run --date 2026-06-12
python -m src.cli rebuild-summary --days 6
```

---

## Explicit non-goals (unchanged)

- Allocation sizing, trim waves, GTC orders, defensive tripwire
- SCHK instrument logic
- Loading V1/V3 methodology at runtime
- Programmatic chart OCR (LLM vision remains the chart reader)

---

## Known limitations

| Item | Notes |
|------|-------|
| DL-3 rule 2 (liquidation near fib) | −10% zone is usually below `fib_382`; rule rarely fires per locked spec |
| Down-leg re-anchoring (Option B) | Deferred; straddle guard re-anchors only the downside target, not the full leg/Fib construction |
| Perplexity migration | `migrate_perplexity.py` bypasses precompute; legacy import only |
| First run offline | Requires network or cached `market_history.json` |
| Qualitative matrix rows | Trend, breadth, credit, etc. remain LLM-authored from charts |

---

## File change index

### Core engine

- `src/config.py` — daily framework paths, `SPX_INCLUDE_MEMORY`, ticker settings
- `src/schemas.py` — `AnalysisContext`, slim `ExternalContext`, `MonteCarloDetail`, 18-row matrix
- `src/prompts.py` — Daily workflow, pre-step, MC copy-from-precompute instructions
- `src/validation.py` — Daily steps, matrix row validation
- `src/analysis_engine.py` — Step 0 + enforcement + audit
- `src/files.py` — `load_role()`, `scaffold_run_dir()`, `ANALYSIS_CONTEXT_FILENAME`
- `src/external_data.py` — EPS-only loader
- `src/memory.py` — `vix_regime` in rollup (not numeric VIX)
- `src/cli.py` — `setup-run`, SPX branding
- `src/migrate_perplexity.py` — updated imports (legacy path)
- `src/anthropic_client.py` — `analysis_context_included` in request snapshot

### New

- `src/market_data.py`, `src/structure.py`, `src/valuation.py`, `src/monte_carlo.py`, `src/precompute.py`, `src/state_enforcement.py`

### Data / config

- `data/runs/*/manifest.json` — removed `instrument_symbol`
- `data/runs/*/external_context.json` — EPS-only samples
- `.env.example`, `README.md`, `pyproject.toml`, `requirements.txt` — yfinance, numpy, pandas

### Web

- `web/lib/types.ts`, `web/components/decision-matrix.tsx`, `signal-grid.tsx`, `run-header.tsx`, `report-view.tsx`, `web/app/layout.tsx`

### Tests / fixtures

- `tests/fixtures/structure/` — `leg_uptrend.json`, `leg_extended.json`, `leg_shallow_pullback.json`
- Full test suite under `tests/` (62 tests)

---

## Review tightening pass (included in PR-1)

| Fix | Implementation |
|-----|----------------|
| Enforce MC/close after Pass 1 | `apply_precomputed_fields()` |
| Sync matrix precompute rows | `sync_matrix_precomputed_rows()` |
| Enforcement audit trail | `validation_report.json`, `run_log.json`, `state_validation` |
| `as_of_date` mismatch warning | `build_market_data_context()` |
| Frozen structure fixtures | `tests/fixtures/structure/` |
| Precompute integration test | `tests/test_precompute_integration.py` |
| `setup-run` manifest stub | `scaffold_run_dir()` |
| Memory migration docs | README + this document |
| MC probability semantics | `monte_carlo.py` docstring + test |
| Cascade upside target | `next_resistance_above()` in structure |
| `effective_threshold` typing | `Literal[65, 70, 75]` in Python + TypeScript |

---

## Verification

```bash
cd spx-analyst
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -e ".[dev]"
pytest
```

Live run (requires `ANTHROPIC_API_KEY` and chart pack):

```bash
python -m src.cli run --date 2026-06-12
```

Expected artifacts after a **completed** `run`:

**`data/runs/2026-06-12/`** (input-side working copy)

- `analysis_context.json` — Step 0 precompute; must exist before Pass 1

**`output/2026-06-12/`** (reproducibility bundle)

- `2026-06-12-state.json` — enforced `monte_carlo`, synced matrix rows
- `2026-06-12-analysis.md`
- `analysis_context.json` — mirror of the run-dir file (should match byte-for-byte)
- `validation_report.json` — includes `precompute_enforcement` section
- `run_log.json` — `precompute_enforcement.applied: true`

See [Artifact locations and authority](#artifact-locations-and-authority) if a
test checks one path but not the other.
