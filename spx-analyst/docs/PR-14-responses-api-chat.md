# PR-14: Responses API chat migration

**Status:** Complete  
**Framework version:** `daily-2026-06`  
**Builds on:** [PR-13: Research assistant Phase 4](PR-13-research-assistant-phase4.md)  
**Plan:** [.cursor/plans/responses_api_migration_e43e873d.plan.md](../../.cursor/plans/responses_api_migration_e43e873d.plan.md)

## Summary

Greenfield replacement of the deprecated OpenAI Assistants/Threads chat runtime with **Responses API + Conversations API**. No dual backend, no session backfill — pre-launch rewrite in place.

## Problem / motivation

OpenAI is sunsetting the Assistants API (August 26, 2026). The research assistant had not been operator-tested; this PR migrates before launch rather than maintaining two backends or backfilling thread→conversation mappings.

## Solution

| Deprecated | Replacement |
|---|---|
| `Assistant` + `OPENAI_ASSISTANT_ID` | Inline `instructions=` on each `responses.stream` (`build_additional_instructions()`) |
| `Thread` | `Conversation` via `conversations.create()` |
| `threads.messages.create` + `runs.stream` | Single `responses.stream(..., conversation=, input=, tools=[file_search])` |
| `threads.messages.list` | `conversations.items.list` → `ChatMessageRecord` parsing |
| `threads.delete` | `conversations.delete` |
| `openai_thread_id` in session index | `openai_conversation_id` |

### Architecture

```text
UI / CLI
    → ChatService.stream_reply()
        → build_additional_instructions()   # unchanged preload authority
        → responses.stream(model, conversation, input, instructions, store=True, file_search)
    → memory/chat/sessions.json             # local conversation registry
```

**Unchanged:** `chat_preload.py`, `rag_index.py`, FastAPI SSE contract, Next.js `/assistant` UI.

## Files touched

| File | Change |
|------|--------|
| `src/openai_responses.py` | **New** — `LiveResponsesClient`, `ResponsesClient` protocol, `ChatMessageRecord`, item parsing |
| `src/openai_assistant.py` | **Deleted** |
| `src/chat_service.py` | Wire Responses client; `openai_conversation_id` |
| `src/chat_sessions.py` | `openai_conversation_id` field |
| `src/schemas.py` | Session schema rename |
| `src/config.py` | `OPENAI_CHAT_MODEL` (default `gpt-5`); remove `OPENAI_ASSISTANT_ID` |
| `src/web/chat_api.py` | Import `ChatMessageRecord` |
| `scripts/setup_openai_resources.py` | **New** — vector store only |
| `scripts/setup_openai_assistant.py` | **Deleted** |
| `tests/test_openai_responses.py` | **New** — conversation item → `ChatMessageRecord` parsing |
| `tests/test_web_chat_api.py` | `FakeResponsesClient`; preload in `instructions` |
| `tests/test_chat_sessions.py` | `openai_conversation_id` |
| `pyproject.toml`, `requirements.txt` | `openai>=1.82.0` |
| `.env.example` | `OPENAI_CHAT_MODEL`; remove assistant id |
| `docs/research-assistant-operator-guide.md` | Responses setup flow |
| `README.md` | Env table, setup script, PR-14 link |
| `docs/PR-11-research-assistant-phase2.md` | Superseded note for runtime |

## Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `OPENAI_API_KEY` | — | Required for chat + RAG |
| `OPENAI_VECTOR_STORE_ID` | — | Required for `file_search` at chat + indexing |
| `OPENAI_CHAT_MODEL` | `gpt-5` | Responses model slug |

## Tests / verification

- **253 pytest pass** — includes required `tests/test_openai_responses.py`
- **`npm run build`** — no web changes
- Product contracts preserved: SSE `{"text":...}` + `[DONE]`, session CRUD, refreshable history, failed-send rollback, preload on every turn

## Operator setup (first live test)

```bash
python scripts/setup_openai_resources.py
# paste OPENAI_VECTOR_STORE_ID + OPENAI_CHAT_MODEL into .env
python -m src.cli index-rag --backfill
uvicorn src.web.app:app --host 127.0.0.1 --port 8000
cd web && npm run dev
```

Authority checklist (A1–A4) unchanged — see [operator guide](research-assistant-operator-guide.md).

## Supersedes

[PR-11](PR-11-research-assistant-phase2.md) Assistants/Threads runtime description — historical record only; chat layer is now Responses + Conversations per this PR.
