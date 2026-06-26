# Workflow: Plan → Implement → Review → Record

Guide: [guide.md](./guide.md)

## Loop

```
┌────────┐   ┌─────────────┐   ┌────────┐   ┌──────────┐
│  PLAN  │ → │ IMPLEMENT   │ → │ REVIEW │ → │  RECORD  │
│ .cursor│   │ /implement  │   │/review │   │ PR-N doc │
│ /plans │   │ /tdd        │   │        │   │          │
└────────┘   └─────────────┘   └────────┘   └──────────┘
```

| Phase | Mode / tools | Artifact |
|-------|--------------|----------|
| **Plan** | Plan mode; `/sharpen-plan`; Ask mode to explore | `.cursor/plans/<slug>_<id>.plan.md` |
| **Implement** | `/implement`; `/tdd` for engine; `/diagnosing-bugs` for bugs | Code + tests in `spx-analyst/` |
| **Review** | `/review` | Fixes before Record |
| **Record** | PR doc | `spx-analyst/docs/PR-N-<slug>.md` |

Plan conventions: [issue-tracker.md](./issue-tracker.md)

## PR doc

**Path:** `spx-analyst/docs/PR-N-<kebab-slug>.md`  
**Numbering:** Next integer `N` after existing `PR-N-*.md` files (highest today: **PR-9** → next is **PR-10**). Decimal suffix only for follow-ups to that parent PR.

```markdown
# PR-N: Short Title

**Status:** Complete | In progress  
**Framework version:** `daily-2026-06` (if applicable)  
**Builds on:** [PR-M: …](PR-M-….md)  
**Plan:** [.cursor/plans/<plan-file>.plan.md](../../.cursor/plans/…)

## Summary

One paragraph: what changed and why.

## Problem / motivation

What was wrong or missing before.

## Solution

How it was solved — layers, modules, key decisions.

## Files touched

| File | Change |

## Tests / verification

What was run and what passed.

## Acceptance criteria (from plan)

- [ ] …
```

Link back to the plan. Update `spx-analyst/README.md` when the PR doc is substantial.
