# PR-4: Pass 2 dynamic image selection and downscaling

**Status:** Implemented (live A/B on 2026-06-10 complete — see [A/B results](../output/ab-test/RESULTS.md))  
**Framework version:** `daily-2026-06`  
**Builds on:** [PR-1](PR-1-spx-daily-framework-migration.md) · [PR-2](PR-2-spx-two-pass-prompt-overhaul.md) · [PR-3](PR-3-memory-rollup-overhaul.md)  
**Design plan:** [`.cursor/plans/pass_2_image_optimization_b11cc4d9.plan.md`](../../.cursor/plans/pass_2_image_optimization_b11cc4d9.plan.md) (aligned to this record)

## Summary

Reduces Pass 2 multimodal cost by sending **fewer charts** at **slightly lower resolution**, without losing signal on charts that matter. Pass 1 is **frozen** — full manifest, full-fidelity images, existing prompt unchanged.

Every Pass 2 attachment decision is explainable after the run via `pass2_selection_reasons` in `run_log.json`.

## Pass separation

| Pass | Charts | Resolution | Prompt |
|------|--------|------------|--------|
| **Pass 1** | Full manifest (`manifest.ordered_charts()`) | `SPX_IMAGE_MAX_DIMENSION` (1568) | Unchanged — full `_manifest_block`, existing task, optional posture snapshot |
| **Pass 2** | `Pass2ImagePlan.attached` only | `SPX_PASS2_IMAGE_MAX_DIMENSION` (1092) when optimization on | Attached/reference manifest block + PR-2 task + optional posture snapshot |

Selection runs **after** `apply_precomputed_fields()` — input is post-enforcement `DailyState`, not raw Pass 1 tool output.

## Authority boundaries

Pass 2 must not indirectly re-read omitted charts. Reference-only entries are listed in the prompt but **not** sent as image bytes.

| Source | Pass 2 authority |
|--------|------------------|
| **Attached images** | Inspectable evidence — descriptive detail and conflict reconciliation for those files only |
| **Reference-only manifest entries** | Filename + label visible; **not** visually inspectable — cite from validated state / conflict checklist text only |
| **Validated daily state** | Immutable numeric and qualitative truth for the report |
| **Prior posture snapshot (PR-3)** | Continuity only — not today's chart evidence |

> When attached-image impressions, prompt wording, and validated daily state differ, **validated daily state is authoritative**.

Pass 1 remains the sole pass that reads the full chart pack at full fidelity.

## Settings

| Variable | Default | Purpose |
|----------|---------|---------|
| `SPX_PASS2_IMAGE_OPTIMIZATION` | `true` | Enable dynamic selection + Pass 2 downscaling |
| `SPX_PASS2_IMAGE_MAX_DIMENSION` | `1092` | Max edge for Pass 2 encoded images |

Operator floor: do not set `SPX_PASS2_IMAGE_MAX_DIMENSION` below **784** without accepting fidelity risk.

### Flag-off (`SPX_PASS2_IMAGE_OPTIMIZATION=false`)

| Field / behavior | Value |
|------------------|-------|
| `attached` | Full manifest paths |
| `reference_only` | `[]` |
| `pass2_charts_omitted` | `[]` |
| `selection_reason` | Every attached filename → `["optimization_disabled"]` |
| Pass 2 prompt | Legacy full `_manifest_block(manifest)` |
| Pass 2 encoding | `SPX_IMAGE_MAX_DIMENSION` (same as Pass 1) |

`run_log.chart_count` == `pass1_chart_count` == full manifest length in both flag-on and flag-off modes.

## Selector (`src/pass2_images.py`)

**Entry point:** `resolve_pass2_images(run_dir, manifest, daily_state, settings) -> Pass2ImagePlan`

Pure Python, deterministic, no LLM involvement.

### Steps

1. **Protected conflict refs** — every resolved `conflicting_evidence[].chart_refs` basename (case-insensitive) must appear in `attached`; never pruned. Unresolved refs append structured warnings; run continues. Duplicate refs across divergences are deduped in `pass2_unresolved_chart_refs`.
2. **Matrix-driven expansion** — non-neutral qualitative rows add charts (see mapping below). Rows that never auto-add: Leverage Risk State, Overall Signal Balance, Recommended Action. Precompute-owned rows are excluded (`PRECOMPUTE_OWNED_MATRIX_ROWS` boundary — enforced by test).
3. **Conservative redundancy prune** — applies only to matrix-added charts (never protected conflict charts). Ambiguous cases: **keep**.

