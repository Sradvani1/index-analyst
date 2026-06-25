# PR-7: Pass 2 Investor Report Template

**Status:** Complete  
**Framework version:** `daily-2026-06`  
**Builds on:** [PR-2: Two-pass prompt overhaul](PR-2-spx-two-pass-prompt-overhaul.md)

---

## Summary

Pass 2 now emits **eight prose sections only**. Python assembles the published
`{date}-analysis.md` with nine visible parts: Header Snapshot, eight narrative
sections (with fact injections under sections 5–7), and a state-rendered Updated
Decision Matrix. Raw Pass 2 prose is retained in `response_raw.report_pass_prose`
for audit and future RAG.

---

## Nine visible parts vs eight LLM sections

| Part | Heading | Author |
|------|---------|--------|
| Header Snapshot | `#` title + bold fact lines | Python |
| 1–4, 8 | Today's Posture … Evidence and Tensions | Pass 2 LLM |
| 5–7 | Valuation / Monte Carlo / Tactical Levels (+ injected fact blocks) | Pass 2 + Python |
| 9 | Updated Decision Matrix | Python (`daily_state.decision_matrix`) |

Pass 2 must not emit a `#` preamble, injected fact blocks, or the matrix.

---

## Pipeline change

```
Pass 2 LLM → report_pass_prose (8 sections)
  → assemble_investor_report()
  → validate_report(assembled)
  → save_outputs → memory mirror (unchanged paths)
```

New module: `src/report_assembly.py`  
Orchestration: `src/analysis_engine.py`  
Validation: strict `INVESTOR_REPORT_SECTIONS` order on assembled markdown; always-on
Evidence and Tensions; matrix-state echo gate.

---

## Files touched

| File | Change |
|------|--------|
| `src/prompts.py` | `INVESTOR_REPORT_SECTIONS`, `PASS2_PROSE_SECTIONS`, investor Pass 2 task |
| `src/report_assembly.py` | Header, fact blocks, matrix render, assembly |
| `src/validation.py` | Strict section validation; matrix echo; always-on tensions |
| `src/analysis_engine.py` | Assembly hook; `report_pass_prose`; `run_log.report_assembly` |
| `src/anthropic_client.py` | Pass 2 stub detection keyed to investor `##` headings (PR-7 follow-up) |
| `tests/test_report_assembly.py` | Assembly unit tests |
| `tests/test_validation.py` | Investor template validation fixtures |
| `tests/test_engine.py` | End-to-end assembly + raw prose persistence |
| `tests/test_prompt_builder.py` | Eight-section prompt contract |

**Unchanged:** web viewer/API, `{date}-state.json`, Step 0, Pass 1, enforcement, Pass 2 chart selection.

---

## Run log

```json
"report_assembly": {
  "matrix_source": "daily_state",
  "prose_sections": 8,
  "prose_chars": 12345,
  "assembled_chars": 15678
}
```

`prose_sections` is the count of canonical Pass 2 headings parsed from
`report_pass_prose` (via `extract_prose_sections`), not a hardcoded constant.

---

## Prompt authority split (HARD_CONSTRAINTS)

Shared system role (`load_system_role`) now distinguishes passes:

- **Pass 1:** emit all 18 decision-matrix rows in structured state.
- **Pass 2:** eight prose `##` sections ending with Evidence and Tensions only —
  no `#` title, fact blocks, or Updated Decision Matrix.

This removes the pre–PR-7 instruction to “always end with the Updated Decision Matrix”
from Pass 2, which conflicted with the investor assembly contract.

---

## Pass 2 stub detection (PR-4.1 + PR-7)

`_is_pass2_stub_response` treats these as **non-stub** (real output):

- Any of `## Today's Posture`, `## Market Regime`, or `## Evidence and Tensions`
- Legacy workflow markers (`## 0.`, `## Structural Regime`, `## Updated Decision Matrix`, …)

These are **stub** under the new contract:

- Short `# SPX Daily Analysis …` preambles without investor sections
- Opus emit_daily_state preambles (unchanged from PR-4.1)

See [PR-4.1](PR-4.1-pass2-stub-response-fix.md) for the tools-free retry path.

---

## `cli validate`

Validates the **assembled** `{date}-analysis.md` against `INVESTOR_REPORT_SECTIONS`.
Reports written before PR-7 (Daily 7-Step workflow headings) fail strict section
validation — expected; no historical backfill. The web viewer still renders both formats.

---

## Validation gates (assembled report)

| Code | Severity | Rule |
|------|----------|------|
| `missing_section` | error | Any of nine sections absent |
| `extra_section` | error | Unknown `##` heading |
| `section_order` | error | Headings out of order |
| `missing_evidence_and_tensions` | error | Every run |
| `missing_primary_tension` | error | Part 8 must address tension |
| `missing_high_weight_conflict` | error | High-weight divergence ids |
| `matrix_not_last` | error | Content after matrix |
| `matrix_state_mismatch` | error | Table ≠ `daily_state.decision_matrix` |
| `contradicting_structural_bias` | error | PR-2 gate (unchanged) |
