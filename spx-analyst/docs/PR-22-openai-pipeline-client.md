# PR-22: OpenAI Analytical Pipeline Client

**Status:** Complete  
**Framework version:** `daily-2026-06`  
**Builds on:** [PR-21: Provider Abstraction Layer](PR-21-provider-abstraction-layer.md)

## Summary

Implements `OpenAIPipelineClient` — an `PipelineLLMClient`-conforming sibling to `AnthropicClient`. Uses the **OpenAI Responses API** (`client.responses.create()`). Pass 1 uses Structured Outputs via `text.format: json_schema`. Pass 2 uses standard text generation. Anthropic remains the default; OpenAI is opt-in via `SPX_LLM_PROVIDER=openai`.

## Changes

### New: `src/openai_pipeline_client.py`

**Constructor:**
- Reads `SPX_OPENAI_PIPELINE_MODEL` env var; falls back to `"gpt-5.6-sol"`
- Validates `OPENAI_API_KEY` is set

**API:** Uses `client.responses.create()` (not Chat Completions). System guidance passed via `instructions=` parameter. No message-based system role.

**Pass 1 — `run_structured_state()`:**
- Uses `text={"format": {"type": "json_schema", "name": "emit_daily_state", "schema": ..., "strict": true}}`
- Parses `response.output_text` JSON string into `CallResult.tool_input`
- Same `EmitDailyStateInput` flat schema as Anthropic path — `flat_to_nested` remains unchanged

**Repair pass — `repair_structured_state()`:**
- Same Structured Outputs approach with `DailyState` (nested) schema
- No instructions or images — lightweight correction prompt

**Pass 2 — `run_markdown_report()`:**
- Standard text generation — no `text.format`, no tools
- No stub detection/retry (Claude-specific failure mode)
- Merges `pass2_audit` into request snapshot

**Content blocks (Responses API format):**
- Text: `{"type": "input_text", "text": "..."}`
- Image: `{"type": "input_image", "image_url": "data:image/png;base64,..."}` (string, not a dict)

**Retry:**
- `openai.APIConnectionError` + `openai.RateLimitError` only
- Exponential backoff, max 2 attempts
- No `InternalServerError` retry (add if observed in shadow runs)

**Telemetry:**
- `PassTelemetry` embedded in each `request_snapshot["telemetry"]`
- `request_shape_version` set to `"2.0"` (Responses API)
- Token counts from `response.usage.input_tokens` / `output_tokens`
- Cached tokens from `response.usage.input_tokens_details.cached_tokens` (populated when available; previously null)
- Refusal detected via output item with `type="refusal"`

### Modified: `src/config.py`

Added field:

```python
openai_pipeline_model: str = Field(default="", alias="SPX_OPENAI_PIPELINE_MODEL")
```

Empty default = fallback to `"gpt-5.6-sol"` at client init. `SPX_MODEL` is never read by `OpenAIPipelineClient`.

### Modified: `src/analysis_engine.py`

The `_resolve_pipeline_client` factory now handles both providers:

- `"anthropic"` → `AnthropicClient(settings)`
- `"openai"` → `OpenAIPipelineClient(settings)` (lazy import). Provider-specific `OpenAIPipelineError` from the constructor is caught and wrapped as `RunError` so it propagates consistently through the engine's error handling.

`resolved_provider` in run_log correctly reflects the active provider (`"openai"` when OpenAI is used).

### No changes to

`prompts.py`, `schemas.py`, `state_normalize.py`, `state_enforcement.py`, `validation.py`, `report_assembly.py`, `files.py`, `precompute.py`, `pass2_images.py`, `memory.py`, `cli.py`, `anthropic_client.py`, `web/`

## Env vars

```
SPX_LLM_PROVIDER=openai                          # override default anthropic
SPX_OPENAI_PIPELINE_MODEL=gpt-5.6-sol            # default: gpt-5.6-sol
OPENAI_API_KEY=sk-...                            # required (was already needed for chat/RAG)
```

## Tests

### New: `tests/test_openai_pipeline_client.py` (17 tests)

| Test | What it verifies |
|------|-----------------|
| `test_uses_env_var_when_set` | `SPX_OPENAI_PIPELINE_MODEL` overrides default |
| `test_defaults_when_env_var_unset` | Falls back to `"gpt-5.6-sol"` |
| `test_returns_call_result_with_parsed_json` | Pass 1 returns parsed JSON as `tool_input` |
| `test_telemetry_includes_cached_tokens` | `cache_read_tokens` populated from `input_tokens_details.cached_tokens` |
| `test_raises_on_invalid_json` | Pass 1 errors on malformed response |
| `test_handles_trailing_text_after_json` | Parses JSON with extra text appended |
| `test_raises_on_empty_output_text` | Pass 1 errors on blank `output_text` |
| `test_raises_on_refusal` | Pass 1 detects refusal in output items |
| `test_raises_on_no_output` | Pass 1 errors on empty `output` list |
| `test_text_only_path_works` | Text-only (no images) produces correct snapshot |
| `test_returns_fixed_state` | Repair pass returns corrected state |
| `test_returns_prose` | Pass 2 returns markdown text |
| `test_empty_image_list` | Text-only path reports `image_count=0` |
| `test_passes_pass2_audit` | Audit dict merged into snapshot |
| `test_raises_on_refusal` (Pass 2) | Pass 2 detects refusal in output items |
| `test_raises_on_blank_output` (Pass 2) | Pass 2 errors on blank `output_text` |
| `test_raises_on_empty_key` | Constructor validates API key |

### Modified: `tests/test_provider_resolution.py`

- Replaced `test_openai_raises_not_available` with `test_resolves_openai` (verifies `OpenAIPipelineClient` is returned)
- Added `test_case_insensitive_openai_resolution`

```bash
# Full suite
pytest -q
```

387 passed, 1 pre-existing failure (`test_live_memory_budget_caps` — unrelated).

## Usage

```bash
# Default: Anthropic (unchanged)
python -m src.cli run --date 2026-07-09

# OpenAI opt-in
SPX_LLM_PROVIDER=openai python -m src.cli run --date 2026-07-09
```

## Live smoke test

Run against `2026-07-08` (15 charts, 5.5K SPX close) using `gpt-5.5` via Responses API.

| Metric | State pass | Report pass |
|--------|-----------|-------------|
| Status | Validated | Validated |
| Input tokens | 22,639 | 21,785 |
| Output tokens | 6,555 | 2,728 |
| Cached tokens | 20,224 | 0 |
| Latency | 71s | 56s |
| Images | 15 | 10 |
| Recommended action | — | Patience / tactical trim bias |

Both passes produced valid `DailyState` and assembled report. All output artifacts present in `output/2026-07-08/`. The structured-output schema now forces all properties as `required` (OpenAI strict-mode requirement), with `_parse_json_response()` handling trailing text from the model.

## Production readiness

Anthropic remains the default. OpenAI is available-but-not-default until shadow-run validation is complete (see PR-22 plan for success criteria). Use `SPX_LLM_PROVIDER=openai` for evaluation.

## Out of scope

- CLI `--provider` flag (future)
- Shadow-run comparison tooling (future)
- Changing prompts, schemas, normalization, enforcement, validation, or assembly
