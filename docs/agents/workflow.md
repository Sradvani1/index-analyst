# Workflow: Plan → Implement → Review → Record

Full guide with command and skill usage: [guide.md](./guide.md).

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
| **Plan** | Plan mode; refine with `/grill-with-docs` | `.cursor/plans/<slug>_<id>.plan.md` |
| **Implement** | Agent mode + `/implement`; `/tdd` for engine logic; `/diagnosing-bugs` for bugs | Code + tests in `spx-analyst/` |
| **Review** | `/review` against plan acceptance criteria | Fixes before Record |
| **Record** | PR implementation record | `spx-analyst/docs/PR-N-<slug>.md` |

Plan conventions and todo status: [issue-tracker.md](./issue-tracker.md).

## Implement

- Engine: `spx-analyst/src/`
- Web: `spx-analyst/web/` (Next.js 16, shadcn)
- Tests: `pytest` from `spx-analyst/`

## PR doc

**Path:** `spx-analyst/docs/PR-N-<kebab-slug>.md`  
**Numbering:** Next integer `N` after existing `PR-N-*.md` files (highest today: **PR-8** → next is **PR-9**). Use a decimal suffix (`PR-3.1`) only for a follow-up to that parent PR.

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

Link back to the plan. Update `spx-analyst/README.md` implementation records list when the PR doc is substantial.
