# PR-3.2: Memory rollup design decision brief

**Purpose:** External review (e.g. Perplexity) of costs, benefits, and tradeoffs for evolving the SPX analyst **prior posture snapshot** — the text block injected into Pass 1 and Pass 2 for day-over-day continuity.

**Status:** **Decision: Option B** (implemented)  
**Builds on:** [PR-3](PR-3-memory-rollup-overhaul.md) · [PR-3.1 backfill](PR-3.1-perplexity-backfill.md)  
**Sample artifacts:** [`docs/samples/memory-rollup-2026-06-08-context/`](samples/memory-rollup-2026-06-08-context/)

## Decision (2026-06-21)

**Option B — Relaxed posture snapshot (no character truncation on selected fields).**

- Keep PR-3 inclusion/exclusion matrix and selection limits (3 changes, 2 conflicts, 2 watchlist, categorical signals).
- Remove ellipsis truncation on `what_changed_today`, `primary_tension`, `conflicting_evidence`, and watchlist items.
- **Do not** include `narrative_summary` (deferred).

Implementation: [`src/memory.py`](../src/memory.py) `_format_day`, `_conflict_line`, `_build_unresolved_watchlist`.

---

## 1. Executive summary

The engine is **stateless at the API level**. Continuity comes from reloading recent valid `DailyState` JSON files from `memory/daily_states/` and formatting them into a compact markdown rollup via `build_recent_summary()` in [`src/memory.py`](../src/memory.py).

PR-3 (implemented) replaced a ~3,700-token narrative replay with a ~550–1,150-token **posture snapshot**: categorical signals, normalized action, truncated deltas, top-2 conflicts, footer watchlist. **No historical prices or raw indicator numbers** appear in memory.

After running a June 2026 Perplexity backfill, operators observed that **truncation mid-sentence** (ellipsis on fields we already selected) hurts readability and may reduce continuity value. This brief compares three designs and frames the **narrative inclusion** question.

**Minimum proposed change:** keep PR-3 field *selection* rules; **remove character truncation** on selected items.

**Open question:** should we also add `narrative_summary` per day (~+1,230 tokens on a 6-day window)?

---

## 2. System context (how memory works)

### 2.1 Authority boundaries (non-negotiable)

| Source | Role in today's run |
|--------|---------------------|
| **`analysis_context.json`** (Step 0 precompute) | Sole numeric truth: close, MC, ERP, structure levels |
| **Today's charts** (Pass 1 full pack; Pass 2 subset per PR-4) | Qualitative evidence for *today* |
| **Prior posture snapshot** | Continuity only — regime, posture, deltas, tensions, watchlist |
| **Full `DailyState` on disk** | Archive; not injected wholesale |

Prompt header (always when memory is injected):

```text
## Prior posture snapshot (continuity only — not authoritative for today's numerics)
Each run is a fresh analysis. Use this block only to track regime shifts, action posture,
day-over-day changes, and unresolved tensions. All calculations, thresholds, targets, and
price levels come from today's analysis_context and charts — never from prior sessions.
```

### 2.2 When memory is injected

| Path | Memory in prompt? | Rolling rebuild? |
|------|-------------------|------------------|
| Live run (`python -m src.cli run`) | Only if `SPX_INCLUDE_MEMORY=true` | Always after success |
| Perplexity backfill (`migrate-perplexity`) | **Always** (sequential chain) | Always after each session |

Config: `SPX_RECENT_STATE_COUNT=6` (max days loaded), newest-first load, **oldest→newest** display in rollup.

### 2.3 Pipeline (not “JSON dump + truncate”)

```
memory/daily_states/{date}-state.json
  → load_recent_states(limit=6, before_date=today)   # validation; skips invalid
  → build_recent_summary(states)
       per day: pick fields → transform → truncate → format lines
  → _optional_memory_block(summary)                 # PR-3 header wrapper
  → prepended to Pass 1 / Pass 2 prompt body
```

