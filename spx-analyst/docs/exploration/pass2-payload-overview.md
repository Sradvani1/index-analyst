# Pass 2 API payload — structure overview

Generated from a real **2026-06-29** run (`build_report_prompt` + production framework/role files).

This document explains **where each instruction lives** in the Anthropic Messages API call. Tone/readability rules today are **not** in a separate “style system prompt” — they sit in the **user message body** under `## Task`.

---

## Answer: what goes in the system prompt?

Pass 2 sends **two system text blocks** (see `anthropic_client._system_blocks`):

| Block | Source | Chars (2026-06-29) | Cached? |
|-------|--------|-------------------|---------|
| **System block 1** | `SPX-Claude-Role-Block.md` + `HARD_CONSTRAINTS` via `load_system_role()` | ~2,204 | No |
| **System block 2** | Full `SPX-Daily-Analysis-Framework.md` via `files.load_framework()` | ~16,645 | Yes (`ephemeral`) |

**Not in system today:** section list, word budgets, investor tone, conflict checklist, validated state JSON, chart pack, or the Pass 2 task block. Those are in the **user message text** (`build_report_prompt()` → `bundle.body`).

---

## Full API shape (Pass 2)

```
POST messages.create
├── model: settings.model (e.g. claude-opus-4-8)
├── max_tokens: settings.max_output_tokens
├── system: [ block_1_role+constraints, block_2_framework_cached ]
├── tools: [ emit_daily_state ]          # same tool as Pass 1 (cache prefix reuse)
├── tool_choice: { type: "none" }        # prose only; no tool call
└── messages:
    └── role: user
        └── content:
            ├── image/png (01_spx_intraday.png)      # resized, base64
            ├── image/png (02_spx_5day.png)
            ├── … (9 attached charts total)
            └── text: bundle.body                    # ~23k chars for 2026-06-29
```

**On stub retry:** same payload but **tools omitted entirely** (see `run_markdown_report`).

**Images:** 9 attached for 2026-06-29 (not all 15 charts). Reference-only charts appear as filenames in text only.

Approximate text payload: **~42k chars** (system + body), plus ~7k chars tool schema, plus image tokens.

---

## Where tone instructions would be injected

| Option | Location | Cache impact | Recommendation |
|--------|----------|--------------|----------------|
| **A — Task block expansion** | User body `## Task` in `build_report_prompt()` | None | **Preferred** — already home of tone/word budgets |
| **B — Pass-2 role addendum** | Append to system block 1 (or new block 3) | Breaks Pass 1/2 system prefix if block 3 added | Use only if system-level voice is needed |
| **C — Trim framework for Pass 2** | Replace system block 2 with excerpt | Breaks cache sharing with Pass 1 | High leverage but needs A/B testing |
| **D — Third LLM pass** | New call after assembly | N/A | Not recommended (see prior discussion) |

Proposed readability rules belong in **Option A** unless you want a dedicated Pass-2 voice paragraph in system block 1 (**Option B**).

---

## Related files (generated for inspection)

| File | Contents |
|------|----------|
| [`pass2-payload-current-example.md`](pass2-payload-current-example.md) | Annotated current payload with abbreviated JSON |
| [`pass2-payload-proposed-tone-example.md`](pass2-payload-proposed-tone-example.md) | Same structure with proposed tone additions marked |
| [`_system_role.txt`](_system_role.txt) | Full system block 1 (verbatim) |
| [`_framework.md`](_framework.md) | Full system block 2 (verbatim, ~491 lines) |
| [`_user_body.md`](_user_body.md) | Full user text body (verbatim) |
| [`_payload_meta.json`](_payload_meta.json) | Char counts and chart lists |
