# PR-9: Daily run import (`import-run`)

**Status:** Complete  
**Builds on:** [PR-1](PR-1-spx-daily-framework-migration.md) · [PR-5](PR-5-eps-master-history.md)

## Summary

Adds `import-run`, a CLI command that ingests 15 raw PNG screenshots from `Images/<date>/` at the repo root, copies them into `data/runs/<date>/charts/` under canonical filenames, fetches SPX close from yfinance, and writes a complete `manifest.json`. This replaces the manual daily workflow of renaming charts and cloning a prior manifest.

`setup-run` remains for placeholder scaffolding and backfill paths; `import-run` is the production operator path once screenshots exist.

## Problem

Before PR-9, starting a daily run required:

1. `setup-run` (placeholder manifest + gray PNG)
2. Manually copy/rename 15 screenshots into `charts/`
3. Clone and edit a prior `manifest.json` (`date`, `close`, 15 chart entries)

`manifest.close` was typed by hand. `market_history.json` was not written until precompute or `run`.

## Solution

```text
Images/<date>/          import-run              data/runs/<date>/
  IMG_1218.png     →    sort + map 1–15    →    charts/01_spx_intraday.png …
  …                     yfinance close           manifest.json
                        cache history            market_history.json
```

### Domain boundaries

| Zone | Role |
|------|------|
| `Images/<date>/` | Intake staging — raw screenshots, any filenames |
| `data/runs/<date>/charts/` | Canonical run input (`01_…` through `15_…`) |
| `manifest.close` | Validation / drift warning only ([PR-1](PR-1-spx-daily-framework-migration.md)) |
| `analysis_context.json` | Step 0 authority — written by precompute/run only |

### Chart pack SSoT

[`src/chart_pack.py`](../src/chart_pack.py) defines the canonical 15-chart pack (`CHART_PACK`, `build_manifest`). Labels match production manifests (verified against `2026-06-23`).

Intake mapping: sort non-hidden `*.png` files alphabetically; index `i` → chart `i+1`. iPhone `IMG_*` sequences work when captured in order (gaps in numbering are fine).

## CLI

```bash
# Default: ../Images/<date>/ → data/runs/<date>/
python -m src.cli import-run --date 2026-06-24

python -m src.cli import-run --date 2026-06-24 --images-dir /path/to/Images/2026-06-24
python -m src.cli import-run --date 2026-06-24 --force
python -m src.cli import-run --date 2026-06-24 --close 7365.46
python -m src.cli import-run --date 2026-06-24 --precompute
```

| Flag | Behavior |
|------|----------|
| `--images-dir` | Override intake folder (default: repo-root `Images/<date>/`) |
| `--input-dir` | Override run directory (default: `data/runs/<date>/`) |
| `--force` | Overwrite an existing imported or incomplete run |
| `--close` | Override `manifest.close` (yfinance fetch still attempted for cache) |
| `--precompute` | Chain Step 0 after import (requires EPS) |
| `--force-fetch` | Fresh yfinance during chained precompute |

## Import pipeline

Order (post-review hardening):

1. Validate intake (15 PNGs, no visible non-PNG files; dotfiles like `.DS_Store` ignored)
2. Guard: block complete imports without `--force`; distinct error for incomplete imports
3. Purge stale `analysis_context.json`
4. Fetch yfinance → write `market_history.json` (or fail / fallback per below)
5. Copy charts to canonical names
6. Write `manifest.json`
7. `load_manifest()` validation

### Close / market data

- **Success:** `fetch_market_series` → `cache_market_series` → `manifest.close` = last bar close
- **Fetch failure, no `--close`:** `InputError` — no charts copied, no manifest written
- **Fetch failure, with `--close`:** writes manifest with override; deletes stale `market_history.json`; warns that precompute needs network
- **`--close` with successful fetch:** override applies to `manifest.close` only; cache still written

Warns (non-fatal) when `as_of_date != run_date` (weekend/holiday).

### Force / stale artifacts

- `--force` overwrites charts + manifest on complete imports
- Any import purges `analysis_context.json` if present
- Incomplete state (canonical charts but `chart_count != 15`): error with `incomplete import detected … use --force`

## Operator workflow

```bash
# 1. Screenshot 15 charts in fixed order → save to Images/2026-06-24/
#    (do not rename out of capture sequence)

# 2. Import
python -m src.cli import-run --date 2026-06-24

# 3. Verify EPS if needed
python -m src.cli show-eps --date 2026-06-24

# 4. Run analysis
python -m src.cli run --date 2026-06-24
```

## Code changes

| Module | Change |
|--------|--------|
| `src/chart_pack.py` | **New** — `CHART_PACK`, `build_manifest()` |
| `src/import_run.py` | **New** — `import_run()`, intake validation, copy/rename, close fetch |
| `src/cli.py` | `import-run` command with `--precompute` chain |
| `tests/test_import_run.py` | **New** — 11 tests |
| `README.md` | `import-run` usage and operator notes |

## Tests

`tests/test_import_run.py` covers:

- Happy path (rename, manifest, market cache)
- Wrong PNG count, non-PNG rejection, dotfile ignore
- Force overwrite, incomplete-import guard
- Fetch failure (no orphan charts; stale cache purge with `--close`)
- Close override, analysis_context purge on force
- Chart pack parity with `2026-06-23` manifest

## Plan deviations

| Plan | Shipped |
|------|---------|
| Write order: charts → fetch → manifest | **fetch → charts → manifest** — avoids orphan canonical charts on network failure |
| Fail on any non-PNG file | **Ignore dotfiles** (`.DS_Store`) — still fail on visible `.jpg`/`.heic` |
| Generic "already imported" error | **Distinct incomplete-import message** when charts exist but manifest not ready |
| Stale cache on fetch failure + `--close` | **Delete `market_history.json`** on fetch failure |
| `analysis_context` purge on `--force` only | **Purge on every import** — simpler and safer |

## Non-goals

- Image resize/optimization (Pass 1/2 in `anthropic_client.py`)
- HEIC/JPEG conversion (PNG intake only)
- EPS gating at import (only at `--precompute` / `run`)

---

## OHLC sanitization (post-ship hardening)

**Problem:** `yf.download()` bulk history sometimes returns a last-row stub with NaN OHLC but valid volume, while `Ticker.history()` for the same session returns full prices.

**Fix (`src/market_data.py`):**

1. After every bulk fetch, **sanitize** the dataframe: for each NaN OHLC row, retry that session via `Ticker.history()`.
2. **Drop** unreparable NaN rows; **fail closed** if the run date session cannot be repaired.
3. **Refuse to cache** invalid bars; **auto-refetch** if an existing cache contains NaN.
4. `build_market_data_context` rejects non-finite SPX close.

This keeps the 300-day bulk fetch for SMA/Monte Carlo while making the run-date close reliable.
