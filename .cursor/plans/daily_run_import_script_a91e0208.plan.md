---
name: Daily Run Import Script
overview: Add a new `import-run` CLI command that copies 15 screenshots from `Images/<date>/` into the run folder, builds a canonical manifest (with yfinance close), and optionally chains precompute — replacing today's manual chart copy + manifest editing workflow.
todos:
  - id: chart-pack-module
    content: Create src/chart_pack.py with canonical 15-chart definitions and build_manifest()
    status: completed
  - id: import-run-module
    content: "Create src/import_run.py: glob/sort images, copy/rename, fetch close, write manifest + market_history cache"
    status: completed
  - id: cli-command
    content: Add import-run command to src/cli.py with --images-dir, --force, --close, --precompute flags
    status: completed
  - id: tests
    content: "Add tests/test_import_run.py: happy path, wrong count, force+stale precompute purge, close override, non-png rejection, review hardening"
    status: completed
  - id: domain-docs
    content: Domain glossary doc — cancelled; vocabulary lives in PR docs and README
    status: cancelled
  - id: readme
    content: Document import-run workflow in spx-analyst/README.md
    status: completed
  - id: pr9-doc
    content: Write docs/PR-9-daily-run-import.md
    status: completed
isProject: false
---

# Daily Run Import Script

**Status:** Shipped — see [PR-9](../spx-analyst/docs/PR-9-daily-run-import.md)

## Implementation summary

`import-run` ingests 15 PNGs from `Images/<date>/`, writes canonical charts + manifest under `data/runs/<date>/`, fetches yfinance close, and caches `market_history.json`.

```bash
python -m src.cli import-run --date 2026-06-24
python -m src.cli run --date 2026-06-24
```

## Deviations from original plan

| Original plan | Shipped behavior | Rationale |
|---------------|------------------|-----------|
| Write order: copy charts → fetch close → manifest | **fetch close → copy charts → manifest** | Network failure must not leave orphan canonical charts that block retry |
| Reject all non-PNG files in intake dir | **Ignore dotfiles** (`.DS_Store`) | macOS noise; still reject visible `.jpg`/`.heic` |
| Single "already imported" error | **Distinct incomplete-import message** | Charts without 15-chart manifest → `incomplete import detected … use --force` |
| Purge `analysis_context.json` on `--force` only | **Purge on every import** | Safer; any re-import invalidates Step 0 |
| Stale `market_history.json` on fetch failure + `--close` | **Delete cache on fetch failure** | Prevents precompute from using wrong-day data |

## Final pipeline

```mermaid
flowchart TD
    A[Validate 15 PNGs] --> B{import guard}
    B -->|complete + no force| X[already imported]
    B -->|incomplete + no force| Y[incomplete import]
    B -->|ok| C[Purge analysis_context]
    C --> D[fetch_market_series + cache]
    D --> E[Copy charts 01..15]
    E --> F[Write manifest.json]
    F --> G[load_manifest validate]
    G --> H{--precompute?}
    H -->|yes| I[run_precompute]
```

## Modules

- [`src/chart_pack.py`](../spx-analyst/src/chart_pack.py) — SSoT for 15-chart definitions
- [`src/import_run.py`](../spx-analyst/src/import_run.py) — import logic
- [`src/cli.py`](../spx-analyst/src/cli.py) — `import-run` command
- [`tests/test_import_run.py`](../spx-analyst/tests/test_import_run.py) — 11 tests

## Operator workflow

1. Screenshot 15 charts in fixed order → `Images/<date>/` (alphabetical filename order = chart order)
2. `python -m src.cli import-run --date <date>`
3. `python -m src.cli show-eps --date <date>` (if EPS row needed)
4. `python -m src.cli run --date <date>`

Optional: `--precompute` on step 2.
