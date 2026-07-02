# Pass 2 Task voice — optimized minimal diff

**Status:** Preview only — not implemented  
**Goal:** Same outcomes as [pass2-task-voice-nudge-before-after.md](./pass2-task-voice-nudge-before-after.md), with **fewer new instructions** and **smallest possible edit** to the committed prompt.

---

## Optimization rationale

The verbose proposal added **three new instruction blocks** (~120 extra words). Most of that duplicated what already exists or what 6/30 already did without being told:

| Verbose addition | Drop? | Why |
|------------------|-------|-----|
| Separate Posture paragraph line | **Fold in** | Section budgets already mention Today's Posture — add structure there in 4 words |
| Framework ban with verb examples + sample rewrite | **Compress** | Replace fixed substring `"requires/flags/rules"` with one pattern: **attributing conclusions to "the framework"** — covers 6/30's "calls" and "raises" without listing verbs |
| Positive example `"trim bias applies here…"` | **Drop** | Fold into ban line tail: **state conclusions directly** (shorter) |
| Evidence Bullish/Bearish/Resolution template | **Drop** | 6/30 already used this shape; existing line already requires bullish/bearish/posture resolution |
| `Do not restate framework_rule text` | **Drop** | Already covered by **do not quote framework-rule labels** in the same paragraph |

**Result:** **2 surgical edits** to existing strings — no new lines, no Evidence paragraph change.

---

## Gaps from 6/29 vs 6/30 → minimal fix

| Observed gap | Minimal fix |
|--------------|-------------|
| "The framework calls/raises…" (6/30) | Edit 1 — broaden ban from verb list to attribution pattern |
| "The framework resolves / framework rule…" (6/29) | Edit 1 — same |
| One dense Posture paragraph (6/30) | Edit 2 — `2–3 short paragraphs` inside existing word budget |
| Evidence structure (6/30 win) | **No change** — keep current posture-resolution sentence |

---

## Edit 1 — Prose bans (one string, in place)

### CURRENT (committed)

```markdown
Do not write in prose: chart filenames (e.g. *.png), workflow labels ("Step N", "Pre-Step", "the framework requires/flags/rules"), or snake_case divergence ids as headings — use plain English instead. You may use framework_rule and chart_refs from the conflict checklist as background inputs; do not quote filenames or framework-rule labels in published prose.
```

### OPTIMIZED (recommended)

```markdown
Do not write in prose: chart filenames (e.g. *.png), workflow labels ("Step N", "Pre-Step"), attributing conclusions to "the framework", or snake_case divergence ids as headings — use plain English headings and state conclusions directly. You may use framework_rule and chart_refs from the conflict checklist as background inputs; do not quote filenames or framework-rule labels in published prose.
```

### Diff (what changed)

```diff
- workflow labels ("Step N", "Pre-Step", "the framework requires/flags/rules"), or snake_case divergence ids as headings — use plain English instead.
+ workflow labels ("Step N", "Pre-Step"), attributing conclusions to "the framework", or snake_case divergence ids as headings — use plain English headings and state conclusions directly.
```

**Net:** ~same length; closes the 6/30 loophole without a second sentence or examples.

---

## Edit 2 — Section budgets (one parenthetical, in place)

### CURRENT (committed)

```markdown
Section budgets: Today's Posture 150–250 words (lead with action); Market Regime 200–300; ...
```

### OPTIMIZED (recommended)

```markdown
Section budgets: Today's Posture 150–250 words (lead with action; 2–3 short paragraphs); Market Regime 200–300; ...
```

### Diff

```diff
- Today's Posture 150–250 words (lead with action);
+ Today's Posture 150–250 words (lead with action; 2–3 short paragraphs);
```

**Net:** +4 words inside an existing line — no new Posture instruction block.

---

## Unchanged lines (explicitly kept)

```markdown
Audience: an experienced investor reading a daily market report. Lead each section with the takeaway in the first sentence; support with evidence after.

Do not regenerate numerics in prose where Python injects a facts block — interpret the read-only snippets instead. Use bullet lists for key levels, session triggers, or when multiple tensions need separating; short prose is fine for a single clear tension.

`## Evidence and Tensions` is required every run. For each item in conflicting_evidence from the conflict checklist, give the bullish read, the bearish read, and how today's validated posture resolves the tension. On zero-divergence days, cover primary_tension and confirming evidence explicitly.
```

---

## Full voice block — three-way compare

### A. CURRENT (committed in `prompts.py`)

```markdown
Audience: an experienced investor reading a daily market report. Lead each section with the takeaway in the first sentence; support with evidence after.

