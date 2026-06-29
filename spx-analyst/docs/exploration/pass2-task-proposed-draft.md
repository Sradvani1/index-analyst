# Pass 2 `## Task` — proposed draft (preview only)

**Status:** Implemented as minimal-plus → [PR-18](../PR-18-pass2-task-voice.md)  
**Edit target:** `build_report_prompt()` → `parts.append("## Task\n" ...)`  
**Scope:** Replace the single `Tone:` paragraph + one Evidence line; everything else in Task unchanged.

---

## What changes vs current

| Section | Current | Proposed |
|---------|---------|----------|
| Tone | One `Tone:` paragraph | Split into **Audience**, **Banned patterns**, **Style** |
| Evidence and Tensions | "how the **framework rule** resolves it" | "how **today's validated posture** resolves the tension" |
| Exposition lock, sections, budgets, Do NOT emit | unchanged | unchanged |
| `mixed_note`, `pass2_task_extra` | unchanged | unchanged |

---

## Current `## Task` (for comparison)

```markdown
## Task
Pass 1 already completed in a separate API call — structured state was emitted via `emit_daily_state`. Do NOT call tools or emit JSON in this pass. Your entire response must be markdown prose only.

Write investor-facing narrative for an already-decided posture. The validated state is final: do not introduce or imply signal readings that contradict its structural_bias, signal_alignment, decision_matrix, or recommended action. Your job is exposition and reconciliation, not re-deciding.

Recommended action (verbatim): 'Defensive — trim bias'.

Re-open charts only to add descriptive detail and to reconcile the conflicts already listed in the conflict checklist — not to form new conclusions.

Output exactly these eight `##` sections in order — nothing else:
1. `## Today's Posture`
2. `## Market Regime`
3. `## Price and Trend`
4. `## Technicals and Sentiment`
5. `## Valuation and ERP`
6. `## Risk and Monte Carlo`
7. `## Tactical Levels and Next Session Plan`
8. `## Evidence and Tensions`

Do NOT emit:
- A `#` title line or Header Snapshot (Python assembles the preamble)
- Injected numeric fact blocks under sections 5–7 (Python inserts them during assembly)
- `## Updated Decision Matrix` (Python renders the matrix from validated state)

Tone: write for market participants, not internal framework review. No methodology meta-commentary (e.g. 'Step 2 requires…'). Do not regenerate numerics in prose where Python injects a facts block — interpret the read-only snippets instead.

Section budgets: Today's Posture 150–250 words (lead with action); Market Regime 200–300; Price and Trend through Tactical Levels 150–350 each; Evidence and Tensions ≥100 words when no divergences remain.

`## Evidence and Tensions` is required every run. For each item in conflicting_evidence from the conflict checklist, give the bullish read, the bearish read, and how the framework rule resolves it. On zero-divergence days, cover primary_tension and confirming evidence explicitly.
```

---

## Proposed `## Task` (full draft)

Below is exactly what the model would see at the bottom of the Pass 2 user body. Placeholders like `{action}` are filled at runtime from `daily_state`.

```markdown
## Task
Pass 1 already completed in a separate API call — structured state was emitted via `emit_daily_state`. Do NOT call tools or emit JSON in this pass. Your entire response must be markdown prose only.

Write investor-facing narrative for an already-decided posture. The validated state is final: do not introduce or imply signal readings that contradict its structural_bias, signal_alignment, decision_matrix, or recommended action. Your job is exposition and reconciliation, not re-deciding.

Recommended action (verbatim): 'Defensive — trim bias'.

Re-open charts only to add descriptive detail and to reconcile the conflicts already listed in the conflict checklist — not to form new conclusions.

Output exactly these eight `##` sections in order — nothing else:
1. `## Today's Posture`
2. `## Market Regime`
3. `## Price and Trend`
4. `## Technicals and Sentiment`
5. `## Valuation and ERP`
6. `## Risk and Monte Carlo`
7. `## Tactical Levels and Next Session Plan`
8. `## Evidence and Tensions`

Do NOT emit:
- A `#` title line or Header Snapshot (Python assembles the preamble)
- Injected numeric fact blocks under sections 5–7 (Python inserts them during assembly)
- `## Updated Decision Matrix` (Python renders the matrix from validated state)

Audience:
- Write for an experienced investor reading a daily morning brief — not an internal framework audit.
- Lead each section with the takeaway in the first sentence; support with evidence after.
- Use active, direct language ("Hold defense", "Do not add") rather than narrating methodology ("The framework mandates…").

