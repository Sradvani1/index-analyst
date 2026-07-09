# PR-20: Prepare-run workflow

**Status:** Complete  
**Framework version:** `daily-2026-06`  
**Builds on:** [PR-19: Chart generation engine](PR-19-chart-generation-engine.md) · [PR-9: Daily run import](PR-9-daily-run-import.md)

## Summary

Adds a `prepare` CLI command that combines chart generation, manifest creation, market-data fetch, and Step 0 precompute into a single step. The daily workflow is now two commands:

```bash
python -m src.cli prepare --date YYYY-MM-DD     # generate charts + precompute
python -m src.cli run --date YYYY-MM-DD          # two-pass Claude analysis
```

The operator can review `prepare`'s output (printed summary + `analysis_context.json`) before committing to the LLM run.

## Motivation

The previous 4-command workflow (`generate-price-charts` → `fetch-fear-greed` → `import-run --precompute` → `run`) required jumping between two staging areas — `Images/<date>/` for chart output and `data/runs/<date>/` for the analysis pipeline. The `Images/` directory was a transient staging area that served no purpose once charts were generated programmatically.

## Changes

### New file: `src/prepare_run.py`

Orchestration module that runs five steps in sequence:

1. **Guard** — `_assert_can_prepare()` checks for existing manifests; errors unless `--force`
2. **Generate charts** — calls `price_charts.fetch_and_generate()` and `fear_greed.fetch_and_generate()` directly into `data/runs/<date>/charts/`
3. **Market data** — fetches SPX/VIX/TNX from yfinance, caches to `market_history.json`, extracts close for manifest
4. **Manifest** — writes canonical 15-chart `manifest.json`
5. **Precompute** — resolves EPS, runs `run_precompute` → `analysis_context.json`

Stale artifacts are purged when `--force` is used (removes `charts/`, manifest, analysis_context, market_history, fear_greed_raw.json).

Prints a readable summary after completion:

```
Prepared 2026-07-08
  SPX close:     5482.35
  Structure:     swing high 5530 (confirmed), swing low 5400 (confirmed)
                 fib 382=5450, fib 618=5430
  Valuation:     forward PE 22.1 (stable)
  Monte Carlo:   65% threshold NOT met (P_up_adj=42.0%), exhaustion: moderate
  15 charts   → data/runs/2026-07-08/charts/
```

### Modified: `src/cli.py`

- Added `prepare` command (`@app.command("prepare")`)
- `generate-price-charts` and `fetch-fear-greed` set to `hidden=True` — still callable but omitted from `--help`

### No changes to

- `run` command — unchanged, reads the same run directory structure
- `price_charts.py` — unchanged
- `fear_greed.py` — unchanged
- `import_run.py` — unchanged, remains for legacy manual intake
- `analysis_engine.py` — unchanged

## New workflow

```bash
# Primary path
python -m src.cli prepare --date 2026-07-08
python -m src.cli run --date 2026-07-08

# Backfill (date defaults to today)
python -m src.cli prepare
python -m src.cli run

# Regenerate an existing date
python -m src.cli prepare --date 2026-07-08 --force
```

The `Images/` staging directory is no longer part of the primary workflow. Standalone generators (`generate-price-charts`, `fetch-fear-greed`) still default to `Images/<date>/` for debug/backfill use.

## Tests

`tests/test_prepare_run.py` covers:

- Happy path: all 15 charts + manifest + precompute written correctly
- Guard: existing prepared run rejected without `--force`
- Force: overwrite clears stale artifacts and regenerates
- Market-data fetch failure
- Missing EPS history

```bash
pytest tests/test_prepare_run.py -q
```

## Files touched

| File | Change |
|------|--------|
| `src/prepare_run.py` | **New** — orchestration module |
| `src/cli.py` | Add `prepare` command; hide standalone generators |
| `tests/test_prepare_run.py` | **New** — tests |
| `README.md` | Two-step workflow usage; PR-19/PR-20 references |
