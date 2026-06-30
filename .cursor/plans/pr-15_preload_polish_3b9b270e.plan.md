---
name: PR-15 preload polish
overview: "Small serialization polish on top of PR-15: improve prompt voice (rounded prices, no conflict IDs, marginal-change arc lines) and align docs so char caps are the hard contract and token counts are approximate targets."
todos:
  - id: format-price
    content: Add src/formatting.format_price(); use in report_assembly + chat_preload render/posture/trigger levels
    status: completed
  - id: risk-voice
    content: "Rewrite _risk_bullets: marginal first bullet from what_changed_today; framework_rule only for conflicts"
    status: completed
  - id: arc-marginal
    content: Add _arc_session_fragment() in memory.py; wire into build_arc_brief
    status: completed
  - id: caps-docs
    content: Update PR-15, operator guide, payload example — char caps hard; token column as approx target (doc-table only, no schema constants)
    status: completed
  - id: tests
    content: Add/update tests for prices, no conflict IDs, arc marginal fragments; regen payload on live memory
    status: completed
isProject: false
---

# PR-15 preload polish pass

**Scope:** Serialization and docs only. No routing, no schema shape changes, no changes to `chat_service.py`, `openai_responses.py`, or RAG.

**Status:** Approved for build — preserves PR-15 contract; token counts are soft guidance only.

**Decision locked:** Char caps remain the **hard** contract (enforced in code). Per-layer token figures are **approx targets** (doc-table only — no schema constants, no runtime enforcement). No tiktoken in production renderers.

---

## Problem summary

PR-15 achieved the main goal (~76% shrink, correct three-layer shape, PR-10 authority intact). The live payload ([`docs/chat-api-payload-example-2026-06-25.md`](spx-analyst/docs/chat-api-payload-example-2026-06-25.md)) still exposes four polish gaps:

| Issue | Root cause today |
|-------|------------------|
| Budget table implies token limits are enforced | Docs use "cap" for token column; code only enforces char caps (`1400` / `1200`) |
| Raw float prices in prompt | [`render_current_brief`](spx-analyst/src/chat_preload.py) emits `{brief.spx_close}` and raw MC targets |
| Conflict IDs in risk bullets | [`_risk_bullets`](spx-analyst/src/chat_preload.py) formats `{divergence.id}: {framework_rule}` |
| Repetitive arc lines | [`build_arc_brief`](spx-analyst/src/memory.py) uses `first_sentence(primary_tension)` — same skeleton opener every day |

---

## 1. Document budgets truthfully (doc-table only for tokens)

Update budget language in:

- [`docs/PR-15-compact-chat-preload.md`](spx-analyst/docs/PR-15-compact-chat-preload.md)
- [`docs/chat-api-payload-example-2026-06-25.md`](spx-analyst/docs/chat-api-payload-example-2026-06-25.md) (regenerate after code changes)
- [`docs/research-assistant-operator-guide.md`](spx-analyst/docs/research-assistant-operator-guide.md) (one sentence)

**Do not** add `MAX_RENDERED_TOKENS_*` constants to [`schemas.py`](spx-analyst/src/schemas.py). Token targets live in markdown tables only — avoids implying a second enforced contract colocated with `*Caps` classes.

**Budget table column labels (use consistently):**

| Layer | Chars (cap, enforced) | Tokens (approx target) |
|-------|----------------------:|------------------------|
| Constitution | 2,000 | ~500 |
| Current brief | 1,400 | ~350 |
| Arc brief | 1,200 | ~300 |
| Total `additional_instructions` | 5,000 | ~1,500 |

Wording rules:

- Char column header: **Cap** (or "Chars (cap)") — these are enforced via `*Caps.MAX_RENDERED_CHARS` and truncation.
- Token column header: **Approx target** or **Observed target range** — never "cap", "max", or "limit".
- Payload example metadata table: same labels; observed values may exceed approx target without failing anything (e.g. 354 vs ~350 is fine).

Extend [`test_live_memory_budget_caps`](spx-analyst/tests/test_chat_preload.py) to assert per-layer **char** caps explicitly (constitution, current, arc). Optional tiktoken count in test may be logged or asserted only against total soft ceiling (`ChatPreloadBudget.MAX_ADDITIONAL_INSTRUCTIONS_TOKENS`) with a comment that per-layer token figures are not enforced.

---

## 2. Presentation-ready price formatting

Introduce a shared helper (minimal new surface):

```python
# src/formatting.py
def format_price(value: float) -> str:
    return f"{value:,.2f}"
```

