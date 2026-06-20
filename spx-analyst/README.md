# SPX Daily Analysis Engine

A headless, file-driven analysis engine for the S&P 500 daily tactical framework.
It ingests a daily chart pack, precomputes numeric context (yfinance + manual EPS),
runs a two-pass Claude pipeline with deterministic post-Pass-1 enforcement, and emits
a markdown report plus structured JSON state.

**Framework version:** `daily-2026-06`

**Implementation records:**

- [PR-1: Daily framework migration](docs/PR-1-spx-daily-framework-migration.md) — Step 0 precompute, schema rebuild, yfinance authority
- [PR-2: Two-pass prompt overhaul](docs/PR-2-spx-two-pass-prompt-overhaul.md) — prompt/enforcement fidelity, ERP fix, Pass 2 validation gate, prompt caching
- [PR-3: Memory rollup overhaul](docs/PR-3-memory-rollup-overhaul.md) — categorical posture snapshot, unconditional rolling rebuild, load observability

## How it works

Each daily run has four stages:

1. **Step 0 — Python precompute.** Fetches `^GSPC` (300d), `^VIX` (60d), and `^TNX`
   (25 sessions) via yfinance, combines manual `forward_eps` / `trailing_eps` from
   `external_context.json`, and writes `analysis_context.json` (ERP, structure,
   Monte Carlo simulation, threshold evaluation). When price has fully retraced the
   active swing leg, a **Monte Carlo straddle guard** re-anchors the downside target
   to the nearest valid level strictly below spot so simulation targets always straddle
   close (see PR-1 doc).
2. **Pass 1 — structured state.** Charts, external context, precomputed
   `analysis_context`, framework, and optional prior posture snapshot are sent in one
   multimodal request. The model emits a schema-valid `DailyState` JSON object,
   focusing on qualitative chart reads and `structural_bias`. Seven decision-matrix
   rows are `(engine-filled)` placeholders; the engine overwrites them next.
3. **Post-Pass-1 enforcement.** `state_enforcement.py` applies precomputed numerics
   (`spx_close`, Monte Carlo block, seven owned matrix rows) before Pass 2 runs.
4. **Pass 2 — markdown report.** The enforced state scaffolds a full report that
   follows the Daily 7-Step Workflow, includes Evidence Reconciliation for listed
   divergences, and ends with the 18-row Updated Decision Matrix. Pass 2 is
   exposition-only: it must not contradict the validated state. When memory is
   enabled, the same optional prior posture snapshot is included (continuity only —
   not authoritative for today's numerics).

On every **successful** run, canonical state and report files are mirrored into
`memory/daily_states/` and `memory/daily_reports/` (used by the web viewer).
`rebuild_rolling_summary` refreshes `memory/rolling/` after every successful run.
`SPX_INCLUDE_MEMORY=true` gates **prompt injection** of the posture snapshot into
Pass 1/Pass 2 only — archival and rolling rebuild always run on success.

See [PR-3: Memory rollup overhaul](docs/PR-3-memory-rollup-overhaul.md) for the
categorical signal buckets, action normalization table, and watchlist rules.

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
| `SPX_IMAGE_MAX_DIMENSION` | `1568` | Long-edge resize for chart images (both passes) |
| `SPX_MAX_REPORT_CHARS` | `24000` | Report length validation limit |
| `SPX_MAX_OUTPUT_TOKENS` | `8000` | Max tokens per Claude response |
| `SPX_RECENT_STATE_COUNT` | `6` | Recent states loaded when memory is enabled |

Path overrides (`SPX_FRAMEWORK_PATH`, `SPX_ROLE_PATH`, `SPX_DATA_DIR`, `SPX_MEMORY_DIR`,
`SPX_OUTPUT_DIR`) default to the package layout below.

Manual inputs per run (`external_context.json`):

- `forward_eps` — S&P 500 consensus forward EPS
- `trailing_eps` — trailing EPS for trailing P/E

**Breaking change:** the schema accepts only `date`, `forward_eps`, and
`trailing_eps`. Any other key (e.g. legacy `us10y`, `fear_greed_index`) causes a
**hard validation error** before the run starts. Remove those fields from existing
run folders before testing.

All other qualitative indicators (VIX regime, Fear & Greed, breadth, etc.) come from
charts in the two-pass LLM pipeline.

## Usage

```bash
# Scaffold a run directory (placeholder manifest + external_context template)
python -m src.cli setup-run --date 2026-06-12

# Optional: preview Step 0 precompute after EPS is set
python -m src.cli setup-run --date 2026-06-12 --precompute

# Run a full daily analysis (replace placeholder charts with the 15-chart pack first)
python -m src.cli run --date 2026-06-12

# Force fresh yfinance fetch during precompute
python -m src.cli run --date 2026-06-12 --force-fetch

# Use a custom run directory
python -m src.cli run --date 2026-06-12 --input-dir data/runs/2026-06-12

# Re-validate previously written outputs
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
  external_context.json   # EPS only — date, forward_eps, trailing_eps (strict schema)
  analysis_context.json   # Step 0 precompute (written during run)
  market_history.json     # yfinance cache (optional after first fetch)
```

`setup-run` creates a **placeholder** 1-chart manifest. Replace it with the full
15-chart pack and a complete `manifest.json` before running analysis.

`manifest.json` lists charts with unique, contiguous `order` values; the engine
sends images to the model in that order. `manifest.close` is validation-only —
yfinance SPX close is the numeric source of truth.

## Outputs

```text
output/2026-06-12/
  2026-06-12-analysis.md     # human-readable report
  2026-06-12-state.json      # canonical machine state (post-enforcement)
  analysis_context.json      # mirror of data/runs/.../analysis_context.json
  request_snapshot.json      # reproducibility metadata per pass (no secrets)
  response_raw.json          # raw provider responses (state_pass + report_pass)
  run_log.json               # timings, warnings, model, precompute enforcement; memory_load when SPX_INCLUDE_MEMORY=true
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

Browse archived runs in `memory/` via a FastAPI backend and Next.js frontend.
Successful `run` commands populate the archive automatically. Start both in separate
terminals:

```bash
# Terminal 1 — API on :8000
cd spx-analyst && source .venv/bin/activate
uvicorn src.web.app:app --host 127.0.0.1 --port 8000

# Terminal 2 — UI on :3000
cd spx-analyst/web && npm install && npm run dev
```

Open http://localhost:3000. API docs: http://127.0.0.1:8000/docs.

## Project layout

```text
framework/   SPX-Daily-Analysis-Framework.md + SPX-Claude-Role-Block.md (runtime)
docs/        PR-1, PR-2, and PR-3 implementation records; docs/archive/ for retired specs
data/runs/   dated input folders (charts + manifest + external context)
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
| Monte Carlo target straddle guard (downside re-anchor when leg fully retraced) | PR-1 doc + `structure.reanchor_downside_for_straddle()` |

**Planned (not yet implemented):** Pass 2 dynamic chart selection and downscaling to
reduce image token cost on the report pass.

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

Update each run's `external_context.json` to EPS-only (`date`, `forward_eps`,
`trailing_eps`) before running. **Do not** leave legacy keys — they are rejected,
not ignored.

## Legacy Perplexity migration

`src/migrate_perplexity.py` imports historical Perplexity markdown into engine
artifacts. It does **not** run Step 0 precompute or `apply_precomputed_fields`.
Use it only for one-off archive imports; daily runs should use `python -m src.cli run`.