**Transform examples (not truncation):**

- Raw RSI 75 → `RSI overbought` (bucket)
- Raw action `hold_trim_into_7695_no_adds` → `trim bias` (closed set)
- 4 `open_questions` per day → footer watchlist max 2 ( eligibility rules )
- 4+ `conflicting_evidence` items → top 2 by weight (high → medium → low)

**Truncate examples (the contested part):**

- Each of 3 `what_changed_today` items → max **60 chars**
- `primary_tension` → max **120 chars**
- Each conflict line → max **90 chars**
- Each watchlist item → max **80 chars**

---

## 3. Current PR-3 limits (implemented)

### 3.1 Per-day block

| Field | Selection limit | Truncation | Excluded entirely |
|-------|-----------------|------------|-------------------|
| `structural_bias` | 1 | No | — |
| `signal_alignment.overall` | 1 | No | — |
| Recommended action | 1 | Normalized; max 60 chars | — |
| `signals` | 5 buckets | Categorical (no floats) | Raw numbers |
| `what_changed_today` | **First 3 items** | **60 chars each** | Items 4+ |
| `primary_tension` | 1 | **120 chars** | — |
| `conflicting_evidence` | **Top 2 by weight** | **90 chars/line** | bullish/bearish reads, chart_refs |
| `narrative_summary` | — | — | **Yes** |
| `open_questions` | — | — | Per-day (footer only) |
| `base_case`, `trend_regime`, MC, close | — | — | **Yes** |

### 3.2 Footer

| Field | Limit | Truncation |
|-------|-------|------------|
| Regime arc | 1 line from `structural_bias` sequence | No |
| Unresolved watchlist | **2 questions** ( eligibility filter ) | **80 chars each** |

### 3.3 Whole rollup

- Soft target: ≤ 2,500 chars
- Hard test cap: ≤ 3,000 chars

---

## 4. Three design options (with samples)

Samples reconstruct the **2026-06-08 backfill context**: four prior valid days (6/01, 6/02, 6/04, 6/05) as they would appear in Pass 1/2 for that session. Generated from production `memory/daily_states/*.json`.

| Option | Description | Sample file | 4-day chars | 4-day ~tokens |
|--------|-------------|-------------|------------:|--------------:|
| **A — Current PR-3** | Truncation on all selected fields | [`A-current-pr3-truncated.md`](samples/memory-rollup-2026-06-08-context/A-current-pr3-truncated.md) | 3,259 | **814** |
| **B — Relaxed (recommended minimum)** | Same picks; **full text** for selected fields | [`B-relaxed-no-truncation.md`](samples/memory-rollup-2026-06-08-context/B-relaxed-no-truncation.md) | 5,890 | **1,472** |
| **C — Relaxed + narrative** | Option B + full `narrative_summary` per day | [`C-relaxed-with-narrative-summary.md`](samples/memory-rollup-2026-06-08-context/C-relaxed-with-narrative-summary.md) | 9,419 | **2,354** |

### 4.1 Side-by-side: same field, three treatments (2026-06-01 `changed:`)

**A — Truncated (current):**

```text
changed: No prior sessions on record — this is the first logged run;…; Fifth consecutive ATH close but smallest gain of the streak…; Overall Fear & Greed fell for a 3rd consecutive session (61…
```

**B — Full text, same 3 items:**

```text
changed: No prior sessions on record — this is the first logged run; baseline established at Late Bull / Topping.; Fifth consecutive ATH close but smallest gain of the streak (+0.26%), signaling rally deceleration.; Overall Fear & Greed fell for a 3rd consecutive session (61->60->59) on rising prices — textbook sentiment divergence.
```

**C — Adds after tension/conflicts:**

