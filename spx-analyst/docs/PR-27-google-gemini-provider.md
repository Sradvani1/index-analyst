# PR-27: Google Gemini Analytical Pipeline Provider

**Status:** Complete

## Summary

Adds Google AI Studio's Gemini Developer API as a third selectable provider for
the two-pass analytical pipeline. Anthropic and OpenAI remain unchanged and
the engine continues to depend only on the provider-neutral
`PipelineLLMClient` protocol.

## Configuration

```env
SPX_LLM_PROVIDER=google
GOOGLE_API_KEY=AIza...
SPX_GOOGLE_PIPELINE_MODEL=gemini-3.7-flash
SPX_GOOGLE_STATE_THINKING_LEVEL=HIGH
SPX_GOOGLE_MAX_OUTPUT_TOKENS=16000
SPX_GOOGLE_SUBSTACK_MAX_OUTPUT_TOKENS=8000
```

The daily runner already loads `.env`, so changing `SPX_LLM_PROVIDER` changes
the provider without changing prompts, schemas, chart handling, validation, or
report assembly.

For isolated comparisons, set `SPX_OUTPUT_DIR` and `SPX_MEMORY_DIR` to shadow
directories so the comparison report does not overwrite production artifacts.

## Implementation

- Added `GooglePipelineClient` using the official `google-genai` SDK.
- Uses Gemini `generate_content` with `system_instruction`, inline image
  parts, and text parts.
- Uses Gemini structured output with the existing `EmitDailyStateInput` and
  `DailyState` Pydantic schemas for state and repair passes.
- Normalizes Gemini token usage into `PassTelemetry`.
- Added transient retry handling for rate-limit and temporary server failures.
- Added configurable Gemini thinking levels and a separate output budget so
  high thinking does not truncate structured state output.
- Pass 1 and Pass 2 can override the shared thinking level independently.
- Added mocked SDK tests and provider-resolution coverage.

## Scope

This adds Google to the analytical and Substack pipelines. The optional OpenAI
Responses chat assistant remains available without vector-store retrieval.
