# Agent workflow guide

## Loop

```
PLAN  →  IMPLEMENT  →  REVIEW  →  RECORD
```

| Phase | Tools | Artifact |
|-------|-------|----------|
| **Plan** | Plan mode; `/sharpen-plan`; Ask mode to explore | `.cursor/plans/<slug>_<id>.plan.md` |
| **Implement** | `/implement`; `/tdd` for engine logic; `/diagnosing-bugs` for bugs | Code + tests in `spx-analyst/` |
| **Review** | `/review` | Fixes before Record |
| **Record** | PR doc | `spx-analyst/docs/PR-N-<slug>.md` |

Active work lives in a plan. Completed work lives in a PR doc.

Not every change needs all four phases. Small follow-ups can go straight to `/implement` → `/review`.

---

## Plan

Use **Plan mode** for features, refactors, or anything non-trivial.

A plan should have:
- Frontmatter `todos[]` with `id`, `content`, `status`
- Acceptance criteria
- Files in scope
- `Builds on` links to prior PR docs

Use **Ask mode** when you need to read the codebase before scoping — no code changes.

Use **`/sharpen-plan`** when the plan exists but scope, tradeoffs, or acceptance criteria are still fuzzy. Point at the plan file; the agent updates it as decisions land.

For UI work, read `design.md` before implementing.

---

## Implement

| Tool | When |
|------|------|
| `/implement` | Default — features, wiring, UI, small fixes |
| `/tdd` | New or changed engine logic in `spx-analyst/src/` |
| `/diagnosing-bugs` | Regressions, pipeline failures, unexpected behavior |

`/tdd` builds behavior test-first. `/diagnosing-bugs` finds why existing behavior broke.

Run tests from `spx-analyst/` (`pytest` for engine).

---

## Review

Run `/review` before writing the PR doc on substantial work.

For ad-hoc fixes, review against what you asked for in chat.

---

## Record

Write `spx-analyst/docs/PR-N-<kebab-slug>.md`. Template: [workflow.md](./workflow.md#pr-doc).

Next integer after existing `PR-N-*.md` files (highest today: **PR-9** → next is **PR-10**). Use a decimal (`PR-3.1`) only for a follow-up to that parent PR.

Update `spx-analyst/README.md` when the PR doc is substantial.

---

## Typical sequences

**Engine feature:** Plan mode → `/sharpen-plan` (optional) → `/tdd` or `/implement` → `/review` → PR doc

**UI feature:** Plan mode → `/sharpen-plan` (optional) → read `design.md` → `/implement` → `/review` → PR doc

**Bug:** Ask mode (if needed) → `/diagnosing-bugs` → `/implement` → `/review`

**Small fix:** `/implement` → `/review`

---

## What to read before coding

1. Active plan (or the request in chat)
2. `design.md` — when touching `spx-analyst/web/`
3. Prior PR docs linked from the plan
4. `spx-analyst/README.md` and `spx-analyst/framework/` for engine context

Details: [domain.md](./domain.md).