```text
summary: SPX printed its fifth consecutive all-time-high close at 7,599.96 but the smallest gain of the streak (+0.26%) on a weak middle-third close, signaling a rally running out of buyers rather than building a base. Structure is Late Bull / Topping: trend is intact and Monte Carlo still favors the upside target first (~63%), but every confirming layer is at a cycle extreme — ERP at zero for seven sessions, junk-bond demand in extreme fear, breadth divergent, VIX at complacent lows, and put/call near cycle complacency. ...
```

Read full samples in the linked files before judging readability.

---

## 5. Token analysis (measured on real June 2026 states)

Estimates use `chars ÷ 4` (typical English prose). Actual billed tokens may vary ±15% by tokenizer.

### 5.1 Four-day window (6/8 migration context)

| Option | ~Tokens | Δ vs A |
|--------|--------:|-------:|
| A — Current | 814 | — |
| B — No truncation | 1,472 | **+658** |
| C — No truncation + narrative | 2,354 | **+1,540** |

### 5.2 Six-day window (full `SPX_RECENT_STATE_COUNT`; dates 6/01–6/10, 6/12 invalid/skipped)

| Option | ~Tokens | Δ vs A |
|--------|--------:|-------:|
| A — Current | 1,148 | — |
| B — No truncation | 2,071 | **+923** |
| C — No truncation + narrative | 3,319 | **+2,171** |
| D — No truncation + **5** changes + **3** conflicts (hypothetical) | 2,415 | **+1,267** |

### 5.3 Narrative contribution (6-day)

| Date | `narrative_summary` chars | ~Tokens |
|------|--------------------------:|--------:|
| 2026-06-01 | 891 | 222 |
| 2026-06-02 | 821 | 205 |
| 2026-06-04 | 866 | 216 |
| 2026-06-05 | 911 | 227 |
| 2026-06-08 | 801 | 200 |
| 2026-06-10 | 645 | 161 |
| **Sum** | **4,935** | **~1,233** |

Adding narrative ≈ adds back the entire pre-PR-3 memory budget by itself.

### 5.4 Memory vs rest of a live run

| Prompt component | Approx ~tokens |
|------------------|---------------:|
| Pass 1 charts (15 @ 1568px) | ~22,000 |
| Pass 1 charts (PR-4 optimized, 7–9 @ 1092px) | ~5,000–6,300 |
| `analysis_context` JSON | ~1,500–2,000 |
| Framework + role + task (cached prefix) | varies |
| **Memory A (current 6-day)** | **~1,150** |
| **Memory B** | **~2,070** |
| **Memory C** | **~3,320** |

Even option C is ~**10–15%** of a full Pass 1 image budget — **affordable in absolute terms**. The design question is **information value and anchoring risk**, not raw affordability.

### 5.5 Historical reference

| Design era | ~Tokens (6-day) | Notes |
|------------|----------------:|-------|
| Pre-PR-3 narrative replay | ~3,700 | Included close + prose replay |
| PR-3 truncated snapshot | ~1,150 | Current |
| Option C | ~3,320 | Near pre-PR-3 size but without historical close in memory |

---

## 6. Minimum plan (recommended baseline): remove truncation

### 6.1 Proposed code change

In [`src/memory.py`](../src/memory.py):

- **`_format_day`:** emit full strings for the **already-selected** items (3 changes, 1 tension, 2 conflict lines).
- **`_conflict_line`:** emit full `framework_rule` (or entire line without 90-char cap).
- **`_build_unresolved_watchlist`:** emit full question text for the 2 selected items.
- **`_normalize_action`:** keep 60-char cap only if needed for pathological matrix strings (rare).
- **Update tests** in [`tests/test_memory_rollup.py`](../tests/test_memory_rollup.py): remove ellipsis assertions; relax 3,000-char hard cap or raise soft cap (~5,000–6,000 for 6-day B).
- **Update** [PR-3 doc](PR-3-memory-rollup-overhaul.md) truncation table.

### 6.2 What stays the same