- Refactor [`report_assembly._format_close`](spx-analyst/src/report_assembly.py) to call `format_price` (same output, single convention).
- Apply at **render time** in [`chat_preload.py`](spx-analyst/src/chat_preload.py):
  - `spx_close:` line in `render_current_brief`
  - `MC upside:` / `MC downside:` in `_trigger_levels` (format numeric targets; leave cascade prose unchanged)
  - `answer_posture_from_preload` SPX close phrase

**Keep** `CurrentBrief.spx_close: float` typed — formatting is presentation-only, not a schema change.

**Expected output:** `spx_close: 7,357.49`, `MC upside: 7,577.92` (matches reader UI [`web/lib/format.ts`](spx-analyst/web/lib/format.ts)).

---

## 3. Strip internal conflict IDs from risk bullets

In [`_risk_bullets`](spx-analyst/src/chat_preload.py):

```python
# before
line = f"{divergence.id}: {divergence.framework_rule.strip()}"
# after
line = divergence.framework_rule.strip()
```

Optionally prioritize **marginal change** for the first bullet (aligns with arc polish):

```python
if state.what_changed_today:
    bullets.append(_truncate(state.what_changed_today[0].strip(), MAX_RISK_BULLET_CHARS))
elif tension := first_sentence(state.primary_tension):
    bullets.append(...)
# then framework_rule-only conflict bullets
```

This removes both `erp_ceiling_vs_forward_pe:` labels and the repeated skeleton opener from `key_risks_or_tensions`.

---

## 4. Arc session lines: marginal change, not skeleton replay

In [`memory.py`](spx-analyst/src/memory.py), replace `_tension_fragment(primary_tension)` in `build_arc_brief` with a new helper:

```python
def _arc_session_fragment(state: DailyState) -> str:
    if state.what_changed_today:
        return _truncate(state.what_changed_today[0].strip(), ArcBriefCaps.MAX_TENSION_FRAGMENT_CHARS)
    return _tension_fragment(state.primary_tension)
```

- Does **not** emit `changed:` prefix (still forbidden).
- Reuses existing `what_changed_today` bullets already written by the engine — same source as report deltas, compressed to 80 chars.
- Fallback to tension first sentence when no change bullets exist.

**Expected arc line (2026-06-25):** `2026-06-25 | Late Bull / Topping | defensive patience | DOWNSIDE TARGET TAGGED: close 7,357.49 fully retraced the active leg…` instead of `A mechanically intact bull skeleton…`.

Update [`tests/test_arc_brief.py`](spx-analyst/tests/test_arc_brief.py): fixture with `what_changed_today` asserts fragment comes from first change bullet; empty-changes fixture asserts tension fallback.

---

## Files touched

| File | Change |
|------|--------|
| [`src/formatting.py`](spx-analyst/src/formatting.py) | **New** — `format_price()` |
| [`src/report_assembly.py`](spx-analyst/src/report_assembly.py) | Import `format_price` |
| [`src/chat_preload.py`](spx-analyst/src/chat_preload.py) | Price formatting; risk bullet voice; optional first-bullet marginal change |
| [`src/memory.py`](spx-analyst/src/memory.py) | `_arc_session_fragment()` |
| [`tests/test_chat_preload.py`](spx-analyst/tests/test_chat_preload.py) | Price format, no conflict IDs, marginal first bullet |
| [`tests/test_arc_brief.py`](spx-analyst/tests/test_arc_brief.py) | Fragment from `what_changed_today` |
| Docs | PR-15 polish section, payload regen, operator guide cap wording |

**Unchanged:** assembly shape, authority stack, char cap enforcement, `file_search`, chat runtime.

---

## Verification

```bash
cd spx-analyst
pytest tests/test_chat_preload.py tests/test_arc_brief.py tests/test_web_chat_api.py -q
```

With live memory, regenerate payload example and confirm:

- No raw float artifacts (`7357.490234375`)
- No `snake_case_id:` prefixes in `key_risks_or_tensions`
- Arc lines differ day-to-day (lead with change headline, not shared skeleton)
- Per-layer char caps still pass; token column labeled **approx target** (not cap)
- Total size remains well under 5,000 chars

---

## Acceptance

- [ ] Char caps documented and enforced as the hard contract; token figures in docs only as approx target (no "cap" in token column)
- [ ] Prices formatted to two decimals with thousands separators in preload output
- [ ] Risk bullets use natural language only (no divergence IDs)
- [ ] Arc snapshots emphasize daily marginal change via first `what_changed_today` bullet
- [ ] Payload example regenerated and aligned with PR-15 docs
