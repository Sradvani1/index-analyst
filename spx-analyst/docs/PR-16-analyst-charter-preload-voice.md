# PR-16: Analyst charter + preload voice

**Status:** Implementation complete — operator sign-off pending (AC-4, AC-5)  
**Framework version:** `daily-2026-06`  
**Builds on:** [PR-10](PR-10-research-assistant-phase1.md) · [PR-15](PR-15-compact-chat-preload.md)  
**Plan:** [.cursor/plans/analyst_charter_preload_c40de7c6.plan.md](../../.cursor/plans/analyst_charter_preload_c40de7c6.plan.md)

## Summary

Upgrade Block 1 from authority policy to **analyst charter** (identity, stance, collaborative reasoning) without changing preload architecture, vector-store scope, or authority order. Align Blocks 2–3 **rendering** so every turn reads as one house-analyst voice. **Follow-up:** expanded preload caps per [PR-15](PR-15-compact-chat-preload.md) for richer market dialogue (6,500 total budget).

**Payload (2026-06-25 live memory):** PR-15 baseline **4,402 chars** → PR-16 voice **4,016 chars** (tighter caps) → **5,388 chars** (expanded caps, current). All observed totals pass the active layer caps and 6,500 total budget.

Measured per layer (expanded caps): Constitution 1,655 · current house view 1,930 · recent arc 1,799.

## Problem / motivation

[PR-15](PR-15-compact-chat-preload.md) fixed authority separation and compact serialization. PR-16 closed the **voice** gap. Expanded caps address **truncation headroom** on busy runs (arc was 1 char under cap at 1,200) without changing routing or retrieval.

## Solution

Serialization and rendering only — no routing, schema authority order, or RAG changes:

```text
every turn (unchanged shape) =
  analyst charter (Constitution, 2,000 cap)
  + current house view      (2,100 cap — prose + matrix + dialogue bullets)
  + recent arc              (1,800 cap — sessions + inflection + still open)
  + file_search             (always enabled)
```

### Block 1 — Constitution

Analyst charter in `framework/chat-assistant-instructions.md` (≤2,000 chars). Authority ordering unchanged.

### Block 2 — Current house view

Prose opening (≤220 chars), setup/tension (≤260), six-row matrix, what shifted (4×160), triggers (5×100), what changes the view (3×110 from `open_questions`).

### Block 3 — Recent arc

Up to 8 session snapshots (110-char fragments), inflection bullets (3×130), still-open bullets (3×140). No `recent_summary.md` replay.

## Code changes

| Module | Change |
|--------|--------|
| `src/schemas.py` | Expanded `*Caps`; `CurrentBrief` + `ArcBrief` dialogue fields |
| `src/formatting.py` | `format_event_headline()` |
| `src/chat_preload.py` | Build/render current house view sections |
| `src/memory.py` | Still-open + inflection bullets; shared question selection |
| `framework/chat-assistant-instructions.md` | Analyst charter |
| Tests + docs | Caps 6,500; forbidden-content guards unchanged |

**Unchanged:** `chat_service.py`, `rag_index.py`, vector-store scope, `file_search` routing, authority stack.

## Documentation changes

| Document | Updated | What changed |
|----------|---------|--------------|
| [research-assistant-operator-guide.md](research-assistant-operator-guide.md) | **Yes** | PR-15 three-layer preload contract; analyst charter; **A5** added |
| [PR-15-compact-chat-preload.md](PR-15-compact-chat-preload.md) | **Yes** | Expanded cap table + measured sample |
| [chat-api-payload-example-2026-06-25.md](chat-api-payload-example-2026-06-25.md) | **Yes — regenerated** | Live memory under expanded caps |

## Acceptance criteria

- [x] **AC-1** Constitution ≤2,000 chars, no truncation
- [x] **AC-2** Current house view ≤2,100; recent arc ≤1,800 on 2026-06-25 live memory
- [x] **AC-3** Total `additional_instructions` ≤6,500
- [ ] **AC-4** Authority A1–A3 — manual operator sign-off
- [ ] **AC-5** Collaborative reasoning A5 — manual operator sign-off
- [x] **AC-6** No routing/RAG/authority-order changes; forbidden-content guards pass

## Verification

```bash
cd spx-analyst
pytest tests/test_chat_preload.py tests/test_arc_brief.py tests/test_web_chat_api.py -q
```

**Handoff links**

- Preload contract + caps: [PR-15-compact-chat-preload.md](PR-15-compact-chat-preload.md)
- Measured payload: [chat-api-payload-example-2026-06-25.md](chat-api-payload-example-2026-06-25.md)
- Operator checklist (A1–A5): [research-assistant-operator-guide.md](research-assistant-operator-guide.md)
