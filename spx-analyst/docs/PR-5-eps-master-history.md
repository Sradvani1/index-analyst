# PR-5: EPS master history

**Status:** Complete  
**Builds on:** [PR-1](PR-1-spx-daily-framework-migration.md) · [PR-3.1 backfill](PR-3.1-perplexity-backfill.md)

## Summary

Forward/trailing EPS now live in a single append-only master file — `data/master/eps_history.json` — instead of per-run `external_context.json` files. EPS is resolved deterministically by run date and passed in-memory through precompute and prompts. Provenance is recorded in `run_log.eps_resolution` only.

## Master file

```json
{
  "entries": [
    {
      "effective_from": "2026-06-01",
      "forward_eps": 354,
      "trailing_eps": 220,
      "notes": "optional"
    },
    {
      "effective_from": "2026-06-10",
      "forward_eps": 370,
      "trailing_eps": 290
    }
  ]
}
```

When consensus changes, **append** a new row. Do not edit historical rows. Both `forward_eps` and `trailing_eps` must be positive.

## Resolution

- **Source:** `data/master/eps_history.json` (or `SPX_EPS_HISTORY_PATH`)
- **Rule:** latest entry where `effective_from <= run_date` (compared as `YYYY-MM-DD` date strings)
- **Sorting:** entries may be stored in any order; the loader sorts before resolution
- **Example:** run date `2026-06-08` → `2026-06-01` row; run date `2026-06-10` → `2026-06-10` row

## Failure policy

| Command | Unresolved EPS |
|---------|----------------|
| `show-eps --date` | Prints message; **exit 1** |
| `setup-run` | Warns; run not ready |
| `setup-run --precompute` | **Fails** (exit 1) |
| `run` | **Fails** before precompute |
| `migrate-perplexity` | **Fails** with guidance |

Invalid master files (malformed JSON, duplicate `effective_from`, empty `entries`, non-positive EPS) surface as unresolved EPS with a clear message — no silent fallback.

## Reproducibility

Completed runs record the exact EPS pair in `output/<date>/run_log.json` → `eps_resolution`. Re-running that date later resolves fresh from master history — results match the original run only if the corresponding historical row(s) still exist in the master file.

## Operator workflow

```bash
# Inspect resolution
python -m src.cli show-eps --date 2026-06-10

# Daily — no per-run EPS files
python -m src.cli setup-run --date 2026-06-21
python -m src.cli run --date 2026-06-21
```

When EPS changes, append to `data/master/eps_history.json`:

```json
{ "effective_from": "2026-06-15", "forward_eps": 358, "trailing_eps": 222 }
```

## Code changes

| Module | Change |
|--------|--------|
| `src/eps_history.py` | Load, resolve, `require_eps_for_run`, `eps_resolution_log` |
| `src/schemas.py` | `EpsHistory`, `EpsHistoryEntry`, `ResolvedEps`; removed `ExternalContext` |
| `src/config.py` | `SPX_EPS_HISTORY_PATH` |
| `src/cli.py` | `show-eps`; `setup-run` EPS validation; migrate catches `InputError` |
| `src/analysis_engine.py` | `require_eps_for_run`; `run_log.eps_resolution` |
| `src/migrate_perplexity.py` | Same resolver as live runs |

## Removed

- `data/runs/<date>/external_context.json` — no code path reads or writes this file
- `src/external_data.py` — replaced by `src/eps_history.py`
- `ExternalContext` schema — replaced by in-memory `ResolvedEps` (EPS carrier only)

## Verification

```bash
cd spx-analyst
pytest tests/test_eps_history.py -v
pytest
python -m src.cli show-eps --date 2026-06-10
```