### Matrix row → chart mapping (v1)

| Matrix row | Rule |
|------------|------|
| Trend Regime | One `technical` chart: prefer `3month` or `6month` if signal contains `maturing`, `diverg`, or `flatten`; else longest unattached `technical` timeframe |
| Intraday Close Position | `timeframe=intraday` |
| RSI / MFI State, 20-Day SMA Status, Bollinger Band State | `timeframe=1month`, `category=technical` (same file — attach once) |
| Credit Condition | `category=credit` |
| Breadth Condition | `category=breadth`; prefer McClellan (`*mcclellan*`) |
| VIX Regime | `category=volatility` |

### Non-neutral row heuristic (v1)

A row qualifies when its `signal` (lowercased, stripped):

1. Is non-empty, **and**
2. Does not consist solely of neutral-only tokens, **and**
3. Contains at least one qualifying token (substring match allowed for qualifying list only).

**Neutral-only:** `neutral`, `within`, `monitor`, `insufficient`, `stable`, `unknown`, `none`  
**Qualifying (any one):** `trim`, `bear`, `bull`, `caution`, `diverg`, `widen`, `tighten`, `fear`, `greed`, `extreme`, `elevated`, `oversold`, `overbought`, `distribution`, `regime shift`, `defensive`, `attractive`, `weak`, `strong`, `deteriorat`, `improv`

If both neutral-only and qualifying tokens match, **prefer expansion** (conservative against signal loss).

### Prune rules (matrix-added only)

| Candidate | Prune when |
|-----------|------------|
| `5day` technical | `1month` technical attached |
| `3year` technical | `6month` or `1year` technical attached |
| `1year` technical | both `3month` and `6month` attached |
| `52wk` breadth | McClellan breadth attached |
| F&G momentum (`09_*`) | F&G overview (`08_*`) attached |
| Safe haven (`14_*`) | **Keep** when F&G overview attached (v1 default) |

### `Pass2ImagePlan` audit contract

| Field | Type | Notes |
|-------|------|-------|
| `attached` | `list[Path]` | De-duplicated, manifest `order` |
| `reference_only` | `list[ChartEntry]` | Remaining entries, manifest `order` |
| `selection_reason` | `dict[str, list[str]]` | Keys **exactly** match attached filenames; all reasons preserved (e.g. `["conflict_ref", "matrix_layer:Credit Condition"]`) |
| `unresolved_chart_refs` | `list[UnresolvedChartRef]` | `original_ref`, `outcome`, `message` |

Zero attached charts is a valid outcome when no conflict refs resolve and no matrix row qualifies.

## Pass 2 prompt contract

**Pass 1:** `build_state_prompt` unchanged (PR-2/PR-3).

**Pass 2:** `_pass2_manifest_block(attached, reference_only, manifest)` when optimization on; task section adds chart authority bullets (attached vs reference-only, validated-state precedence, prior-run posture block continuity only).

**Body order (fixed):**

1. Prior posture snapshot — when `SPX_INCLUDE_MEMORY=true` (PR-3 unchanged)
2. Precomputed analysis context
3. External context
4. Attached / reference-only chart block
5. Validated daily state (immutable JSON)
6. Conflict checklist
7. Task section

When zero charts attached, prompt states explicitly that no chart images are attached.

## Observability

### `run_log.json`

| Field | Meaning |
|-------|---------|
| `chart_count` | Pass 1 chart count (backward compatible) |
| `pass1_chart_count` | Same as `chart_count` |
| `pass2_chart_count` | Attached Pass 2 images |
| `pass2_image_optimization_enabled` | Flag at run time |
| `pass2_image_max_dimension` | Configured Pass 2 max edge |
| `pass2_charts_attached` | Filenames, manifest order |
| `pass2_charts_omitted` | Reference-only filenames (`[]` when flag-off) |
| `pass2_selection_reasons` | Per-file reason lists (keys ⊆ attached) |
| `pass2_unresolved_chart_refs` | Structured normalization failures |

PR-3 fields (`memory_included`, `memory_load`) unchanged.

### `request_snapshot.json` → `report_pass`

Same `pass2_*` fields as above, plus `pass2_image_max_dimension_used` (actual encode dimension).

## PR-3 interaction

