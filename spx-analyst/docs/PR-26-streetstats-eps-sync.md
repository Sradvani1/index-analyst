# PR-26: StreetStats EPS sync

**Status:** Complete
**Builds on:** [PR-5](PR-5-eps-master-history.md) · [PR-20](PR-20-prepare-run-workflow.md)

## Summary

The daily runner now refreshes the master EPS history from StreetStats before
preparation. The source uses the public guest-token flow and the numeric growth
endpoint:

```text
GET /api/token
GET /api/valuation/market/growth
```

There is one sync attempt per daily run and no retry. The complete `growthHistory`
response is normalized to the existing `data/master/eps_history.json` contract:

```text
Date -> effective_from
ntmE -> forward_eps
ltmE -> trailing_eps
```

Only the EPS fields are stored in the master file. The full source payload is not
sent to the model.

## Update behavior

The sync command is:

```bash
python -m src.cli sync-eps --date YYYY-MM-DD
```

On a valid response it atomically replaces the master file with the complete
normalized history. The latest valid source row on or before the requested run
date is recorded in `data/runs/<date>/eps_source.json` and in the completed run's
`run_log.json` under `eps_sync`.

The source artifact records both a fingerprint of the raw response and a
canonical fingerprint of the normalized history. The latter can be recomputed
from the master file without retaining the provider's full response.

If the source request, parsing, validation, or write fails, the master file is not
modified. The command falls back to the latest qualifying local row. It exits with
an error only when no usable local history exists. No retry is performed.

The existing EPS resolver remains unchanged: it selects the latest row where
`effective_from <= run_date`. This keeps historical CLI and migration behavior
backward compatible.

## Prompt trend

The full local history is retained for resolution and audit, but the model receives
only the latest 12 completed Monday-Friday weeks. For each week, Python selects the
latest available trading-day row, using Thursday when Friday is absent. The current
resolved EPS pair remains the authoritative numeric block and is provided separately.

The full three-year history is no longer rendered into Pass 1 or Pass 2 prompts.

## Daily workflow

`scripts/daily-run.sh` now runs:

```text
market status -> sync-eps -> prepare -> run
```

The sync is outside the existing LLM retry wrapper. `prepare` and `run` continue
to consume local EPS data and do not perform hidden network fetches.

## Files

| File | Change |
|------|--------|
| `src/streetstats_eps.py` | StreetStats token request, growth fetch, validation, normalization |
| `src/eps_sync.py` | One-shot sync, fallback behavior, atomic master update, source artifact |
| `src/eps_history.py` | Completed-week EPS selection |
| `src/prompts.py` | Compact 12-week trend block in both passes |
| `src/analysis_engine.py` | Include EPS sync provenance in `run_log.json` |
| `src/cli.py` | Add `sync-eps` command |
| `scripts/daily-run.sh` | Run EPS sync before preparation |
| `src/config.py` | StreetStats host and timeout settings |
| `src/files.py` | Atomic JSON writer and source artifact filename |

## Verification

```bash
.venv/bin/pytest -q
.venv/bin/python -m src.cli sync-eps --date YYYY-MM-DD
.venv/bin/python -m src.cli show-eps --date YYYY-MM-DD
```
