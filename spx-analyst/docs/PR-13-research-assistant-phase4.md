# PR-13: Research assistant Phase 4 (operator docs)

**Status:** Complete — **Phase 4 accepted**  
**Framework version:** `daily-2026-06`  
**Builds on:** [PR-12: Research assistant Phase 3](PR-12-research-assistant-phase3.md)  
**Plan:** [.cursor/plans/subscription_chat_assistant_9dcd0913.plan.md](../../.cursor/plans/subscription_chat_assistant_9dcd0913.plan.md)

## Summary

Phase 4 delivers operator-facing documentation for the research assistant: a one-time OpenAI setup guide with an optional setup script, `.env` reference updates, manual E2E checklist (platform + authority), troubleshooting, and SSE contract notes. No new runtime features.

## Problem / motivation

Phases 1–3 shipped preload, RAG indexing, chat engine, and UI. Operators still needed a single walkthrough to create OpenAI resources, backfill the vector index, start local servers, and verify authority behavior with live LLM replies.

## Solution

| Deliverable | Path |
|-------------|------|
| Operator guide (setup + E2E + troubleshooting) | [`docs/research-assistant-operator-guide.md`](research-assistant-operator-guide.md) |
| One-time setup script | [`scripts/setup_openai_assistant.py`](../scripts/setup_openai_assistant.py) |
| Env template comments | [`.env.example`](../.env.example) |
| README cross-links | [`README.md`](../README.md) |

### Setup flow (operator)

```text
scripts/setup_openai_assistant.py  →  paste ids into .env
index-rag --backfill               →  memory/rag/{date}.json manifests
uvicorn + npm run dev              →  /assistant
Manual E2E checklist               →  authority sign-off (A1–A4)
```

## Files touched

| File | Change |
|------|--------|
| `docs/research-assistant-operator-guide.md` | **New** — full operator guide |
| `scripts/setup_openai_assistant.py` | **New** — vector store + assistant creation |
| `docs/PR-13-research-assistant-phase4.md` | **New** — this record |
| `.env.example` | OpenAI section comments + optional instructions path |
| `README.md` | PR-13 link, research assistant section, routes table |
| `.cursor/plans/subscription_chat_assistant_9dcd0913.plan.md` | Phase 4 complete |

## Tests / verification

- Setup script is operator-run (requires live `OPENAI_API_KEY`); not in CI
- **247 pytest pass** — no engine changes
- Operator follows guide for live E2E (checklist sections P1–P8, A1–A4)

## Acceptance criteria (Phase 4)

- [x] One-time OpenAI setup steps documented (script + Platform UI fallback)
- [x] `.env.example` lists all three OpenAI vars with purpose
- [x] Local run commands (`uvicorn`, `npm run dev`, CLI chat)
- [x] Manual E2E checklist with authority verification (A1–A4)
- [x] Index retry + troubleshooting documented
- [x] SSE contract documented for UI consumers

## Non-goals (this PR)

- Automated live LLM tests in CI
- `phase1.1-reindex-cleanup` (stale vector file deletion)
- Rename session UI, message pagination

## Operator next step

Follow [`research-assistant-operator-guide.md`](research-assistant-operator-guide.md) Steps 1–5 and complete checklist **A1–A4** for authority sign-off.
