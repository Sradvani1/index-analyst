# SPX Daily Analysis Engine

A headless, file-driven analysis engine for the S&P 500 daily tactical framework.
It ingests a daily chart pack, precomputes numeric context (yfinance + master EPS history),
runs a two-pass Claude pipeline with deterministic post-Pass-1 enforcement, and emits
a markdown report plus structured JSON state.

**Framework version:** `daily-2026-06`

**Implementation records:**

- [PR-1: Daily framework migration](docs/PR-1-spx-daily-framework-migration.md) — Step 0 precompute, schema rebuild, yfinance authority
- [PR-2: Two-pass prompt overhaul](docs/PR-2-spx-two-pass-prompt-overhaul.md) — prompt/enforcement fidelity, ERP fix, Pass 2 validation gate, prompt caching
- [PR-3: Memory rollup overhaul](docs/PR-3-memory-rollup-overhaul.md) — categorical posture snapshot, unconditional rolling rebuild, load observability
- [PR-4: Pass 2 image optimization](docs/PR-4-pass2-image-optimization.md) — dynamic chart selection, Pass 2 downscaling, attached vs reference-only authority
- [PR-4.1: Pass 2 stub-response fix](docs/PR-4.1-pass2-stub-response-fix.md) — `claude-opus-4-8` tools-free retry when Pass 2 returns a preamble stub
- [PR-5: EPS master history](docs/PR-5-eps-master-history.md) — single `eps_history.json` source; no per-run EPS files
- [PR-6: Pass 1 schema discipline](docs/PR-6-pass1-schema-discipline.md) — signals contract prompt + tool schema descriptions, allowlisted drift coalescer, `pass1_schema_status` audit trail
- [PR-7: Pass 2 investor report template](docs/PR-7-pass2-investor-report-template.md) — eight-section Pass 2 prose, Python assembly of nine visible parts, strict heading validation
- [PR-8: Pass 1 repair hardening](docs/PR-8-pass1-repair-hardening.md) — structural coercion (`what_changed_today`), extended signals drift rules, repair SLO observability

## How it works

Each daily run has five stages:

1. **Step 0 — Python precompute.** Fetches `^GSPC` (300d), `^VIX` (60d), and `^TNX`
   (25 sessions) via yfinance, resolves `forward_eps` / `trailing_eps` from
   `data/master/eps_history.json`, and writes `analysis_context.json` (ERP, structure,
   Monte Carlo simulation, threshold evaluation). When price has fully retraced the
   active swing leg, a **Monte Carlo straddle guard** re-anchors the downside target
   to the nearest valid level strictly below spot so simulation targets always straddle
   close (see PR-1 doc).
2. **Pass 1 — structured state.** The **full** chart pack (all manifest entries), resolved
   EPS inputs, precomputed `analysis_context`, framework, and optional prior posture snapshot
   are sent in one multimodal request at `SPX_IMAGE_MAX_DIMENSION` (default 1568). The model
   emits a `DailyState` JSON object via `emit_daily_state`, focusing on qualitative chart reads
   and `structural_bias`. The prompt and tool schema enforce a strict `signals` contract (no
   `*_detail`, `*_note`, or extra `*_zone` fields) and require `what_changed_today` as a
   3–5 item JSON array. Before validation, `state_normalize.coalesce_pass1_drift()` applies
   structural coercion (e.g. wrap a lone `what_changed_today` string as a one-element list)
   and **allowlisted** signals drift rules (e.g. `vix_regime_detail` → `vix_regime`, drop
   `*_zone` except `fear_greed_zone`, drop null/empty unknown keys). Unknown extras with
   substantive values fail closed and may trigger a one-shot repair fallback. Seven
   decision-matrix rows are `(engine-filled)` placeholders; the engine overwrites them next.
   See [PR-6](docs/PR-6-pass1-schema-discipline.md) and
   [PR-8](docs/PR-8-pass1-repair-hardening.md).
3. **Post-Pass-1 enforcement.** `state_enforcement.py` applies precomputed numerics
   (`spx_close`, Monte Carlo block, seven owned matrix rows) before Pass 2 runs.
