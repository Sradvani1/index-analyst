# PR-11: Research assistant Phase 2 (chat engine)

**Status:** Complete — **Phase 2 accepted** (review sign-off + targeted fixes)  
**Superseded (runtime):** Chat OpenAI layer replaced by [PR-14: Responses API chat](PR-14-responses-api-chat.md) — this doc remains the historical Phase 2 record.  
**Framework version:** `daily-2026-06`  
**Builds on:** [PR-10: Research assistant Phase 1](PR-10-research-assistant-phase1.md)  
**Plan:** [.cursor/plans/subscription_chat_assistant_9dcd0913.plan.md](../../.cursor/plans/subscription_chat_assistant_9dcd0913.plan.md)

## Summary

Phase 2 wires the OpenAI Assistants runtime: local session index (`memory/chat/sessions.json`), thread lifecycle, preload injection on every message, FastAPI SSE chat routes, and an interactive CLI REPL. Every Assistants run receives `build_additional_instructions()` (latest `DailyState` matrix + rolling summary + static instructions).

## Problem / motivation

Phase 1 established preload authority and section-vector RAG but had no conversation runtime. Phase 2 adds Threads-backed chat without UI — proving the authority model works end-to-end before the Next.js assistant page.

## Solution

```text
CLI / FastAPI
    → ChatService.stream_reply()
        → build_additional_instructions()   # Phase 1 preload
        → threads.messages.create(user)
        → runs.stream(assistant_id, additional_instructions=…)
    → memory/chat/sessions.json             # local thread registry
```

### Session store

`memory/chat/sessions.json` — UUID → `openai_thread_id`, title, timestamps. Atomic write (temp + rename). Gitignored under `memory/chat/`.

### FastAPI routes

| Route | Purpose |
|-------|---------|
| `GET /api/chat/sessions` | List sessions (newest `updated_at` first) |
| `POST /api/chat/sessions` | Create OpenAI thread + local row |
| `GET /api/chat/sessions/{id}/messages` | Proxy thread messages |
| `PATCH /api/chat/sessions/{id}` | Rename title |
| `DELETE /api/chat/sessions/{id}` | Delete local row + OpenAI thread |
| `POST /api/chat/sessions/{id}/messages` | SSE stream (`data: {"text": "..."}` → `[DONE]`) |

Next.js dev proxy forwards `/api/*` to `127.0.0.1:8000` (unchanged).

## Code changes

| Module | Change |
|--------|--------|
| `src/openai_assistant.py` | **New** — `LiveAssistantClient`, `AssistantClient` protocol, streamed runs |
| `src/chat_sessions.py` | **New** — CRUD + atomic persist |
| `src/chat_service.py` | **Rewritten** — orchestration, auto-title, `get_chat_service()` |
| `src/schemas.py` | `ChatSessionRecord`, `ChatSessionIndex` |
| `src/config.py` | `chat_dir` |
| `src/web/chat_api.py` | **New** — chat router + SSE |
| `src/web/app.py` | Include chat router; CORS for write methods |
| `src/web/models.py` | Chat request/response DTOs |
| `src/cli.py` | Interactive `chat` REPL; `--session-id` resume |
| `.gitignore` | `memory/chat/` |
| `tests/test_chat_sessions.py` | **New** — 7 tests |
| `tests/test_web_chat_api.py` | **New** — 7 tests |

## CLI

```bash
python -m src.cli chat
python -m src.cli chat --session-id <uuid>
```

Requires `OPENAI_API_KEY` and `OPENAI_ASSISTANT_ID` in `.env`.

## Tests / verification

**246 tests pass** (+14 Phase 2 tests).

Exit gate: CLI REPL + FastAPI SSE with mocked OpenAI — **passed**.

## Review fixes (same PR)

| Issue | Fix |
|-------|-----|
| POST message pre-check called OpenAI `list_messages` | Use local `get_session()` only |
| `updated_at` bumped on failed stream | `touch_session` only after successful stream |

## Plan deviations

| Plan | Shipped |
|------|---------|
| Chat routes in `app.py` | Separate `web/chat_api.py` router included in `app` |
| `ChatSessionContext` removed from `ChatService` | Service uses preload + OpenAI only; deprecated `load_chat_context()` unchanged |

## Open follow-ups (not blocking Phase 3)

- Message list pagination (long threads)
- SSE error event + `[DONE]` contract doc for UI consumers
- `phase1.1-reindex-cleanup` — delete stale vector files on re-index

## Next (Phase 3)

See [PR-12: Research assistant Phase 3](PR-12-research-assistant-phase3.md).

## Non-goals (this PR)

- Next.js `/assistant` UI — shipped in PR-12
- Live LLM authority compliance tests
- Message pagination