- Categorical `signals:` line (no raw numbers)
- 3 change items max; 2 conflicts max; 2 watchlist items max
- Exclusion of close, MC, matrix, per-day open_questions
- `analysis_context` as numeric authority
- PR-3 header contract

### 6.3 Operator impact

- `memory/rolling/recent_summary.md` becomes readable without ellipses.
- No re-backfill required — rolling summary regenerates from existing JSON on next run or `rebuild-summary`.

---

## 7. Open design questions (beyond truncation)

These are **selection limit** changes — independent of truncation and narrative.

| Question | Current | Alternative | 6-day ~token impact (no trunc) |
|----------|---------|-------------|-------------------------------:|
| Change bullets per day | 3 | 5 | D ≈ +340 vs B |
| Conflicts per day | 2 (rule only) | 3 (+ bull/bear reads) | not measured; est +400–800 |
| Watchlist items | 2 | 3 | est +80–200 |
| Days in window | 6 | 8 or 10 | linear scale ~×1.33–1.67 |

**Recommendation for review:** decide truncation first (B vs A), then narrative (C vs B), then consider selection expansions only if continuity gaps remain in live output.

---

## 8. Narrative inclusion: costs, benefits, tradeoffs

### 8.1 Potential benefits

1. **Regime story coherence** — model sees how prior days *framed* the arc, not just bullet deltas.
2. **Richer `what_changed_today`** — today's changes can reference yesterday's stated base case in natural language.
3. **Conflict continuity** — narratives often restate how tensions resolved or persisted.
4. **Operator auditability** — memory block alone reads like a mini briefing without opening JSON.

### 8.2 Potential costs and risks

1. **Stale anchoring** — narrative embeds **prior** MC probabilities, levels, and action rationale that may contradict **today's** `analysis_context` after enforcement.
2. **Double counting** — Pass 2 already writes a fresh narrative from validated state; memory narrative duplicates that job.
3. **Action inertia** — model may **hold prior posture language** (e.g. repeated "trim bias") when today's chart read warrants a shift.
4. **Numeric leakage** — narratives include prices and percentages (`7,599.96`, `63%`, `7,695`) despite PR-3 excluding numerics elsewhere — **undermines the categorical-only design**.
5. **Token creep** — option C ≈ pre-PR-3 memory size without delivering the old design's completeness (still no full matrix/MC in memory).

### 8.3 Hypotheses to test (for Perplexity / live A-B)

| Hypothesis | If true | If false |
|------------|---------|----------|
| H1: Truncation hurts continuity | B improves `what_changed_today` quality vs A | A is sufficient; save tokens |
| H2: Narrative improves regime tracking | C reduces contradictory day-over-day posture shifts | C increases anchoring to stale prose |
| H3: Narrative adds numeric staleness bugs | Reports cite prior close/ERP despite header | Header + enforcement sufficient |
| H4: B is the sweet spot | Best quality/token ratio | Need C or expanded selection limits |

### 8.4 Suggested evaluation protocol

1. Pick 3 dates with chart packs (e.g. re-run 6/10, 6/12, plus one new day).
2. Run each date **three times** with memory variants injected (feature flag or branch):
   - A: current truncated
   - B: no truncation
   - C: no truncation + narrative
