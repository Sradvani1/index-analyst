# PR-10: Research assistant Phase 1 (RAG + preload)

**Status:** Complete — **Phase 1 accepted** (review sign-off)
**Framework version:** `daily-2026-06`  
**Builds on:** [PR-7: Pass 2 investor report template](PR-7-pass2-investor-report-template.md) · [PR-3: Memory rollup overhaul](PR-3-memory-rollup-overhaul.md)  
**Plan:** [.cursor/plans/subscription_chat_assistant_9dcd0913.plan.md](../../.cursor/plans/subscription_chat_assistant_9dcd0913.plan.md)

## Summary

Phase 1 of the local SPX research assistant: deterministic **latest-run preload** (authority-ordered instructions + structured `DailyState` + rolling summary) and **section-vector RAG indexing** (one OpenAI file per investor report section, manifest in `memory/rag/`). Python only — no Threads, no FastAPI chat routes, no UI.

Every successful `run` now ends with RAG indexing after memory is saved. Index failure is a hard `fail_run` with a copy-paste stderr retry command. Preload matrix authority comes **only** from `memory/daily_states/{latest}-state.json`; same-date report markdown is validate/warn only.

## Problem / motivation

The daily engine produces canonical artifacts in `memory/`, but there is no structured contract for a conversational layer to answer “what is posture now?” without re-parsing reports or risking parallel interpretation. Historical comparison needs retrieval over report prose without uploading `state.json` or treating report markdown as the authoritative matrix.

Phase 1 establishes the authority stack in code and indexes report sections for future `file_search` — without building chat runtime yet.

## Solution

```text
memory/daily_states/{latest}-state.json
        │
        ▼
chat_preload.build_additional_instructions()
  ├── framework/chat-assistant-instructions.md
  ├── LatestRunState block (matrix rows from DailyState only)
  └── rolling/recent_summary.md

memory/daily_reports/{date}-analysis.md
        │
        ▼
rag_index.index_report_rag()  →  OpenAI Vector Store (9 sections)
                              →  memory/rag/{date}.json
```

### Authority stack (preload)

| Priority | Source | Phase 1 use |
|----------|--------|-------------|
| 1 | Latest `DailyState` JSON | `LatestRunState` — matrix rows, bias, action, Monte Carlo summary |
| 2 | Same-date report prose | **Not** loaded into preload; optional warn-only validation |
| 3 | `rolling/recent_summary.md` | Injected into `additional_instructions` |
| 4 | Vector sections | Indexed only; retrieval is Phase 2 |

**Rule:** Present-tense posture answers come from preload only, never retrieval alone.

### Matrix source

- `LatestRunState.decision_matrix` is a typed copy of `DailyState.decision_matrix` (same `DecisionMatrixRow` model).
- `recommended_action` derived via `DecisionMatrix.recommended_action` property.
- Preload serializes structured rows (markdown table + JSON); never injects rendered report matrix markdown.

### RAG indexing

- Split assembled report on `INVESTOR_REPORT_SECTIONS` (9 sections).
- One upload per section with YAML preamble (`report_date`, `section`, `source`).
- Manifest: `memory/rag/{date}.json` — atomic write (temp + rename).
- `state.json` is **not** uploaded.

### Index failure (operator recovery)

On failure after a successful analysis save:

```text
ERROR: RAG indexing failed for 2026-06-25 (report saved to memory/).
Retry: python -m src.cli index-rag --date 2026-06-25
```

Memory stays fresh; only the vector store lags until manual retry.

## Code changes

| Module | Change |
|--------|--------|
| `src/schemas.py` | **New** — `MonteCarloSummary`, `LatestRunState`, `ChatPreloadContext` |
| `src/chat_preload.py` | **New** — latest-run load, `build_latest_run_block()`, `build_additional_instructions()`, optional report-matrix validation, `answer_posture_from_preload()` canary |
| `src/rag_index.py` | **New** — section split, OpenAI upload, manifest, `index_rag_or_fail()`, CLI backfill |
| `src/chat_context.py` | Thin wrapper — `load_chat_preload()`; `load_chat_context()` deprecated |
| `src/analysis_engine.py` | Post-run hook: `index_rag_or_fail()` after `rebuild_rolling_summary()` |
| `src/migrate_perplexity.py` | Conditional RAG hook when report has all investor sections |
| `src/cli.py` | **New** — `index-rag --date`, `--backfill` |
| `src/config.py` | OpenAI env vars; `rag_dir`, `chat_assistant_instructions_path` |
| `framework/chat-assistant-instructions.md` | **New** — authority stack, citation rule, behavior |
| `pyproject.toml`, `requirements.txt` | `openai>=1.40.0` |
| `.env.example` | OpenAI vars |
| `README.md` | OpenAI required for `run`, `index-rag` commands, config table |
| `tests/test_chat_preload.py` | **New** — 8 tests including posture canary |
| `tests/test_rag_index.py` | **New** — 7 tests |
| `tests/test_engine.py` | Autouse RAG mock; `test_rag_index_failure_emits_retry_hint` |

**Not changed (Phase 2+):** `openai_assistant.py`, `chat_sessions.py`, `chat_service.py` (stub), FastAPI chat routes, Next.js `/assistant`.

## CLI

```bash
# Automatic after every successful run (requires OPENAI_API_KEY + OPENAI_VECTOR_STORE_ID)

# Manual retry / backfill
python -m src.cli index-rag --date 2026-06-25
python -m src.cli index-rag --backfill
```