Do not write in prose: chart filenames (e.g. *.png), workflow labels ("Step N", "Pre-Step", "the framework requires/flags/rules"), or snake_case divergence ids as headings — use plain English instead. You may use framework_rule and chart_refs from the conflict checklist as background inputs; do not quote filenames or framework-rule labels in published prose.

Do not regenerate numerics in prose where Python injects a facts block — interpret the read-only snippets instead. Use bullet lists for key levels, session triggers, or when multiple tensions need separating; short prose is fine for a single clear tension.

Section budgets: Today's Posture 150–250 words (lead with action); Market Regime 200–300; Price and Trend through Tactical Levels 150–350 each; Evidence and Tensions ≥100 words when no divergences remain.

`## Evidence and Tensions` is required every run. For each item in conflicting_evidence from the conflict checklist, give the bullish read, the bearish read, and how today's validated posture resolves the tension. On zero-divergence days, cover primary_tension and confirming evidence explicitly.
```

### B. VERBOSE PROPOSAL (previous doc — not recommended)

Adds: standalone Posture line, long framework ban with examples, Evidence template + `Do not restate framework_rule`. **~120 words added.**

See [pass2-task-voice-nudge-before-after.md](./pass2-task-voice-nudge-before-after.md) § Full voice block — AFTER.

### C. OPTIMIZED MINIMAL (recommended for implementation)

```markdown
Audience: an experienced investor reading a daily market report. Lead each section with the takeaway in the first sentence; support with evidence after.

Do not write in prose: chart filenames (e.g. *.png), workflow labels ("Step N", "Pre-Step"), attributing conclusions to "the framework", or snake_case divergence ids as headings — use plain English headings and state conclusions directly. You may use framework_rule and chart_refs from the conflict checklist as background inputs; do not quote filenames or framework-rule labels in published prose.

Do not regenerate numerics in prose where Python injects a facts block — interpret the read-only snippets instead. Use bullet lists for key levels, session triggers, or when multiple tensions need separating; short prose is fine for a single clear tension.

Section budgets: Today's Posture 150–250 words (lead with action; 2–3 short paragraphs); Market Regime 200–300; Price and Trend through Tactical Levels 150–350 each; Evidence and Tensions ≥100 words when no divergences remain.

`## Evidence and Tensions` is required every run. For each item in conflicting_evidence from the conflict checklist, give the bullish read, the bearish read, and how today's validated posture resolves the tension. On zero-divergence days, cover primary_tension and confirming evidence explicitly.
```

**Diff vs CURRENT:** 2 substrings in 2 existing lines only.

---

## Python implementation shape (for later)

Only these two replacements inside `parts.append("## Task\n" ...)`:

```python
# Edit 1 — replace the prose-bans fragment
'"Pre-Step", "the framework requires/flags/rules"), or snake_case divergence ids as headings — use plain English instead.'
# →
'"Pre-Step"), attributing conclusions to "the framework", or snake_case divergence ids as headings — use plain English headings and state conclusions directly.'

# Edit 2 — replace section budgets fragment
"Today's Posture 150–250 words (lead with action);"
# →
"Today's Posture 150–250 words (lead with action; 2–3 short paragraphs);"
```

**Test updates (minimal):** extend `test_report_prompt_task_voice_guidance` to assert `attributing conclusions to "the framework"` and `2–3 short paragraphs` present; `requires/flags/rules` absent.

---

## Expected outcome vs verbose proposal

| Outcome | Verbose | Optimized |
|---------|---------|-----------|
| Block "the framework calls/raises…" | Yes | Yes (same pattern ban) |
| Posture scannability | Yes (extra line) | Yes (budget parenthetical) |
| Evidence bullet template | Explicit | Relies on 6/30 behavior + existing posture line |
| Prompt token growth | High | **~minimal** |
| Risk of mechanical/template output | Higher | Lower |

---

## Recommendation

Implement **optimized minimal (C)** — two in-place string edits. If the next run still quotes `framework_rule` verbatim in Evidence, add **one** clause to the existing Evidence sentence only (e.g. ` without quoting framework_rule text`) — not the full template block.
