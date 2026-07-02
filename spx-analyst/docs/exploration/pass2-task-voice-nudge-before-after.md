# Pass 2 Task voice — before / after (proposed nudge)

**Status:** Preview only — not implemented  
**Edit location:** `build_report_prompt()` in `src/prompts.py`, lines 378–394  
**Context:** Everything above this block in `## Task` is **unchanged** (Pass 1 complete, exposition lock, recommended action, eight sections, Do NOT emit list). `mixed_note` and `pass2_task_extra` append **unchanged** after this block.

Below is the text **as the model sees it** in the user message (not Python string syntax).

---

## Unchanged context (for orientation)

```markdown
## Task
Pass 1 already completed in a separate API call — structured state was emitted via `emit_daily_state`. Do NOT call tools or emit JSON in this pass. Your entire response must be markdown prose only.

Write investor-facing narrative for an already-decided posture. The validated state is final: do not introduce or imply signal readings that contradict its structural_bias, signal_alignment, decision_matrix, or recommended action. Your job is exposition and reconciliation, not re-deciding.

Recommended action (verbatim): '…'.

Re-open charts only to add descriptive detail and to reconcile the conflicts already listed in the conflict checklist — not to form new conclusions.

Output exactly these eight `##` sections in order — nothing else:
1. `## Today's Posture`
… through 8. `## Evidence and Tensions`

Do NOT emit:
- A `#` title line or Header Snapshot (Python assembles the preamble)
- Injected numeric fact blocks under sections 5–7 (Python inserts them during assembly)
- `## Updated Decision Matrix` (Python renders the matrix from validated state)
```

---

## Section A — Audience + Posture structure

### BEFORE (current, committed)

```markdown
Audience: an experienced investor reading a daily market report. Lead each section with the takeaway in the first sentence; support with evidence after.
```

### AFTER (proposed)

```markdown
Audience: an experienced investor reading a daily market report. Lead each section with the takeaway in the first sentence; support with evidence after.

Today's Posture: use 2–3 short paragraphs; do not pack the full case into one block.
```

**Why:** 6/30 led with action but used one dense Posture paragraph; this is a single-section structure hint only.

---

## Section B — Prose bans + checklist clarifier

### BEFORE (current, committed)

```markdown
Do not write in prose: chart filenames (e.g. *.png), workflow labels ("Step N", "Pre-Step", "the framework requires/flags/rules"), or snake_case divergence ids as headings — use plain English instead. You may use framework_rule and chart_refs from the conflict checklist as background inputs; do not quote filenames or framework-rule labels in published prose.
```

### AFTER (proposed)

```markdown
Do not write in prose: chart filenames (e.g. *.png), workflow labels ("Step N", "Pre-Step"), snake_case divergence ids as headings, or attributing conclusions to "the framework" (e.g. "the framework calls/requires/flags/raises/resolves…") — state the market conclusion directly instead (e.g. "trim bias applies here; do not add"). You may use framework_rule and chart_refs from the conflict checklist as background inputs; do not quote filenames or framework-rule labels in published prose.
```

**Why:** 6/30 still wrote “The framework raises the bar” and “the framework calls for” — outside the old banned phrase list. Closes the attribution loophole; adds a positive example.

**Diff summary:**

| Removed | Added |
|---------|--------|
| `"the framework requires/flags/rules"` as a fixed substring list | Ban on **any** sentence attributing conclusions to `"the framework"` |
| — | Example of direct phrasing: `"trim bias applies here; do not add"` |

---

## Section C — Numerics + bullets (unchanged)

### BEFORE and AFTER (identical)

```markdown
Do not regenerate numerics in prose where Python injects a facts block — interpret the read-only snippets instead. Use bullet lists for key levels, session triggers, or when multiple tensions need separating; short prose is fine for a single clear tension.
```

---

## Section D — Section budgets (unchanged)

### BEFORE and AFTER (identical)

```markdown
Section budgets: Today's Posture 150–250 words (lead with action); Market Regime 200–300; Price and Trend through Tactical Levels 150–350 each; Evidence and Tensions ≥100 words when no divergences remain.
```

---

## Section E — Evidence and Tensions

### BEFORE (current, committed)

```markdown
`## Evidence and Tensions` is required every run. For each item in conflicting_evidence from the conflict checklist, give the bullish read, the bearish read, and how today's validated posture resolves the tension. On zero-divergence days, cover primary_tension and confirming evidence explicitly.
```

### AFTER (proposed)

```markdown
`## Evidence and Tensions` is required every run. For each item in conflicting_evidence from the conflict checklist, give the bullish read, the bearish read, and how today's validated posture resolves the tension. For each tension, use a plain-English heading and three parts: Bullish read, Bearish read, Resolution (one sentence on what today's posture implies for action). Do not restate framework_rule text or label it as a rule. On zero-divergence days, cover primary_tension and confirming evidence explicitly.
```

**Why:** Locks in the 6/30 bullet + Resolution pattern; discourages quoting `framework_rule` verbatim (6/29: “The framework rule — never use Monte Carlo…”).

---

## Full voice block — side by side

### BEFORE (full block, current)

```markdown
Audience: an experienced investor reading a daily market report. Lead each section with the takeaway in the first sentence; support with evidence after.