## Configuration

Set in `spx-analyst/.env`:

| Variable | Phase 1 required | Purpose |
|----------|------------------|---------|
| `OPENAI_API_KEY` | Yes (for `run` indexing) | Upload sections to vector store |
| `OPENAI_VECTOR_STORE_ID` | Yes (for `run` indexing) | Target vector store |
| `OPENAI_ASSISTANT_ID` | No (Phase 2 chat) | Reserved for Assistants API |

Optional path override: `SPX_CHAT_ASSISTANT_INSTRUCTIONS_PATH` (default `framework/chat-assistant-instructions.md`).

## Tests / verification

```bash
cd spx-analyst && pytest
```

**232 tests pass** (13 new Phase 1 tests).

| Test file | Coverage |
|-----------|----------|
| `test_chat_preload.py` | Matrix from `DailyState` only; latest-run date selection; preload assembly; report validation warn-only; **posture canary** without retrieval |
| `test_rag_index.py` | Nine-section split; manifest write; missing report/section errors; backfill; upload error → `RagIndexError`; `index_rag_or_fail` stderr retry |
| `test_engine.py` | RAG mocked by default; failure test asserts stderr retry hint |

**Exit gate (plan):** preload-only posture canary — `answer_posture_from_preload()` answers from `LatestRunState` without vector retrieval. **Passed.**

## Acceptance criteria (Phase 1)

### Authority
- [x] `LatestRunState.decision_matrix.rows` sourced only from `DailyState` JSON
- [x] Every preload run injects instructions + latest-run block + rolling summary
- [x] Preload-only canary: posture answerable without retrieval
- [x] Same-date report = optional validate/warn; never preload matrix source
- [ ] Current-view LLM replies name `latest_run_date` and cite matrix rows — **Phase 2** (instructions + preload ready)
- [ ] Refuses to override recommended action — **Phase 2** (instructions ready)

### Platform / indexing
- [x] Index failure: stderr shows copy-paste `index-rag --date` retry
- [x] Retry command documented in README
- [x] `index-rag --date` and `--backfill` CLI
- [ ] Chat UI, Threads, sessions — **Phase 2–3**

## Plan deviations

| Plan | Shipped | Rationale |
|------|---------|-----------|
| Hook only in `analysis_engine.py` | **`index_rag_or_fail()`** shared helper; also called from `migrate_perplexity.py` when report has all 9 investor sections | Migration saves to memory; index when indexable; skip legacy-format reports with warning |
| Deprecate `ChatSessionContext` schema | **`load_chat_context()` deprecated**; schema kept for Phase 2 `ChatService` stub | Avoid breaking stub; migrate to `load_chat_preload()` in Phase 2 |
| Index failure catch in engine only | **`index_rag_or_fail()`** centralizes stderr emit + re-raise | Single operator recovery path for engine and CLI |
| — | **OpenAI upload errors wrapped as `RagIndexError`** | Review fix: network/API failures get stderr retry hint, not raw tracebacks |
| — | **`answer_posture_from_preload()`** test helper | Explicit exit-gate canary without mocking LLM |
| Re-index replaces vector files | **Re-index is additive** (new files uploaded; old IDs not deleted) | **Open follow-up** — Phase 1.1; local manifest is latest truth; vector store can accumulate stale duplicates |
| Phase 4 docs | **Partial in this PR:** README + `.env.example` | Full one-time OpenAI setup guide remains Phase 4 |
| `run_log.index_rag` audit field | **Not added** | Plan marked optional; stderr retry is v1 notification |

## Operator notes

1. Create OpenAI Vector Store (`max_chunk_size_tokens: 1024` recommended).
2. Set `OPENAI_API_KEY` and `OPENAI_VECTOR_STORE_ID` in `.env` before first post-PR-10 `run`.
3. Backfill existing memory: `python -m src.cli index-rag --backfill`.
4. If `run` fails at indexing, memory is already saved — paste the stderr retry command.

**Breaking change:** `python -m src.cli run` now requires OpenAI indexing credentials. Analysis completes and persists before indexing; only the index step fails if keys are missing.

## Non-goals (this PR)

- OpenAI Threads, Assistants runs, chat REPL
- FastAPI `/api/chat/*` routes
- Next.js `/assistant` UI
- `memory/chat/sessions.json`
- Supabase, Stripe, auth, cloud deploy
- Deleting stale vector files on re-index

## Review sign-off

Phase 1 accepted. Matrix authority resolves cleanly: `LatestRunState.decision_matrix` from structured `DailyState`, `recommended_action` derived from that object, same-date report markdown validate-only. Preload-only posture canary passed.

Documented deviations (`index_rag_or_fail()` shared helper, deprecated `load_chat_context()` with schema retained) are appropriate for staged rollout. **Do not reopen Phase 1 scope.**

**Open follow-up (not blocking Phase 2):** additive re-index cleanup — delete prior vector store file IDs from `memory/rag/{date}.json` before re-upload. Plan todo: `phase1.1-reindex-cleanup`.

## Next (Phase 2)

- `openai_assistant.py`, `chat_sessions.py`, `chat_service.py`
- FastAPI SSE chat routes
- CLI interactive `chat` REPL (exit gate before UI)
- Wire `load_chat_preload()` into Assistants `additional_instructions`