4. **Pass 2 chart selection (PR-4).** `pass2_images.resolve_pass2_images()` runs on the
   post-enforcement state: protected conflict `chart_refs`, matrix-driven adds for
   non-neutral qualitative rows, then conservative redundancy pruning. See
   [PR-4](docs/PR-4-pass2-image-optimization.md).
5. **Pass 2 — markdown report.** Only **attached** charts are encoded (default max edge
   1092 when `SPX_PASS2_IMAGE_OPTIMIZATION=true`). The prompt lists reference-only charts
   by filename without sending their bytes. Pass 2 returns **eight investor-facing prose
   sections only** (no `#` preamble, no Decision Matrix). Python then assembles the
   published `{date}-analysis.md`: Header Snapshot, prose sections with injected fact
   blocks under Valuation / Monte Carlo / Tactical Levels, and the Updated Decision Matrix
   from enforced state. Raw Pass 2 output is stored as `response_raw.report_pass_prose`.
   Pass 2 is exposition-only: it must not contradict the validated state. When memory is
   enabled, the same optional prior posture snapshot is included (continuity only — not
   authoritative for today's numerics).

See [PR-7: Pass 2 investor report template](docs/PR-7-pass2-investor-report-template.md)
for the nine-vs-eight distinction, assembly module, validation gates, and
`cli validate` expectations on historical vs new reports.

Set `SPX_PASS2_IMAGE_OPTIMIZATION=false` to restore pre-PR-4 Pass 2 behavior (all charts,
full resolution, legacy manifest prompt block).

On every **successful** run, canonical state and report files are mirrored into
`memory/daily_states/` and `memory/daily_reports/` (used by the web viewer).
`rebuild_rolling_summary` refreshes `memory/rolling/` after every successful run.
`SPX_INCLUDE_MEMORY=true` gates **prompt injection** of the posture snapshot into
Pass 1/Pass 2 only — archival and rolling rebuild always run on success.

See [PR-3: Memory rollup overhaul](docs/PR-3-memory-rollup-overhaul.md) for the
categorical signal buckets, action normalization table, and watchlist rules.

See [PR-4: Pass 2 image optimization](docs/PR-4-pass2-image-optimization.md) for
selector rules, flag-off semantics, and `run_log` pass2 audit fields. Pass 2 stub handling:
[PR-4.1](docs/PR-4.1-pass2-stub-response-fix.md). Live token A/B: [PR-4-live-ab-results.md](docs/PR-4-live-ab-results.md).

See [PR-5: EPS master history](docs/PR-5-eps-master-history.md) for the append-only
`eps_history.json` workflow, `show-eps`, resolution rules, and `run_log.eps_resolution`.

See [PR-6: Pass 1 schema discipline](docs/PR-6-pass1-schema-discipline.md) for the
`signals` contract, allowlisted coalescer rules, `run_log.pass1_schema_status`, and
traceable `response_raw` payloads (`state_pass_original`, `state_pass_normalized`,
`repair_pass`).

See [PR-8: Pass 1 repair hardening](docs/PR-8-pass1-repair-hardening.md) for
`coalesce_pass1_drift`, extended drift rules (zone keys, framework-bleed denylist,
null/empty unknown drop), `normalize_audit.structural_coercions`, and repair-rate SLO
fields (`repair_avoided`, `what_changed_today_count`, `what_changed_today_count_warning`).

## Install

```bash
cd spx-analyst
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install -e ".[dev]"   # optional: editable install + pytest
cp .env.example .env      # then fill in API keys
```

## Configuration

Set these in `.env` (see `.env.example`):

| Variable | Default | Purpose |
|----------|---------|---------|
| `ANTHROPIC_API_KEY` | — | Required for live runs |
| `SPX_MODEL` | `claude-opus-4-20250514` | Claude model for both passes |
| `SPX_PROMPT_CACHE_ENABLED` | `true` | Reuse framework + tool schema across passes |
| `SPX_INCLUDE_MEMORY` | `false` | Inject prior posture snapshot into Pass 1/Pass 2 (rebuild always runs on success; rollup is categorical-only — no historical numerics) |
| `SPX_IMAGE_MAX_DIMENSION` | `1568` | Long-edge resize for Pass 1 chart images (and Pass 2 when optimization off) |
| `SPX_PASS2_IMAGE_OPTIMIZATION` | `true` | Dynamic Pass 2 chart selection + downscaling ([PR-4](docs/PR-4-pass2-image-optimization.md)) |
| `SPX_PASS2_IMAGE_MAX_DIMENSION` | `1092` | Long-edge resize for Pass 2 attached charts when optimization on (operator floor: 784) |
| `SPX_MAX_REPORT_CHARS` | `24000` | Report length validation limit |
| `SPX_MAX_OUTPUT_TOKENS` | `8000` | Max tokens per Claude response |
| `SPX_RECENT_STATE_COUNT` | `6` | Recent states loaded when memory is enabled |
| `SPX_EPS_HISTORY_PATH` | `data/master/eps_history.json` | Append-only forward/trailing EPS history ([PR-5](docs/PR-5-eps-master-history.md)) |

Path overrides (`SPX_FRAMEWORK_PATH`, `SPX_ROLE_PATH`, `SPX_DATA_DIR`, `SPX_EPS_HISTORY_PATH`,
`SPX_MEMORY_DIR`, `SPX_OUTPUT_DIR`) default to the package layout below.

EPS master history (`data/master/eps_history.json`):

- Append-only list of `{ effective_from, forward_eps, trailing_eps }` rows
- Resolved by run date: latest row where `effective_from <= run_date`
- Provenance recorded in `run_log.eps_resolution` on each completed run

See [PR-5](docs/PR-5-eps-master-history.md) for operator workflow and failure policy.

All qualitative indicators (VIX regime, Fear & Greed, breadth, etc.) come from
charts in the two-pass LLM pipeline.

## Usage

```bash
# Scaffold a run directory (placeholder manifest)
python -m src.cli setup-run --date 2026-06-12

# Append a row when consensus changes (never edit old rows)
# effective_from = date the new values apply; runs on/after that date pick this row
python -m src.cli show-eps --date 2026-06-10   # verify before run

# Optional: preview Step 0 precompute when EPS resolves
python -m src.cli setup-run --date 2026-06-12 --precompute

# Import 15 PNG screenshots from Images/<date>/ (repo root) into the run directory
python -m src.cli import-run --date 2026-06-24

# Optional: chain Step 0 precompute after import
python -m src.cli import-run --date 2026-06-24 --precompute

# Run a full daily analysis (use import-run instead of manual chart copy + manifest edit)
python -m src.cli run --date 2026-06-12

# Force fresh yfinance fetch during precompute
python -m src.cli run --date 2026-06-12 --force-fetch

# Use a custom run directory
python -m src.cli run --date 2026-06-12 --input-dir data/runs/2026-06-12

# Re-validate previously written outputs (investor-template reports post–PR-7;
# pre-migration workflow-heading reports will fail strict section validation)
python -m src.cli validate --date 2026-06-12

# Rebuild memory/rolling/recent_summary.md from archived states (also runs automatically after every successful run)
python -m src.cli rebuild-summary --days 6

# Phase 2 stub: load a day's context (interactive chat not yet implemented)
python -m src.cli chat --date 2026-06-12
```

The console entry point `spx-analyst` is also available after `pip install -e .`.

## Run directory layout

```text
data/runs/2026-06-12/
  charts/
    01_spx_intraday.png
    02_spx_5day.png
    03_spx_1month.png
    04_spx_3month.png
    05_spx_6month.png
    06_spx_1year.png
    07_spx_3year.png
    08_fear_greed_index.png
    09_fear_greed_momentum.png
    10_breadth_52wk_highs_lows.png
    11_breadth_mcclellan.png
    12_put_call_ratio.png
    13_vix_volatility.png
    14_safe_haven_demand.png
    15_junk_bond_spread.png
  manifest.json
  analysis_context.json   # Step 0 precompute (written during run)
  market_history.json     # yfinance cache (optional after first fetch)

data/master/
  eps_history.json        # sole EPS source — append rows when consensus changes
```

`setup-run` creates a **placeholder** 1-chart manifest. For daily production runs,
use `import-run` to copy the 15-chart pack from `Images/<date>/` at the repo root
and build a complete `manifest.json` (fetches SPX close from yfinance). Screenshot
files in intake order — alphabetical filename order maps to chart order 1–15; do not
rename out of capture sequence.

`manifest.json` lists charts with unique, contiguous `order` values; Pass 1 sends
images to the model in that order. Pass 2 sends a subset in the same manifest order
when optimization is enabled. `manifest.close` is validation-only — yfinance SPX close
is the numeric source of truth.

## Outputs

```text
output/2026-06-12/
  2026-06-12-analysis.md     # human-readable report
  2026-06-12-state.json      # canonical machine state (post-enforcement)
  analysis_context.json      # mirror of data/runs/.../analysis_context.json
  request_snapshot.json      # reproducibility metadata per pass (no secrets)
  response_raw.json          # raw provider responses; state_pass + report_pass; state_pass_original always; state_pass_normalized / repair_pass when applicable (PR-6)
  run_log.json               # timings, warnings, eps_resolution, pass1_schema_status (PR-6/PR-8), report_assembly (PR-7), model, precompute enforcement; pass2_* audit fields; memory_load when SPX_INCLUDE_MEMORY=true
  validation_report.json     # schema, report structure, enforcement audit

memory/daily_states/2026-06-12-state.json      # mirrored on successful run
memory/daily_reports/2026-06-12-analysis.md    # mirrored on successful run
memory/rolling/recent_summary.md               # posture snapshot rollup (rebuilt every successful run)
memory/rolling/recent_memory.json              # JSON mirror of states used in rollup
```

After a successful `run`, `analysis_context.json` exists in **both** the run
directory and `output/`. They should be identical. Use the run-dir copy while
preparing inputs; use the `output/` copy when auditing a completed run. Details in
[PR-1 — Artifact locations](docs/PR-1-spx-daily-framework-migration.md#artifact-locations-and-authority).

## Testing

```bash
pytest
```

Unit and engine tests mock the provider and run offline. Precompute unit tests use
fixed fixtures; live yfinance is not required for CI.

## Phase 2 web viewer (local)

Publication-style archive and report reader over canonical `memory/` artifacts. The
viewer is **read-only exposition**: it does not recompute analytical outputs or
synthesize market interpretations from prose. Structured UI (rails, chips, matrix)
uses `DailyState` / `RunSummary` fields only; the assembled markdown report is
rendered as served (see [PR-7](docs/PR-7-pass2-investor-report-template.md)).

### Routes

| Route | Purpose |
|-------|---------|
| `/` | Redirects to the newest archived run |
| `/archive` | Full archive grid (optional; primary navigation is the left sidebar) |
| `/runs/{date}` | Report header, signal grid, and section tabs |
| `/about` | Static product note |

API (FastAPI, port 8000): `GET /api/health`, `GET /api/runs`, `GET /api/runs/{date}`.

### Prerequisites — seed `memory/`

The UI requires at least one valid **state + report pair** in `memory/`. Successful
`run` commands populate the archive automatically. For local UI work without a full
engine run:

```bash
cd spx-analyst && source .venv/bin/activate
python -c "
from pathlib import Path
import json
from tests.conftest import SAMPLE_STATE
from tests.fixtures.investor_report import assembled_report_for_state
from src.schemas import DailyState

memory = Path('memory')
(memory / 'daily_states').mkdir(parents=True, exist_ok=True)
(memory / 'daily_reports').mkdir(parents=True, exist_ok=True)

for date in ('2026-06-12', '2026-06-11'):
    data = dict(SAMPLE_STATE)
    data['date'] = date
    state = DailyState.model_validate(data)
    (memory / 'daily_states' / f'{date}-state.json').write_text(
        json.dumps(state.model_dump(mode='json'), indent=2) + '\n')
    (memory / 'daily_reports' / f'{date}-analysis.md').write_text(
        assembled_report_for_state(state, date))
    print('Seeded', date)
"
```

**Do not** use `memory-archive/` Perplexity migration samples for the viewer — they
use a legacy `DailyState` shape and will be skipped by the API.

### Start locally

```bash
# Terminal 1 — API on :8000
cd spx-analyst && source .venv/bin/activate
uvicorn src.web.app:app --host 127.0.0.1 --port 8000

# Terminal 2 — UI on :3000
cd spx-analyst/web && npm install && npm run dev
```

Open http://localhost:3000. API docs: http://127.0.0.1:8000/docs.

### Troubleshooting

| Symptom | Likely cause |
|---------|----------------|
| Empty homepage / archive | No valid pairs in `memory/daily_states` + `memory/daily_reports` |
| Run missing from list | Orphan state or report; corrupt JSON; schema validation failure (check API logs) |
| Backend unavailable page | FastAPI not running on `:8000` or `API_BASE_URL` misconfigured |

## Project layout

```text
framework/   SPX-Daily-Analysis-Framework.md + SPX-Claude-Role-Block.md (runtime)
docs/        PR-1 through PR-8 implementation records; docs/archive/ for retired specs
data/
  master/    eps_history.json — sole EPS source (append-only)
  runs/      dated input folders (charts + manifest + precompute cache)
memory/      archived states/reports + rolling summary (rebuilt on every successful run)
output/      per-run artifacts
src/         engine modules (includes src/web/ FastAPI viewer)
web/         Next.js Phase 2 frontend
tests/       pytest suite
```

Retired SCHK methodology files and the original Phase 1 spec live in
`docs/archive/` for reference only. They are not loaded at runtime.

## Recent changes (summary)

| Change | Doc / commit |
|--------|----------------|
| Daily framework engine with yfinance precompute | PR-1 |
| Two-pass prompt overhaul, ERP enforcement fix, Pass 2 state consistency validation, cross-pass prompt caching | PR-2 |
| Memory rollup posture snapshot, categorical signals, rebuild decoupled from injection flag | PR-3 |
| Pass 2 dynamic chart selection, downscaling, attached vs reference-only prompt authority | PR-4 |
| Pass 2 stub-response retry for `claude-opus-4-8` | PR-4.1 |
| EPS master history — single `eps_history.json`, `show-eps`, no per-run EPS files | PR-5 |
| Pass 1 schema discipline — signals contract, allowlisted coalescer, repair observability | PR-6 |
| Pass 2 investor report template — eight prose sections, Python assembly, strict validation | PR-7 |
| Pass 1 repair hardening — `what_changed_today` coercion, extended drift rules, repair SLO | PR-8 |
| Monte Carlo target straddle guard (downside re-anchor when leg fully retraced) | PR-1 doc + `structure.reanchor_downside_for_straddle()` |

## Memory migration (one-time)

Pre-migration `memory/daily_states/*.json` files use the old V1/SCHK schema and
are **incompatible** with the daily framework engine. On upgrade:

1. Archive or delete `memory/daily_states/` and `memory/daily_reports/` if you
   do not need historical viewer access.
2. Run fresh analyses; new states use `framework_version: daily-2026-06`.
3. `load_recent_states` always skips unreadable legacy files during load; when
   `SPX_INCLUDE_MEMORY=true`, invalid skips are logged in `output/{date}/run_log.json`
   under `memory_load` and surfaced as run warnings.
4. Rolling summary rebuilds automatically after every successful run (or manually):

```bash
python -m src.cli rebuild-summary --days 6
```

Ensure `data/master/eps_history.json` has an entry with `effective_from <=` each run
date before running. See [PR-5](docs/PR-5-eps-master-history.md).

## Legacy Perplexity migration

Use `migrate-perplexity` to backfill valid `daily-2026-06` memory from historical
Perplexity markdown when chart packs are unavailable. The pipeline runs Step 0
precompute, Pass 1 with the same `coalesce_pass1_drift` pipeline and `pass1_schema_status`
audit as chart runs ([PR-6](docs/PR-6-pass1-schema-discipline.md),
[PR-8](docs/PR-8-pass1-repair-hardening.md)), `apply_precomputed_fields`,
PR-3 posture snapshots, and rebuilds rolling memory after each session. See
[docs/PR-3.1-perplexity-backfill.md](docs/PR-3.1-perplexity-backfill.md).

```bash
python -m src.cli migrate-perplexity \
  --history ../perplexity_analysis_history.md \
  --from 2026-06-01 \
  --to 2026-06-08
```

Older `perplexity-migration` states in `memory/` are invalid for PR-3 — archive them
before backfill. Daily chart-based runs use `python -m src.cli run`.
