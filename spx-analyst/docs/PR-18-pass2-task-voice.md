# PR-18: Pass 2 Task Voice

**Status:** Complete  
**Framework version:** `daily-2026-06`  
**Builds on:** [PR-7: Pass 2 investor report template](PR-7-pass2-investor-report-template.md)

---

## Summary

Tightens **Pass 2 user Task text only** in `build_report_prompt()` for investor-facing readability. PR-7 assembly, validation, system prompts, and hard constraints are unchanged.

New runs get improved prose guidance; archived reports are not backfilled.

---

## What changed

Replaced the single `Tone:` paragraph and the Evidence and Tensions resolution line in the Pass 2 `## Task` block.

### Before

```markdown
Tone: write for market participants, not internal framework review. No methodology meta-commentary (e.g. 'Step 2 requires…'). Do not regenerate numerics in prose where Python injects a facts block — interpret the read-only snippets instead.

… give the bullish read, the bearish read, and how the framework rule resolves it.
```

### After

```markdown
Audience: an experienced investor reading a daily market report. Lead each section with the takeaway in the first sentence; support with evidence after.

Do not write in prose: chart filenames (e.g. *.png), workflow labels ("Step N", "Pre-Step", "the framework requires/flags/rules"), or snake_case divergence ids as headings — use plain English instead. You may use framework_rule and chart_refs from the conflict checklist as background inputs; do not quote filenames or framework-rule labels in published prose.

Do not regenerate numerics in prose where Python injects a facts block — interpret the read-only snippets instead. Use bullet lists for key levels, session triggers, or when multiple tensions need separating; short prose is fine for a single clear tension.

… give the bullish read, the bearish read, and how today's validated posture resolves the tension.
```

---

## Unchanged

- Exposition lock, eight-section output contract, Do NOT emit list, section budgets
- `mixed_note` and `pass2_task_extra` conditionals
- `report_assembly.py`, `validation.py`, system role, `HARD_CONSTRAINTS`, framework injection
- `migrate_perplexity.build_migration_report_prompt` (legacy path)

---

## Files touched

| File | Change |
|------|--------|
| `src/prompts.py` | Pass 2 Task voice block in `build_report_prompt()` |
| `tests/test_prompt_builder.py` | `test_report_prompt_task_voice_guidance`; exposition test split |

---

## Acceptance criteria

- Pass 2 still requires exactly eight prose sections; no title, fact blocks, or matrix in LLM output
- Task reflects daily-market-report audience, takeaway-first, prose bans, checklist clarifier
- Evidence and Tensions resolves via today's validated posture, not "framework rule"
- `pytest tests/test_prompt_builder.py` passes

---

## Optional post-merge verification

Re-run Pass 2 for one date and spot-check published prose for fewer `.png` references and framework meta-language. Not required for merge.
