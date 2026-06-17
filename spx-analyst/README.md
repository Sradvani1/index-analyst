# SPX Daily Analysis Engine

See [docs/PR-1-spx-daily-framework-migration.md](docs/PR-1-spx-daily-framework-migration.md) for the full PR-1 implementation record (architecture, schema changes, migration guide).

A headless, file-driven analysis engine for the S&P 500 daily tactical framework.
It ingests a daily chart pack, precomputes numeric context (yfinance + manual EPS),
runs a two-pass Claude pipeline, and emits a markdown report plus structured JSON
state for optional day-over-day memory.

## How it works

Each daily run has three stages:

1. **Step 0 — Python precompute.** Fetches `^GSPC` (300d), `^VIX` (60d), and `^TNX`
   (25 sessions) via yfinance, combines manual `forward_eps` / `trailing_eps` from
   `external_context.json`, and writes `analysis_context.json` (ERP, structure,
   Monte Carlo simulation, threshold evaluation).
2. **Pass 1 — structured state.** Charts, external context, precomputed
   `analysis_context`, framework, and optional memory are sent in one multimodal
   request. The model emits a schema-valid `DailyState` JSON object. Monte Carlo
   probabilities are copied from precompute — not recalculated.
3. **Pass 2 — markdown report.** The validated state scaffolds a full report that
   follows the Daily 7-Step Workflow and ends with the 18-row Updated Decision Matrix.

Canonical outputs are mirrored into `memory/` when enabled for narrative continuity.

## Install

```bash
cd spx-analyst
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then fill in API keys
```

## Configuration

Set these in `.env` (see `.env.example`):

- `ANTHROPIC_API_KEY` — required for live runs.
- `SPX_INCLUDE_MEMORY` — default `false`; prior runs are optional narrative context only.

Manual inputs per run (`external_context.json`):

- `forward_eps` — S&P 500 consensus forward EPS.
- `trailing_eps` — trailing EPS for trailing P/E.

**Breaking change:** the schema accepts only `date`, `forward_eps`, and
`trailing_eps`. Any other key (e.g. legacy `us10y`, `fear_greed_index`) causes a
**hard validation error** before the run starts. Remove those fields from existing
run folders before testing.

All other qualitative indicators (VIX regime, Fear & Greed, breadth, etc.) come from
charts in the two-pass LLM pipeline.

## Usage

```bash
# Scaffold a run directory (optional precompute preview)
python -m src.cli setup-run --date 2026-06-12

# Run a full daily analysis (charts in data/runs/<date>/)
python -m src.cli run --date 2026-06-12

# Use a custom run directory
python -m src.cli run --date 2026-06-12 --input-dir data/runs/2026-06-12

# Re-validate previously written outputs
python -m src.cli validate --date 2026-06-12

# Rebuild the rolling memory summary
python -m src.cli rebuild-summary --days 5
```

## Run directory layout

```text
data/runs/2026-06-12/
  charts/01_spx_daily.png ... 15_positioning.png
  manifest.json
  external_context.json   # EPS only — date, forward_eps, trailing_eps (strict schema)
  analysis_context.json   # Step 0 precompute (working copy; authoritative during run)
  market_history.json     # yfinance cache (optional after first fetch)
```

`manifest.json` lists charts with unique, contiguous `order` values; the engine
sends images to the model in that order. `manifest.close` is validation-only —
yfinance SPX close is the numeric source of truth.

## Outputs

```text
output/2026-06-12/
  2026-06-12-analysis.md     # human-readable report
  2026-06-12-state.json      # canonical machine state
  analysis_context.json      # mirror of data/runs/.../analysis_context.json
  request_snapshot.json      # reproducibility metadata (no secrets)
  response_raw.json          # raw provider responses
  run_log.json               # timings, warnings, model
  validation_report.json     # schema + report structure checks
```

After a successful `run`, `analysis_context.json` exists in **both** the run
directory and `output/`. They should be identical. Use the run-dir copy while
preparing inputs; use the `output/` copy when auditing a completed run. Details in
[PR-1 doc — Artifact locations](docs/PR-1-spx-daily-framework-migration.md#artifact-locations-and-authority).

## Testing

```bash
pip install -e ".[dev]"
pytest
```

Unit and engine tests mock the provider and run offline. Precompute unit tests use
fixed fixtures; live yfinance is not required for CI.

## Phase 2 web viewer (local)

Browse the canonical report archive in `memory/` via a FastAPI backend and
Next.js frontend. Start both in separate terminals:

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
framework/   SPX-Daily-Analysis-Framework.md + SPX-Claude-Role-Block.md
data/runs/   dated input folders (charts + manifest + external context)
memory/      rolling state history + report archive (optional)
output/      per-run artifacts
src/         engine modules (includes src/web/ FastAPI viewer)
web/         Next.js Phase 2 frontend
tests/       pytest suite
```

Legacy V1/V3 methodology files remain in `framework/` for reference but are not
loaded at runtime.

## Memory migration (one-time)

Pre-migration `memory/daily_states/*.json` files use the old V1/SCHK schema and
are **incompatible** with the daily framework engine. On upgrade:

1. Archive or delete `memory/daily_states/` and `memory/daily_reports/` if you
   do not need historical viewer access.
2. Run fresh analyses; new states use `framework_version: daily-2026-06`.
3. `load_recent_states` silently skips unreadable legacy files when
   `SPX_INCLUDE_MEMORY=true`.
4. Rebuild the rolling summary after your first successful new-format run:

```bash
python -m src.cli rebuild-summary --days 6
```

Update each run's `external_context.json` to EPS-only (`date`, `forward_eps`,
`trailing_eps`) before running. **Do not** leave legacy keys — they are rejected,
not ignored.

## Legacy Perplexity migration

`src/migrate_perplexity.py` imports historical Perplexity markdown into the old
two-pass shape. It does **not** run Step 0 precompute or `apply_precomputed_fields`.
Use it only for one-off archive imports; daily runs should use `python -m src.cli run`.
