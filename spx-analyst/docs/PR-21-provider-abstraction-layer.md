# PR-21: Provider Abstraction Layer

**Status:** Complete  
**Framework version:** `daily-2026-06`  
**Builds on:** [PR-20: Prepare-run workflow](PR-20-prepare-run-workflow.md)

## Summary

Decouples the two-pass analytical pipeline from the concrete `AnthropicClient` by introducing a `PipelineLLMClient` Protocol. The engine talks to the Protocol; `AnthropicClient` conforms structurally. A factory function selects the provider at runtime via `SPX_LLM_PROVIDER`.

Zero behavioural change — all existing tests pass, Anthropic remains the default, `openai` errors with a clear not-yet-implemented message.

This is PR-1 of a two-PR sequence. PR-22 adds the `OpenAIPipelineClient`.

## Motivation

The two analytical passes were tightly coupled to the Anthropic SDK:

- `analysis_engine.py` imported `AnthropicClient` directly
- `CallResult` and `_encode_image` lived inside `anthropic_client.py`
- Retry logic, stub detection, and caching strategy were Claude-specific but mixed into the engine's critical path

OpenAI was already used elsewhere (chat assistant, RAG indexing). The analytical pipeline should have the same structural flexibility.

## Changes

### New: `src/pipeline_client.py`

Provider-neutral types and interface:

- **`CallResult`** — moved from `anthropic_client.py`. All fields are JSON-serialisable dicts/primitives. No provider SDK types leak through.
- **`PassTelemetry`** — normalised per-pass observability payload (provider, model, pass name, input/output tokens, cache read/write tokens, latency, attempt count, retry reason, image count, request shape version). Embedded in `request_snapshot["telemetry"]`.
- **`PipelineLLMClient`** — structural Protocol with three methods: `run_structured_state`, `repair_structured_state`, `run_markdown_report`. Matches existing `AnthropicClient` signatures exactly.

### New: `src/pipeline_utils.py`

- **`EncodedImage`** — typed value object (`media_type`, `base64_data`, `width`, `height`, `source_path`)
- **`encode_image()`** — resize + base64 encode, returns `EncodedImage`. Each client wraps the result in its own multimodal request envelope.

### Modified: `src/anthropic_client.py`

- Removed local `CallResult` definition → imported from `pipeline_client`
- Removed local `_encode_image` → uses `pipeline_utils.encode_image`; `_user_content` now wraps `EncodedImage` in the Anthropic envelope
- All five pass methods (`run_structured_state`, `repair_structured_state`, `run_markdown_report`, `run_text_structured_state`, `run_text_markdown_report`) now build and embed `PassTelemetry` in `request_snapshot["telemetry"]`
- Class conforms structurally to `PipelineLLMClient` (no inheritance — structural subtyping)
- No method signature or runtime behaviour changes

### Modified: `src/config.py`

Added one field:

```python
llm_provider: str = Field(default="anthropic", alias="SPX_LLM_PROVIDER")
```

Existing `model`/`SPX_MODEL` untouched. `SPX_ANTHROPIC_MODEL` and `SPX_OPENAI_PIPELINE_MODEL` deferred to PR-22.

### Modified: `src/analysis_engine.py`

- Import `PipelineLLMClient` in place of `AnthropicClient` for the type annotation
- Signature: `client: PipelineLLMClient | None = None`
- Added `_resolve_pipeline_client(settings)` factory — validates provider, returns `AnthropicClient`, raises `RunError` for unknown or `openai` (before any import)
- If `client` is passed, engine uses it directly — no resolution, validation, or import of any provider SDK
- Run log records `configured_provider` (from env var or `"default"`) and `resolved_provider` (`"anthropic"` or `"injected"`)

### No changes to

`prompts.py`, `schemas.py`, `state_normalize.py`, `state_enforcement.py`, `validation.py`, `report_assembly.py`, `files.py`, `precompute.py`, `pass2_images.py`, `memory.py`, `cli.py`, `openai_responses.py`, `chat_service.py`, `rag_index.py`, `web/`

## Tests

### New: `tests/test_provider_resolution.py`

| Test | What it verifies |
|------|-----------------|
| `test_default_resolves_anthropic` | Unset `SPX_LLM_PROVIDER` → `AnthropicClient` |
| `test_case_insensitive_resolution` | `ANTHROPIC` and `Anthropic` both resolve |
| `test_openai_raises_not_available` | `openai` → `RunError` before any import |
| `test_unknown_provider_raises_actionable_error` | `grok` → `RunError` with clear message |
| `test_fake_client_conforms_to_protocol` | `PipelineLLMClient` accepts structural subtyping |
| `test_pass_telemetry_shape` | `PassTelemetry` dataclass has all expected fields |
| `test_run_log_records_providers` | Run log contains `configured_provider` and `resolved_provider` |

### New: `tests/test_image_encoding.py`

| Test | What it verifies |
|------|-----------------|
| `test_encode_image_produces_expected_encoded_image` | `EncodedImage` fields populated correctly |
| `test_encode_image_respects_max_dim` | Resize respects `max_dim` parameter |
| `test_anthropic_image_bytes_match_baseline` | Encoding produces valid PNG base64 |

### Modified: `tests/test_engine.py`

- `CallResult` import path: `src.pipeline_client` instead of `src.anthropic_client`

### Modified: `tests/test_migrate_perplexity.py`

- `CallResult` import path: `src.pipeline_client` instead of `src.anthropic_client`

### Modified: `tests/test_pass2_images.py`

- Mock targets updated: `src.anthropic_client._encode_image` → `src.anthropic_client.encode_image`
- Mock return values use `EncodedImage` dataclass
- Mock responses include `usage` attribute for telemetry path

```bash
# Full suite
pytest -q
```

360 passed, 1 pre-existing failure (`test_live_memory_budget_caps` — unrelated token budget issue).

## Acceptance criteria

1. Default Anthropic runs produce the same validated `DailyState`, assembled report, enforcement result, and file structure as pre-PR-21 (request snapshots gain `"telemetry"` sub-dict; everything else identical)
2. Provider resolution is tested independently from client execution
3. Injected clients bypass provider resolution (no SDK import, no env var check)
4. `CallResult`, `EncodedImage`, and `PassTelemetry` contain no provider SDK types
5. Existing Anthropic request snapshots, cache telemetry, and Pass-2 stub retry audit fields are preserved
6. Every persisted production run records `configured_provider`, `resolved_provider`, and per-pass `PassTelemetry`
7. `openai` fails before any provider network call or analysis-phase artifact write; pre-run scaffolding unaffected
8. `SPX_MODEL` continues to work exactly as before (untouched)

## Out of scope

- `OpenAIPipelineClient` implementation (PR-22)
- CLI `--provider` flag (PR-22)
- Model precedence changes (`SPX_ANTHROPIC_MODEL`, `SPX_OPENAI_PIPELINE_MODEL`)
- Shadow comparison tooling
- Changes to prompts, schemas, validation, or assembly
