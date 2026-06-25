# PR-6: Pass 1 Schema Discipline

## Goal

Reduce Pass 1 schema repair by making `signals` contract expectations explicit, coalescing only known extra-field drift before parse, and logging every normalization or repair step as auditable structured state. Repair remains a rare fallback.

## Layers

1. **Prompt discipline** (`build_state_prompt`): explicit allowed-key list and prohibition of `*_detail`, `*_note`, extra `*_zone` fields.
2. **Schema descriptions** (`SignalSet` `Field(description=...)`): flows into `emit_daily_state` tool schema at zero extra prompt cost.
3. **Contract-preserving coalescer** (`state_normalize.coalesce_pass1_drift` → `coalesce_signals_drift`): allowlisted rules only; unknown extras with values left untouched (fail closed). Extended in [PR-8](PR-8-pass1-repair-hardening.md).
4. **Observability**: `pass1_schema_status` in `run_log.json`; traceable payloads in `response_raw.json`.

## Coalescence rules (v1)

| Extra key | Action |
|-----------|--------|
| `signals.vix_regime_detail` | Append to `vix_regime` with ` — `; delete extra |
| `signals.vix` (numeric) | Append `VIX {v:.2f}` to `vix_regime` if level not already present; delete |
| `signals.{field}_note` | Append to `{field}` when both are strings; else drop |
| `signals.put_call_zone` | Drop |
| Any other unknown `signals` key | Leave untouched → validation fails → repair |

## `response_raw.json` keys

| Key | When present |
|-----|--------------|
| `state_pass` | Always (raw API response; backward compatible) |
| `state_pass_original` | Always (first-pass tool input dict) |
| `state_pass_normalized` | When coalescer changed the payload |
| `repair_pass` | When repair API call ran |

Migration backfills use `pass1` / `pass2` for API responses plus the same `state_pass_*` trace keys.

## `run_log.pass1_schema_status`

```json
{
  "original_valid": false,
  "normalized": true,
  "repair_triggered": false,
  "final_valid": true,
  "normalize_audit": { "merged": [], "dropped": [], "untouched_unknown": [] },
  "validation_errors_original": [],
  "validation_errors_after_normalize": [],
  "repair_usage": null
}
```

## Deferred (v1)

- No `vix: Optional[float]` on `SignalSet` unless live gate fails after Layers 1–3.
- No official `vix_regime_detail` field.
- No blind strip of unknown keys; `extra="forbid"` unchanged.

## Fixtures

Historical invalid first-pass payloads live in `tests/fixtures/state_normalize/` (from `output/**/response_raw.json` for 6/02, 6/04, 6/08, 6/10, 6/12, ab-test/off). Tests assert parse success after coalesce and material equivalence vs repaired `*-state.json`.
