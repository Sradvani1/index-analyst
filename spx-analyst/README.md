# SPX / SCHK Direct API Analysis Engine (Phase 1)

A headless, file-driven analysis engine for the S&P 500 / SCHK tactical trading
workflow. It ingests a daily chart pack, loads the standing methodology, reads
user-supplied external market context, reasons over recent history, and emits a
human-readable markdown report plus a structured JSON state object for machine
memory.

## How it works

A daily run is a two-pass Claude pipeline:

1. **Pass 1 — structured state.** All chart images, external context, methodology,
   and recent state history are sent in one multimodal request. The model is
   forced (via tool use) to emit a schema-valid `DailyState` JSON object.
2. **Pass 2 — markdown report.** The validated state scaffolds a full report that
   follows the methodology's Daily 7-Step Workflow and ends with the Updated
   Decision Matrix.

Every run persists request snapshots, raw responses, validation reports, and run
logs for reproducibility, and mirrors the canonical `state.json` / `analysis.md`
into `memory/` for day-over-day continuity.

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

External market data is supplied manually — nothing is fetched over the network.
All context is read from each run's `external_context.json`:

- `us10y` — 10-year Treasury yield.
- `forward_eps` — S&P 500 consensus forward EPS (for the market Forward P/E).
- `fear_greed_index` — overall index as `{ "value", "reading" }`.
- `fear_greed_components` — the seven CNN sub-indicators, each as
  `{ "value", "reading" }`: `market_momentum`, `stock_price_strength`,
  `stock_price_breadth`, `put_call_options`, `market_volatility` (value is the
  VIX), `safe_haven_demand`, `junk_bond_demand` (value is the high-yield spread).

If the file is missing, the engine writes a blank template for you to fill in,
and any field left `null` carries through without aborting the run.

## Usage

```bash
# Run a full daily analysis (charts in data/runs/<date>/)
python -m src.cli run --date 2026-06-12

# Use a custom run directory
python -m src.cli run --date 2026-06-12 --input-dir data/runs/2026-06-12

# Re-validate previously written outputs
python -m src.cli validate --date 2026-06-12

# Rebuild the rolling memory summary
python -m src.cli rebuild-summary --days 5

# Phase 2 stub: load a day's chat context
python -m src.cli chat --date 2026-06-12
```

## Run directory layout

```text
data/runs/2026-06-12/
  charts/01_spx_daily.png ... 15_positioning.png
  manifest.json
  external_context.json   # auto-generated if missing
```

`manifest.json` lists charts with unique, contiguous `order` values; the engine
sends images to the model in that order.

## Outputs

```text
output/2026-06-12/
  2026-06-12-analysis.md     # human-readable report
  2026-06-12-state.json      # canonical machine state
  request_snapshot.json      # reproducibility metadata (no secrets)
  response_raw.json          # raw provider responses
  run_log.json               # timings, warnings, model
  validation_report.json     # schema + report structure checks
```

## Testing

```bash
pip install -e ".[dev]"
pytest
```

Unit and engine tests mock the provider and run offline. Tests marked `live`
(none required for CI) would call real APIs.

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
framework/   methodology markdown (immutable runtime input)
data/runs/   dated input folders (charts + manifest + external context)
memory/      rolling state history + report archive
output/      per-run artifacts
src/         engine modules (includes src/web/ FastAPI viewer)
web/         Next.js Phase 2 frontend
tests/       pytest suite
```

Phase 2 reuses Phase 1 file contracts unchanged; `chat_context.py` /
`chat_service.py` define the read-only retrieval interface for a future chat layer.
