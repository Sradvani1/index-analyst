# PR-8: Pass 1 Repair Hardening

Extends [PR-6: Pass 1 schema discipline](PR-6-pass1-schema-discipline.md) with structural coercion, broader signals drift rules, and richer `pass1_schema_status` observability. Repair remains a rare fallback — zero-repair is not a goal.

## Problem

Post-PR-6 instrumented runs showed **2 / 6 (33%)** repair rate vs an operator target of **~12–14%** (1 in 7–8). PR-6 eliminated repair for known `signals` extras (`vix_regime_detail`, `vix`, `*_note`, `put_call_zone`) but left two failure classes:

1. **Top-level type drift** — `what_changed_today` emitted as a single `str` instead of `list[str]` (2026-06-17).
2. **Novel `signals` hallucinations** — `rsi14_zone`, `rsi_divergence: null` (2026-06-10, 2026-06-17).

## Layers (builds on PR-6)

1. **Prompt discipline** (`build_state_prompt`): `what_changed_today` must be a JSON array of 3–5 strings; divergences belong in `conflicting_evidence`, not invented `signals` keys.
2. **Schema descriptions** (`DailyState.what_changed_today`, `DailyState.open_questions`): flows into `emit_daily_state` tool schema at zero extra prompt cost.
3. **Contract-preserving coalescer** (`state_normalize.coalesce_pass1_drift`): structural coercion plus PR-6 signals rules; unknown extras with substantive values left untouched (fail closed).
4. **Repair fallback** (unchanged): one text-only API call when coalesce + parse still fails.
5. **Observability**: extended `pass1_schema_status` and `normalize_audit.structural_coercions`.

## Entry point

`resolve_pass1_daily_state` calls **`coalesce_pass1_drift`**, which:

1. Applies structural rules (3a) on the full tool input.
2. Delegates to **`coalesce_signals_drift`** for PR-6 + PR-8 signals rules (3b–3d).

## Coalescence rules

### Structural (3a) — `coalesce_pass1_drift`

| Field | Condition | Action |
|-------|-----------|--------|
| `what_changed_today` | Non-empty `str` | Wrap as single-element `[str]`; audit `wrap_str_as_list` |

Whitespace-only strings are **not** coerced (validation fails → repair).

### Signals — `coalesce_signals_drift` (PR-6 + PR-8)

PR-6 rules unchanged: `vix_regime_detail`, `vix`, `{field}_note` append/merge; see [PR-6 coalescence table](PR-6-pass1-schema-discipline.md#coalescence-rules-v1).

| Rule | Extra key / pattern | Action |
|------|---------------------|--------|
| **3c** | `signals.*_zone` except `fear_greed_zone` | Drop unconditionally (generalizes `put_call_zone`) |
| **3d** | `FRAMEWORK_BLEED_KEYS` when null/empty | Drop (`framework_bleed_null_or_empty`) |
| **3b** | Any other unknown `signals` key when null/empty | Drop (`null_or_empty_unknown`) |
| Fail closed | Unknown key with non-null, non-empty value | Leave untouched → validation fails → repair |

`FRAMEWORK_BLEED_KEYS` (v1): `rsi_divergence`, `mfi_divergence`, `bearish_divergence`, `bullish_divergence`.

Non-null framework-bleed values are **not** dropped — substantive content must go through repair (or a future explicit merge into `conflicting_evidence`).

## `run_log.pass1_schema_status`

```json
{
  "original_valid": false,
  "normalized": true,
  "repair_triggered": false,
  "final_valid": true,
  "repair_avoided": true,
  "what_changed_today_count": 1,
  "what_changed_today_count_warning": true,
  "normalize_audit": {
    "merged": [],
    "dropped": [
      { "key": "signals.rsi_divergence", "reason": "framework_bleed_null_or_empty" }
    ],
    "untouched_unknown": [],
    "structural_coercions": [
      { "field": "what_changed_today", "action": "wrap_str_as_list" }
    ]
  },
  "validation_errors_original": [],
  "validation_errors_after_normalize": [],
  "repair_usage": null
}
```

| Field | Meaning |
|-------|---------|
| `repair_avoided` | `original_valid=false`, `repair_triggered=false`, `final_valid=true` |
| `what_changed_today_count` | Item count in **post-coalesce** `normalized_tool_input` |
| `what_changed_today_count_warning` | `true` when count &lt; 2 (warning only; does not fail run) |

## Success metric (SLO)

Over the first **20 post-deploy instrumented runs** (min **10** before judgment):

- **Primary:** `repair_rate` = `repair_triggered=true` / runs with `pass1_schema_status` ≤ **14%** (operator) or ≤ **10%** (north star).
- Pre-PR-8 runs and failed runs excluded from denominator.

Fixture regression (6/10 `rsi14_zone`, 6/17 string `what_changed_today` + null `rsi_divergence`) is necessary evidence, not sufficient for the SLO.

## Deferred (v1)

- No `rsi_divergence` (or other framework concepts) on `SignalSet`.
- No blind strip of unknown keys with values.
- No `open_questions` str→list coercion (schema description only).
- No `"; "` split heuristic for long `what_changed_today` strings.
- No post-repair quality gate for thin `what_changed_today`.
- No unconditional framework-bleed denylist drop for non-null values.

## Fixtures

`tests/fixtures/state_normalize/`:

| Fixture | Source failure |
|---------|----------------|
| `2026-06-17.json` | `what_changed_today` str + `rsi_divergence: null` |
| `2026-06-10-rsi14-zone.json` | `rsi14_zone: null` |

From `output/{date}/response_raw.json` (`state_pass_original`) + `{date}-state.json` (`repaired_signals`).

## Files changed

| File | Change |
|------|--------|
| `src/state_normalize.py` | `coalesce_pass1_drift`, rules 3a–3d, extended audit/status |
| `src/schemas.py` | `Field(description=...)` on list fields |
| `src/prompts.py` | `what_changed_today` + divergence contract |
| `tests/test_state_normalize.py` | PR-8 fixtures and unit tests |
| `tests/test_prompt_builder.py` | Prompt/schema description assertions |
| `tests/fixtures/state_normalize/` | `2026-06-17.json`, `2026-06-10-rsi14-zone.json` |
