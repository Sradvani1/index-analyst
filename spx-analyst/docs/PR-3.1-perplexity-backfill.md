# PR-3.1: June Perplexity backfill

**Status:** Implemented  
**Builds on:** [PR-3](PR-3-memory-rollup-overhaul.md) · [PR-1](PR-1-spx-daily-framework-migration.md)  
**Design plan:** [`.cursor/plans/june_perplexity_backfill_2888cb73.plan.md`](../../.cursor/plans/june_perplexity_backfill_2888cb73.plan.md)

## Summary

Rebuilds valid `daily-2026-06` memory for early June 2026 from [`perplexity_analysis_history.md`](../../perplexity_analysis_history.md) **without chart packs**. Perplexity markdown supplies qualitative evidence; yfinance Step 0 precompute supplies authoritative numerics; `apply_precomputed_fields` runs after Pass 1 like live runs.

**PR-4 note:** Backfill uses text-only Pass 2 (`run_text_markdown_report`). It does not invoke `resolve_pass2_images` or Pass 2 image optimization — no conflict with [PR-4](PR-4-pass2-image-optimization.md).

## Provenance

| Field | Value |
|-------|-------|
| `framework_version` | `daily-2026-06` (same as live runs) |
| `run_log.source` | `perplexity_backfill` |
| `run_log.perplexity_close` | Header close from export (reference) |
| `run_log.yfinance_close` | Authoritative close after enforcement |

## Operator runbook

### Step 0 — Archive invalid June files

```bash
cd spx-analyst
mkdir -p memory-archive/perplexity-migration-2026-06
mv memory/daily_states/2026-06-0{1,2,4,5,8}-state.json memory-archive/perplexity-migration-2026-06/
mv memory/daily_reports/2026-06-0{1,2,4,5,8}-analysis.md memory-archive/perplexity-migration-2026-06/ 2>/dev/null || true
```

Keep **2026-06-10** unless you want a full MC/enforcement-consistent re-backfill.

### Step 1 — EPS-only run dirs

```bash
for d in 2026-06-01 2026-06-02 2026-06-04 2026-06-05 2026-06-08; do
  python -m src.cli setup-run --date $d
done
```

Edit each `data/runs/{d}/external_context.json`:

```json
{
  "date": "2026-06-01",
  "forward_eps": 354,
  "trailing_eps": 220
}
```

Adjust EPS if you have session-specific values; document assumptions in `run_log.json` warnings.

### Step 2 — Sequential backfill (oldest first)

```bash
python -m src.cli migrate-perplexity \
  --history ../perplexity_analysis_history.md \
  --from 2026-06-01 \
  --to 2026-06-08
```

Sessions in export: **2026-06-01, 02, 04, 05, 08** (5 days). Each session rebuilds rolling memory from prior valid states.

**API cost:** 5 dates × 2 text-only Claude passes (no images).

### Step 3 — Verify

```bash
python -m src.cli rebuild-summary --days 6
cat memory/rolling/recent_summary.md
```

Check:

- Five `### 2026-06-…` blocks with categorical `signals:` lines
- Footer regime arc + unresolved watchlist
- All backfilled `memory/daily_states/2026-06-0*-state.json` validate as `daily-2026-06`
- `output/{date}/analysis_context.json` exists for each backfilled date
- `run_log.source == perplexity_backfill`

### Step 4 — Enable live memory

```bash
# .env
SPX_INCLUDE_MEMORY=true
```

Future daily runs append to the valid archive; PR-3 rollup continues automatically.

## Acceptance criteria

- [ ] Five valid `daily-2026-06` states for 2026-06-01, 02, 04, 05, 08
- [ ] Matching reports in `memory/daily_reports/`
- [ ] `memory/rolling/recent_summary.md` shows PR-3 posture format
- [ ] `rebuild-summary` with zero invalid skips
- [ ] `apply_precomputed_fields` applied; provenance in `run_log`

## Files changed

- `src/migrate_perplexity.py` — precompute, enforcement, PR-3 prompts, rolling rebuild
- `src/cli.py` — `migrate-perplexity` command
- `tests/test_migrate_perplexity.py`
- `README.md` — Legacy Perplexity section updated