Do not write in prose:
- Chart filenames (e.g. `04_spx_3month.png`) — describe what the chart shows instead.
- Workflow labels: "Step 2", "Pre-Step", "the seven steps", "the framework requires/flags/rules".
- Snake_case divergence ids as headings — use plain English (e.g. "Breadth vs price bounce", not `breadth_credit_vs_bounce`).

Style:
- Keep paragraphs to 2–4 sentences; use bullet lists for key levels, session triggers, and Evidence and Tensions items.
- Today's Posture: first sentence = recommended action in plain English; second sentence = the single most important reason today.
- Explain acronyms once on first use in each section (e.g. equity risk premium (ERP)).
- Do not regenerate numerics in prose where Python injects a facts block — interpret the read-only snippets instead.

Section budgets: Today's Posture 150–250 words (lead with action); Market Regime 200–300; Price and Trend through Tactical Levels 150–350 each; Evidence and Tensions ≥100 words when no divergences remain.

`## Evidence and Tensions` is required every run. For each item in conflicting_evidence from the conflict checklist:
- Use a short plain-English heading (not the divergence id).
- Bullish read (1–2 sentences).
- Bearish read (1–2 sentences).
- Resolution: how today's validated posture resolves the tension.
On zero-divergence days, cover primary_tension and confirming evidence explicitly.
```

---

## With runtime conditionals appended (unchanged logic)

When `signal_alignment.overall == "mixed"`, this sentence is appended immediately after the Evidence block:

```markdown
 When alignment is mixed, present qualified/hedged readings without altering validated signal values.
```

When Pass 2 image optimization is enabled, this block is appended at the end:

```markdown
Pass 2 chart authority:
- Attached images: reconciliation and descriptive detail for listed conflicts only where cited.
- Reference-only charts: workflow citations from validated state / conflict checklist text only.
- Do not contradict validated state.
- Prior-run posture block (if present): continuity only — not today's chart evidence.
- When attached-image impressions, prompt wording, and validated daily state differ, validated daily state is authoritative.
```

---

## Proposed Python string shape (for implementers)

Conceptual diff inside `build_report_prompt()` — replace lines 378–387 with:

```python
        "Audience:\n"
        "- Write for an experienced investor reading a daily morning brief — not an internal framework audit.\n"
        "- Lead each section with the takeaway in the first sentence; support with evidence after.\n"
        "- Use active, direct language (\"Hold defense\", \"Do not add\") rather than narrating methodology (\"The framework mandates…\").\n\n"
        "Do not write in prose:\n"
        "- Chart filenames (e.g. `04_spx_3month.png`) — describe what the chart shows instead.\n"
        "- Workflow labels: \"Step 2\", \"Pre-Step\", \"the seven steps\", \"the framework requires/flags/rules\".\n"
        "- Snake_case divergence ids as headings — use plain English (e.g. \"Breadth vs price bounce\", not `breadth_credit_vs_bounce`).\n\n"
        "Style:\n"
        "- Keep paragraphs to 2–4 sentences; use bullet lists for key levels, session triggers, and Evidence and Tensions items.\n"
        "- Today's Posture: first sentence = recommended action in plain English; second sentence = the single most important reason today.\n"
        "- Explain acronyms once on first use in each section (e.g. equity risk premium (ERP)).\n"
        "- Do not regenerate numerics in prose where Python injects a facts block — interpret the read-only snippets instead.\n\n"
        "Section budgets: Today's Posture 150–250 words (lead with action); Market Regime 200–300; "
        "Price and Trend through Tactical Levels 150–350 each; Evidence and Tensions ≥100 words when "
        "no divergences remain.\n\n"
        f"`## {EVIDENCE_AND_TENSIONS_HEADING}` is required every run. For each item in "
        "conflicting_evidence from the conflict checklist:\n"
        "- Use a short plain-English heading (not the divergence id).\n"
        "- Bullish read (1–2 sentences).\n"
        "- Bearish read (1–2 sentences).\n"
        "- Resolution: how today's validated posture resolves the tension.\n"
        "On zero-divergence days, cover primary_tension and confirming evidence explicitly."
```

---

## Tests to update when implementing

- `tests/test_prompt_builder.py` — assertions on `investor-facing`, `Tone:`, `framework rule resolves`
- Any golden snapshots that embed the old Task wording

---

## Optional: minimal variant

If the full draft feels heavy, use only Audience + Do not write + Evidence line change (drop Style bullets except the numerics line):

```markdown
Audience: experienced investor morning brief — not internal framework audit. Lead with the takeaway first.

Do not write in prose: chart filenames (*.png), "Step N"/"Pre-Step", "the framework requires/flags", snake_case divergence headings.

Do not regenerate numerics in prose where Python injects a facts block — interpret the read-only snippets instead.
```

Everything else in Task stays identical to current.
