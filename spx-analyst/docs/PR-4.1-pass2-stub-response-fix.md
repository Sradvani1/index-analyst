# PR-4.1: Pass 2 stub-response fix (claude-opus-4-8)

**Status:** Implemented  
**Follows:** [PR-4](PR-4-pass2-image-optimization.md) live A/B (`output/ab-test/RESULTS.md`)

## Problem

On `claude-opus-4-8`, Pass 2 sometimes returned a ~25-token text preamble instead of the full markdown report:

> "I'll emit the structured daily state and then deliver the full markdown report."

This occurred when Pass 2 sent `tools=[emit_daily_state]` with `tool_choice: none` (the PR-2 cache-prefix pattern). Pass 1 state was fine; only Pass 2 report failed `validate_report`. Both optimization OFF and ON were affected — not a PR-4 selector regression.

## Root cause

The model treated Pass 2 as another structured-state turn because `emit_daily_state` remained visible in the request, despite `tool_choice: none` and the exposition-only task wording.

## Fix

1. **Prompt** (`build_report_prompt`): explicit instruction that Pass 1 already completed, do not call tools, entire response must be markdown only.
2. **Client** (`run_markdown_report`):
   - Attempt 1: unchanged cache-friendly request (tools + `tool_choice: none`).
   - If `_is_pass2_stub_response(text)`: log warning, retry **once** without `tools` / `tool_choice`.
   - If still stub: raise `AnthropicError`.
3. **Observability** (`request_snapshot` → `report_pass`): `pass2_stub_retry`, `pass2_tools_in_request`.

### Stub heuristic (`_is_pass2_stub_response`)

- Known preamble phrases (`emit the structured daily state`, `emit_daily_state`, …), or
- Short response (<500 chars) with no `## ` markdown headings, unless already looks like a full report (`# SPX`, `## Updated Decision Matrix`, workflow headings).

## Cache impact

- **No stub:** Pass 2 still uses tools+system cache prefix from Pass 1 (PR-2 O1 unchanged).
- **Stub retry:** second request omits tools — framework system block may still cache-read; tools prefix not reused on that attempt.

## Tests

`tests/test_anthropic_pass2_stub.py` — stub detection, retry without tools, no retry on valid report, error when stub persists.

## Verification

Re-run 2026-06-10 after fix (2026-06-21):

```bash
SPX_PASS2_IMAGE_OPTIMIZATION=true \
SPX_OUTPUT_DIR=output/ab-test/on-fixed \
SPX_MEMORY_DIR=output/ab-test/memory-on-fixed \
SPX_INCLUDE_MEMORY=false \
python -m src.cli run --date 2026-06-10
```

**Result:** `daily_state` PASS, `report` PASS (`output/ab-test/on-fixed/2026-06-10/`).

| Metric | Pre-fix A/B | Post-fix run |
|--------|-------------|--------------|
| Report validation | FAIL (25 output tokens, stub preamble) | **PASS** |
| Report size | ~80 chars | 17,234 chars |
| Pass 2 output tokens | 25 | 6,891 |
| `pass2_stub_retry` | n/a | `false` (prompt fix sufficient this run; retry path tested in unit tests) |
| Pass 2 charts attached | 11 | 9 |