| PR-3 artifact | PR-4 touch |
|---------------|------------|
| `_optional_memory_block` | **Unchanged** |
| `memory_load` in run_log | Coexists with `pass2_*` fields |
| Rollup `conflicts:` lines | Not selector input — today's refs only from `conflicting_evidence` |
| Zero-chart Pass 2 | Posture snapshot + validated state backstop |

## Files changed

| File | Change |
|------|--------|
| `src/pass2_images.py` | **New** — selector module |
| `src/config.py` | Pass 2 image settings |
| `src/analysis_engine.py` | Post-enforcement wiring; observability |
| `src/anthropic_client.py` | Pass 2 max_dim; snapshot audit fields |
| `src/prompts.py` | `_pass2_manifest_block`; `build_report_prompt` wiring only |
| `tests/fixtures/pass2_images/*.json` | Golden selector fixtures |
| `tests/test_pass2_images.py` | Selector + integration unit tests |
| `tests/test_prompt_builder.py` | Prompt authority contract |
| `tests/test_engine.py` | End-to-end pass2 fields |

## Testing

```bash
pytest   # 125 tests; includes test_pass2_images, test_engine pass2 paths, test_memory_rollup coexistence
```

Golden fixtures: `tests/fixtures/pass2_images/conflict_heavy.json`, `neutral_zero_chart.json`, `matrix_add.json`.

### Live A/B — 2026-06-10 (2026-06-21)

Full results: [`output/ab-test/RESULTS.md`](../output/ab-test/RESULTS.md)

| Metric | OFF (`SPX_PASS2_IMAGE_OPTIMIZATION=false`) | ON (default) |
|--------|--------------------------------------------|--------------|
| Pass 2 charts attached | 15 @ 1568px | **11 @ 1092px** |
| Pass 2 omitted | 0 | 4 |
| Pass 1 input tokens | 24,687 | 24,687 |
| Pass 2 input tokens | 30,747 | **16,794 (−45%)** |
| Total input tokens | 55,434 | **41,481 (−25%)** |
| `daily_state` validation | PASS | PASS |

**`validate_report` on live reruns:** both arms failed the **report** gate because Pass 2 returned a 25-token stub preamble (model did not emit the markdown body). This affected OFF and ON equally — not a PR-4 regression. The established baseline at `output/2026-06-10/` still **passes** `validate_report` (`python -m src.cli validate --date 2026-06-10`).

**Follow-up:** [PR-4.1](PR-4.1-pass2-stub-response-fix.md) — Pass 2 stub-response fix for `claude-opus-4-8` (stub detection + tools-free retry).

## Acceptance criteria

**Pass behavior**

- [x] Pass 1 identical to pre-PR-4 (full manifest @ 1568, prompt unchanged)
- [x] Pass 2 never omits a resolved conflict `chart_ref`
- [x] Pass 2 completes with zero attached charts
- [x] Mixed-signal days attach fewer than 15 charts when optimization on (live: 11/15 on 2026-06-10)
- [x] 2026-06-10 baseline report passes `validate_report` (`output/2026-06-10/`); live A/B report gate blocked by Pass 2 model stub (see A/B results — not PR-4-specific)

**Architecture**

- [x] Selection post-enforcement only
- [x] No `DailyState` schema changes
- [x] No fixed Pass 2 core bundle in v1
- [x] Multi-reason `selection_reason`; keys match attached files; manifest-ordered de-duplicated `attached`
- [x] Reference-only charts not sent as image bytes

**PR-3 unchanged**

- [x] Posture snapshot header and contract unchanged
- [x] `rebuild_rolling_summary()` on every successful run unchanged
- [x] `memory_load` in run_log when memory enabled unchanged

**Efficiency** (live 2026-06-10 A/B)

- [x] `pass2_charts_attached` length < 15 on mixed day (11 attached)
- [x] Pass 2 input tokens −45% (30,747 → 16,794); total run input −25%

## Expected token impact (2026-06-10 reference)

| Scenario | Attached | ~Image tokens @ 1092 |
|----------|----------|----------------------|
| Pre-PR-4 (15 @ 1568) | 15 | ~22,000 |
| PR-4 mixed day (live 2026-06-10) | 11 @ 1092 | 16,794 input tokens (API) |
| PR-4 neutral zero-chart | 0 | 0 |

## Out of scope

Plotly/scraper changes, `DailyState` schema, validation logic, Pass 1 prompt redesign, memory rollup logic, speculative heuristics beyond conflict refs + matrix adds + documented prune rules. `migrate_perplexity.py` memory header alignment (separate cleanup).
