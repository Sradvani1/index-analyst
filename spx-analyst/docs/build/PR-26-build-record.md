# Build Record — PR-26: StreetStats EPS Sync and Weekly Prompt Trend

**Date:** 2026-08-09
**Phase:** PR-26 daily EPS source synchronization
**Status:** Complete — implemented, tested, reviewed, and committed
**Cadence:** Daily (unchanged)

---

## 1. What Was Built

PR-26 replaces manual daily EPS-history maintenance with a one-shot StreetStats
sync at the start of the automated daily workflow. It delivers three connected
capabilities:

1. **Full-history source refresh** — obtains a guest token, downloads the complete
   `growthHistory` payload, validates and normalizes it, and atomically replaces
   `data/master/eps_history.json`.
2. **Failure-safe local fallback** — source, parsing, validation, or master-file
   failures leave the prior master unchanged and resolve the latest qualifying
   local row instead.
3. **Compact model context** — retains the full local history for resolution and
   audit, while sending only the current authoritative EPS pair and the latest 12
   completed Monday-Friday weekly points to Pass 1 and Pass 2.

The checked-in master snapshot contains 7,952 normalized observations spanning
`1995-01-03` through `2026-08-07` at the time of implementation.

## 2. Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Source flow | `GET /api/token`, then `GET /api/valuation/market/growth` with `Authorization: Bearer <token>` | Matches the working public guest-token flow; no API key is required |
| Retry policy | One source attempt per daily sync; no retry inside the EPS adapter | Keeps the source contract explicit and prevents hidden repeated calls; the existing LLM retry wrapper is unrelated |
| Master update | Replace the entire normalized history, not append a selected row | The provider response is the canonical full-history source and avoids stale/manual snapshots |
| Write safety | Same-directory temporary file, flush/fsync, then `os.replace` | Prevents partial JSON from becoming the active master |
| Truncation protection | Reject a response that omits dates from an existing valid local history | A valid JSON response can still be incomplete; conservative fallback is safer than destroying history |
| Run-date resolution | Select the latest source row where `effective_from <= run_date` | Preserves the existing EPS resolver and historical-run behavior |
| Prompt trend | Select one latest available weekday row per completed Monday-Friday week; retain the latest 12 | Provides directional context without rendering the multi-year file into the prompt; Thursday naturally serves as the fallback when Friday is absent |
| Numeric authority | The resolved current EPS block is authoritative; weekly points are context only | Prevents the model from treating historical trend points as the run-date EPS value |
| Provenance | Store raw-response SHA-256 and canonical normalized-history SHA-256 | The raw fingerprint identifies the provider response; the normalized fingerprint can be recomputed from the master file |
| Payload retention | Store only normalized EPS fields, not the full provider payload | Keeps the model and local artifacts focused on the existing EPS contract |

The source is an undocumented proprietary endpoint with no stability, SLA, or
licensing guarantee. It is isolated behind an adapter so the provider can be
replaced without changing prompt or resolver contracts.

## 3. Architecture

### 3.1 Daily Runtime Flow

```text
scripts/daily-run.sh
        │
        ├─ market-open/data readiness check
        │
        ▼
src.cli sync-eps --date <date>
        │
        ▼
src.streetstats_eps.fetch_streetstats_history()
        │
        ├─ /api/token
        ├─ /api/valuation/market/growth
        ├─ decode gzip / JSON
        ├─ validate positive numeric EPS rows and unique dates
        ├─ normalize Date / ntmE / ltmE
        └─ compute response and normalized-history fingerprints
        │
        ▼
src.eps_sync.sync_eps_for_date()
        │
        ├─ compare incoming date coverage with valid local master
        ├─ atomically replace data/master/eps_history.json on success
        ├─ write data/runs/<date>/eps_source.json
        └─ preserve master and resolve local fallback on failure
        │
        ▼
prepare → run
        │
        ├─ load_eps_history() / require_eps_for_run()
        ├─ select_completed_weekly_eps(..., limit=12)
        ├─ build Pass 1 prompt with current pair + weekly trend
        └─ build Pass 2 prompt with current pair + weekly trend
```

### 3.2 Component Relationships

| Component | Role | Depends on |
|-----------|------|------------|
| `src/streetstats_eps.py` | HTTP transport, token flow, gzip/JSON decoding, source validation, normalization, fingerprints | `urllib`, `gzip`, `json`, `schemas`, `config` |
| `src/eps_sync.py` | Full-history replacement, truncation guard, fallback result, source artifact | `streetstats_eps`, `eps_history`, `files`, `schemas` |
| `src/files.py` | Atomic JSON persistence and `eps_source.json` filename contract | `tempfile`, `os`, `pydantic` |
| `src/eps_history.py` | Local load/resolve behavior and completed-week selection | `schemas`, `config`, `files` |
| `src/prompts.py` | Current EPS block and compact weekly-trend block in both passes | `eps_history`, `schemas` |
| `src/cli.py` | `sync-eps` operator command and status/exit behavior | `eps_sync`, `files` |
| `scripts/daily-run.sh` | Places EPS sync before `prepare` and `run` | CLI, existing market readiness check |
| `src/analysis_engine.py` | Copies the per-run EPS source artifact into completed `run_log.json` | `files`, existing output persistence |

## 4. API Contracts

### 4.1 Provider Endpoints

```text
GET https://streetstats.finance/api/token
Accept: application/json
```

Expected response shape:

```json
{"token": "<guest-token>"}
```