3. Score blind (operator or LLM judge) on:
   - Continuity accuracy (references real prior deltas, not hallucinated)
   - Freshness (today's close/MC match `analysis_context`, not memory)
   - Action appropriateness (no undue inertia)
   - Conflict reconciliation quality
4. Compare token usage from `run_log.json` / provider metrics.

---

## 9. Signal analysis framework (value vs bias)

Use this rubric when reviewing options:

### 9.1 Continuity signals (want more of)

- Correct identification of **regime arc** persistence or transition
- `what_changed_today` that cites **real** prior watchlist items resolving or persisting
- Action normalization stable unless **today's evidence** triggers shift
- Conflict IDs/themes carried forward without re-inventing new IDs each day

### 9.2 Bias / failure modes (want less of)

- **Narrative numerics** overriding precompute (close, MC %, Fib levels from memory)
- **Posture inertia** — "trim bias" repeated because memory said so, not charts
- **Hallucinated continuity** — referencing events not in prior states (truncation may *cause* this by cutting context)
- **Prompt dilution** — memory so long model under-attends to today's chart evidence
- **Contradiction blindness** — memory says melt-up favored; today's MC after enforcement says downside-first

### 9.3 Design principle tension

PR-3 explicitly chose **posture snapshot** over **narrative replay** to prevent (2) and (4). Option C partially reverses that trade. Option B honors selection discipline while fixing the readability failure mode of truncation.

---

## 10. Decision matrix (for reviewer)

| Criterion | A Current | B No trunc | C + narrative |
|-----------|:---------:|:----------:|:-------------:|
| Readability | Poor (ellipsis) | Good | Good |
| Token cost (6-day) | ~1,150 | ~2,070 | ~3,320 |
| Numeric staleness risk | Low | Low–Med (text has some numbers in deltas) | **High** |
| Anchoring / inertia risk | Low | Low–Med | **Med–High** |
| Implementation effort | — | Small | Small+ |
| Alignment with PR-3 philosophy | Full | **Strong** | Partial reversal |

**Engine team decision:** **Option B** — ship no truncation on selected fields; narrative deferred.

---

## 11. Questions for external reviewer (Perplexity)

Please analyze and recommend:

1. **Truncation:** Is removing truncation on already-selected fields clearly net-positive given +650–920 tokens (6-day)? Any downside beyond token cost?

2. **Narrative:** Given option C ≈ old ~3,700-token memory budget, does including `narrative_summary` improve next-day analysis quality enough to justify **numeric staleness** and **action inertia** risks?

3. **Selection limits:** Should we expand beyond 3 changes / 2 conflicts before adding narrative? What limits would you set for a 6-day SPX macro regime tracker?

4. **Conflict detail:** Is full `framework_rule` sufficient, or do **bullish_read / bearish_read** belong in memory (estimated +400–800 tokens)?

5. **Bias test:** Read samples A vs B vs C (linked above). For the 2026-06-08 session, which memory block would produce the **best** `what_changed_today` and **least biased** recommended action — and why?

6. **Watchlist:** Is the footer watchlist (2 items, eligibility rules) sufficient, or should per-day `open_questions` appear in day blocks when truncated today?

7. **Final recommendation:** Choose A, B, C, or a hybrid (e.g. B + narrative only for most recent 1–2 days).

---

## 12. Implementation checklist (post-decision)

- [x] Update `_format_day`, `_conflict_line`, `_build_unresolved_watchlist` — Option B
- [x] Revise `tests/test_memory_rollup.py`
- [x] Update PR-3 doc + this brief
- [ ] Regenerate `memory/rolling/recent_summary.md` via `rebuild-summary` (operator)
- [ ] Optional: A/B flag for narrative experiment (deferred)
- [ ] Re-run 2026-06-10 and 2026-06-12 chart analyses with updated rollup

---

## 13. Related files

| File | Role |
|------|------|
| [`src/memory.py`](../src/memory.py) | Rollup formatter |
| [`src/prompts.py`](../src/prompts.py) | `_optional_memory_block()` wrapper |
| [`src/analysis_engine.py`](../src/analysis_engine.py) | Live run injection |
| [`src/migrate_perplexity.py`](../src/migrate_perplexity.py) | Backfill always injects memory |
| [`docs/PR-3-memory-rollup-overhaul.md`](PR-3-memory-rollup-overhaul.md) | Current contract |
| [`docs/samples/memory-rollup-2026-06-08-context/`](samples/memory-rollup-2026-06-08-context/) | **A / B / C samples** |

---

*Generated 2026-06-21 from production June 2026 backfill states. Token counts reproducible via scripts in repo conversation history or by regenerating samples from `memory/daily_states/`.*
