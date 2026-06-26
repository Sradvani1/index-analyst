# Agent workflow

## Loop

```
PLAN  →  IMPLEMENT  →  REVIEW  →  RECORD
```

| Phase | Tools | Artifact |
|-------|-------|----------|
| **Plan** | Plan mode; `/sharpen-plan`; Ask mode | `.cursor/plans/<slug>_<id>.plan.md` |
| **Implement** | `/implement`; `/tdd`; `/diagnosing-bugs` | Code + tests in `spx-analyst/` |
| **Review** | `/review` | Fixes before Record |
| **Record** | PR doc | `spx-analyst/docs/PR-N-<slug>.md` |

Active work → plan. Completed work → PR doc. Small follow-ups can skip Plan and Record.

**Commands** (`/sharpen-plan`, `/implement`, `/review`) are global Cursor commands in `~/.cursor/commands/`, not in this repo.

---

## Plan

**Plan mode** for features, refactors, or non-trivial work.

**Ask mode** to read the codebase before scoping — no edits.

**`/sharpen-plan`** when the plan exists but scope or tradeoffs are still fuzzy.

**`design.md`** when touching `spx-analyst/web/`.

### Plan file

- Location: `.cursor/plans/<slug>_<id>.plan.md` — one feature per file
- Frontmatter: `name`, `overview`, `todos[]` with `id`, `content`, `status`
- Body: decision summary, acceptance criteria, files in scope, `Builds on` PR links
- Todos are vertical slices — independently implementable steps

| Todo status | Meaning |
|-------------|---------|
| `pending` | Not started |
| `in_progress` | In progress |
| `completed` | Done and verified |
| `cancelled` | Dropped |

---

## Implement

| Tool | When |
|------|------|
| `/implement` | Default — features, UI, wiring, small fixes |
| `/tdd` | New or changed logic in `spx-analyst/src/` |
| `/diagnosing-bugs` | Regressions, pipeline failures |

`/tdd` builds behavior test-first. `/diagnosing-bugs` finds why existing behavior broke.

Tests: `pytest` from `spx-analyst/`.

---

## Review

**`/review`** before the PR doc on substantial work. For ad-hoc fixes, review against what was asked in chat.

---

## Record

**Path:** `spx-analyst/docs/PR-N-<kebab-slug>.md`

**Numbering:** Next integer after existing `PR-N-*.md` files (highest: **PR-9** → next **PR-10**). Decimal (`PR-3.1`) only for follow-ups to that parent PR.

Update `spx-analyst/README.md` when the PR doc is substantial.

Link the PR doc from the plan. Mark plan todos `completed`.

### PR doc template

```markdown
# PR-N: Short Title

**Status:** Complete | In progress  
**Framework version:** `daily-2026-06` (if applicable)  
**Builds on:** [PR-M: …](PR-M-….md)  
**Plan:** [.cursor/plans/<plan-file>.plan.md](../../.cursor/plans/…)

## Summary

One paragraph: what changed and why.

## Problem / motivation

## Solution

## Files touched

| File | Change |

## Tests / verification

## Acceptance criteria (from plan)

- [ ] …
```

---

## Typical sequences

| Situation | Flow |
|-----------|------|
| Engine feature | Plan → `/sharpen-plan`? → `/tdd` or `/implement` → `/review` → PR doc |
| UI feature | Plan → `/sharpen-plan`? → `design.md` → `/implement` → `/review` → PR doc |
| Bug | Ask mode? → `/diagnosing-bugs` → `/implement` → `/review` |
| Small fix | `/implement` → `/review` |

---

## Before coding — read order

1. Active plan (or request in chat)
2. `design.md` — web work
3. Prior PR docs from the plan's `Builds on`
4. `spx-analyst/README.md` — pipeline, run commands
5. `spx-analyst/framework/` — framework specs

**Vocabulary:** Pass 1, Pass 2, `signals` contract, decision matrix, `analysis_context` — follow naming in PR docs and framework. Ask mode or ask before inventing new terms.

**Layout:** Engine `spx-analyst/src/` · Web `spx-analyst/web/` · Tests `spx-analyst/tests/` · PR history `spx-analyst/docs/PR-*.md`
