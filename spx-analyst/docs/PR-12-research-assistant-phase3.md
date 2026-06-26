# PR-12: Research assistant Phase 3 (local UI)

**Status:** Complete — **Phase 3 accepted** (review sign-off + targeted fixes)  
**Framework version:** `daily-2026-06`  
**Builds on:** [PR-11: Research assistant Phase 2](PR-11-research-assistant-phase2.md)  
**Plan:** [.cursor/plans/subscription_chat_assistant_9dcd0913.plan.md](../../.cursor/plans/subscription_chat_assistant_9dcd0913.plan.md)

## Summary

Phase 3 adds the Next.js research assistant UI: `/assistant` with conversation sidebar, streaming message pane, and site-header link. The UI calls existing FastAPI chat routes via the dev proxy (`/api/*` → `127.0.0.1:8000`). No auth, no new backend routes.

## Problem / motivation

Phase 2 proved the chat engine via CLI REPL and FastAPI SSE. Phase 3 delivers the operator-facing workspace described in the plan — secondary to report reading, localhost only.

## Solution

```text
Browser (localhost:3000)
    → Next.js /assistant, /assistant/[sessionId]
    → web/lib/chat-api.ts (fetch + SSE parser)
    → FastAPI /api/chat/* (Phase 2)
    → ChatService → OpenAI Threads
```

### Routes

| Route | Purpose |
|-------|---------|
| `/assistant` | Empty state + session sidebar |
| `/assistant/[sessionId]` | Resume conversation; stream replies |

### UI components

| File | Role |
|------|------|
| `web/lib/chat-api.ts` | Session CRUD, message list, `streamChatMessage()` SSE |
| `web/lib/types.ts` | `ChatSession`, `ChatMessage` |
| `web/components/chat/assistant-workspace.tsx` | Sidebar + messages + composer |
| `web/components/chat/assistant-link.tsx` | Header link to `/assistant` |
| `web/app/(reader)/layout.tsx` | Report reader shell with run sidebar |
| `web/app/assistant/layout.tsx` | Full-width assistant shell (no run sidebar) |
| `web/app/assistant/page.tsx` | Landing |
| `web/app/assistant/[sessionId]/page.tsx` | Deep-link resume |

Removed `chat-panel-placeholder.tsx`; `AssistantLink` wired in reader layout sidebar header.

## Local run

```bash
# terminal 1
cd spx-analyst && uvicorn src.web.app:app --host 127.0.0.1 --port 8000 --reload

# terminal 2
cd spx-analyst/web && npm run dev
```

Open http://localhost:3000/assistant. Requires `OPENAI_API_KEY` and `OPENAI_ASSISTANT_ID` in `spx-analyst/.env`.

## Tests / verification

- **247 Python tests pass** (+1 stream-failure regression test)
- **`npm run build`** — `/assistant` and `/assistant/[sessionId]` compile

Manual E2E (operator):

1. New conversation → ask “what is posture now?” → streaming markdown reply
2. Refresh page → session persists in sidebar
3. Historic question → retrieval-backed answer (when vector store populated)
4. Failed send (e.g. stop FastAPI) → no phantom user message in UI

## Review fixes (same PR)

| Issue | Fix |
|-------|-----|
| Optimistic user message stuck on HTTP/SSE failure | Roll back optimistic bubble in `catch`; SSE errors throw `ApiError` |
| Double sidebar on `/assistant` | Route group: `(reader)/layout` vs `assistant/layout` |
| Raw FastAPI JSON in error UI | `parseErrorDetail()` in `chat-api.ts` |
| No thinking indicator before first token | Assistant bubble with “Thinking…” while streaming |
| `updated_at` bumped on failed stream via auto-title | Auto-title uses `touch_updated_at=False` |
| Assistant link no active state | `usePathname()` highlight on `/assistant` |

## Plan deviations

| Plan | Shipped |
|------|---------|
| `ai` / `@ai-sdk/react` optional | Raw `fetch` + SSE parser in `chat-api.ts` |
| Chat helpers in `web/lib/api.ts` | Separate `web/lib/chat-api.ts` |
| shadcn chat primitives | Existing `Button`, `ScrollArea`, `Separator` + `ReportMarkdown` for assistant replies |

## Non-goals (this PR)

- Auth, subscription gating, cloud deploy
- Rename session UI (PATCH API exists; UI deferred)
- Message pagination
- Live LLM authority compliance tests

## Open follow-ups (unchanged)

- `phase1.1-reindex-cleanup` — delete stale vector files on re-index
- Phase 4 — one-time OpenAI setup guide, full manual E2E checklist doc
- SSE error contract doc for UI consumers

## Next (Phase 4)

See [PR-13: Research assistant Phase 4](PR-13-research-assistant-phase4.md) and the [operator guide](research-assistant-operator-guide.md).