Do not write in prose: chart filenames (e.g. *.png), workflow labels ("Step N", "Pre-Step", "the framework requires/flags/rules"), or snake_case divergence ids as headings — use plain English instead. You may use framework_rule and chart_refs from the conflict checklist as background inputs; do not quote filenames or framework-rule labels in published prose.

Do not regenerate numerics in prose where Python injects a facts block — interpret the read-only snippets instead. Use bullet lists for key levels, session triggers, or when multiple tensions need separating; short prose is fine for a single clear tension.

Section budgets: Today's Posture 150–250 words (lead with action); Market Regime 200–300; Price and Trend through Tactical Levels 150–350 each; Evidence and Tensions ≥100 words when no divergences remain.

`## Evidence and Tensions` is required every run. For each item in conflicting_evidence from the conflict checklist, give the bullish read, the bearish read, and how today's validated posture resolves the tension. On zero-divergence days, cover primary_tension and confirming evidence explicitly.
```

### AFTER (full block, proposed)

```markdown
Audience: an experienced investor reading a daily market report. Lead each section with the takeaway in the first sentence; support with evidence after.

Today's Posture: use 2–3 short paragraphs; do not pack the full case into one block.

Do not write in prose: chart filenames (e.g. *.png), workflow labels ("Step N", "Pre-Step"), snake_case divergence ids as headings, or attributing conclusions to "the framework" (e.g. "the framework calls/requires/flags/raises/resolves…") — state the market conclusion directly instead (e.g. "trim bias applies here; do not add"). You may use framework_rule and chart_refs from the conflict checklist as background inputs; do not quote filenames or framework-rule labels in published prose.

Do not regenerate numerics in prose where Python injects a facts block — interpret the read-only snippets instead. Use bullet lists for key levels, session triggers, or when multiple tensions need separating; short prose is fine for a single clear tension.

Section budgets: Today's Posture 150–250 words (lead with action); Market Regime 200–300; Price and Trend through Tactical Levels 150–350 each; Evidence and Tensions ≥100 words when no divergences remain.

`## Evidence and Tensions` is required every run. For each item in conflicting_evidence from the conflict checklist, give the bullish read, the bearish read, and how today's validated posture resolves the tension. For each tension, use a plain-English heading and three parts: Bullish read, Bearish read, Resolution (one sentence on what today's posture implies for action). Do not restate framework_rule text or label it as a rule. On zero-divergence days, cover primary_tension and confirming evidence explicitly.
```

---

## What does not change

- System prompt (role + hard constraints + framework)
- Pass 2 exposition lock, section list, Do NOT emit list
- `mixed_note` (when alignment is mixed)
- `pass2_task_extra` (Pass 2 chart authority)
- User body blocks 1–6 (analysis_context, state JSON, conflict checklist, etc.)
- `report_assembly.py`, `validation.py`

---

## Approval options

| Option | Edits |
|--------|--------|
| **Minimal** | Section B only (framework attribution ban) |
| **Recommended** | Sections B + E (ban + Evidence format) |
| **Full proposed** | Sections A + B + E (add Posture paragraph nudge) |