```text
GET https://streetstats.finance/api/valuation/market/growth
Accept: application/json
Accept-Encoding: gzip
Authorization: Bearer <guest-token>
```

Expected response shape:

```json
{
  "growthHistory": [
    {"Date": "2026-08-07", "ntmE": 384.63, "ltmE": 326.52}
  ]
}
```

The adapter rejects missing/empty history, non-object rows, invalid dates,
duplicate dates, non-positive or non-finite EPS values, invalid JSON, transport
errors, and responses with no row on or before the requested run date.

### 4.2 Python Adapter Contract

```python
def fetch_streetstats_history(
    run_date: str,
    *,
    settings: Settings | None = None,
) -> StreetStatsFetch
```

`StreetStatsFetch` contains:

```python
history: EpsHistory
source_as_of_date: str
forward_eps: float
trailing_eps: float
retrieved_at: str
response_sha256: str
history_sha256: str
```

`StreetStatsError` is the adapter-level failure type. Callers do not receive
partially normalized data.

### 4.3 Sync Contract

```python
def sync_eps_for_date(
    run_date: str,
    *,
    settings: Settings | None = None,
) -> EpsSyncResult
```

`EpsSyncResult.status` is one of:

| Status | Meaning | Master file |
|--------|---------|-------------|
| `updated` | Source history validated and was written | Replaced atomically |
| `fallback` | Source sync failed, but local EPS resolved | Unchanged |
| `missing` | Source sync failed and no local EPS resolved | Unchanged; CLI exits 1 |

The CLI command is:

```bash
python -m src.cli sync-eps --date YYYY-MM-DD
```

## 5. Data Models and File Contracts

### 5.1 Master History

`data/master/eps_history.json` retains the existing schema:

```json
{
  "entries": [
    {
      "effective_from": "YYYY-MM-DD",
      "forward_eps": 384.63,
      "trailing_eps": 326.52
    }
  ]
}
```

`EpsHistoryEntry` forbids unknown fields, validates ISO dates, and requires
positive `forward_eps` and `trailing_eps`. `EpsHistory` requires at least one
entry and unique `effective_from` values. The source normalizer sorts entries by
date before constructing the model.

### 5.2 Source Artifact

`data/runs/<date>/eps_source.json` stores the sync result:

```json
{
  "status": "updated",
  "requested_for": "2026-08-07",
  "provider": "streetstats",
  "source_as_of_date": "2026-08-07",
  "forward_eps": 384.63,
  "trailing_eps": 326.52,
  "retrieved_at": "<UTC timestamp>",
  "response_sha256": "<raw-response hash>",
  "history_sha256": "<canonical-history hash>",
  "error": null
}
```

Completed analysis runs load this dictionary and copy it to
`output/<date>/run_log.json` under `eps_sync`. A failed source sync records the
fallback status and error while preserving the old master.

### 5.3 Prompt Data

The full `EpsHistory` remains available to Python for date resolution and weekly
selection. Prompt builders receive:

1. The resolved `ResolvedEps` pair as the authoritative current EPS block.
2. Up to 12 entries shaped as `as_of_date`, `forward_eps`, and `trailing_eps`.

Only completed weeks are eligible. Weekend rows are excluded, future rows are
excluded, and an in-progress week is excluded even if it has earlier weekday
observations.

## 6. Configuration and Operator Behavior

| Setting | Default | Purpose |
|---------|---------|---------|
| `SPX_STREETSTATS_BASE_URL` | `https://streetstats.finance` | Provider host/path root |
| `SPX_STREETSTATS_TIMEOUT_SECONDS` | `30` | Timeout for each token/growth request |
| `SPX_EPS_HISTORY_PATH` | `data/master/eps_history.json` | Normalized master history location |

The automated order is:

```text
market readiness → sync-eps → prepare → run → export-report
```

The sync is outside the existing LLM retry wrapper. `prepare` and `run` consume
the local master and do not perform hidden StreetStats calls.

## 7. Test and Verification Record

Added coverage includes:

- Token authorization and full-history normalization.
- No-retry behavior after transport failure.
- Invalid UTF-8 response fallback through `StreetStatsError`.
- Entire-master replacement and source-artifact fields.
- Truncated-history rejection with unchanged master content.
- Completed-week selection, latest trading-day selection, incomplete-week exclusion,
  and 12-point prompt truncation.

Verification completed:

```text
436 passed, 1 warning
python -m compileall -q src tests: passed
git diff --check: passed
live sync-eps --date 2026-08-07: updated
live show-eps --date 2026-08-07: forward=384.63 trailing=326.52
```

The one warning is the existing Starlette/httpx deprecation warning from the test
environment; it is unrelated to PR-26.

## 8. Context for the Next Phase

- StreetStats is undocumented and proprietary. Monitor endpoint availability,
  token behavior, response shape, and terms before treating it as a permanent
  production dependency.
- The raw provider response is fingerprinted but intentionally not archived; the
  normalized history hash is the durable local reproducibility contract.
- Master and source-artifact writes are separate filesystem operations. The master
  remains the source of truth; the artifact is audit metadata and is copied into
  completed run logs when present.
- The truncation guard compares incoming dates with the existing valid master. If
  the provider intentionally removes historical dates, an operator may need to
  review the source change before accepting a replacement.
- The weekly trend is deliberately compact and deterministic. Any future event or
  weekly cadence should reuse the selector contract rather than render the full
  history into prompts.
- The next phase can replace the StreetStats adapter without changing
  `EpsHistory`, `ResolvedEps`, prompt blocks, or the daily-run ordering.
