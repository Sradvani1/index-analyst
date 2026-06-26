# Agent workflow guide

How to plan, build, review, and record work on this repo — and when to use each command and skill.

## Overview

Every feature follows the same loop:

```
PLAN  →  IMPLEMENT  →  REVIEW  →  RECORD
```

| Phase | You / agent do | Primary artifact |
|-------|----------------|------------------|
| **Plan** | Scope the work, break into todos, define acceptance criteria | `.cursor/plans/<slug>_<id>.plan.md` |
| **Implement** | Write code and tests | `spx-analyst/src/`, `spx-analyst/web/`, `spx-analyst/tests/` |
| **Review** | Compare the build against the plan | Fixes in chat before recording |
| **Record** | Write what was built and why | `spx-analyst/docs/PR-N-<slug>.md` |

**Active work** lives in a Cursor plan. **Completed work** lives in a PR doc. Link them both ways.

---

## Phase 1 — Plan

### When

Starting a new feature, a significant refactor, or any work that spans more than a quick fix.

### How

1. Open **Cursor Plan mode** and produce a plan file under `.cursor/plans/`.
2. Include YAML frontmatter with `name`, `overview`, and `todos[]` (each with `id`, `content`, `status`).
3. In the body: decision summary, acceptance criteria, files in scope, and `Builds on` links to prior PR docs.
4. Break work into **vertical slices** — todos that can each be implemented and verified on their own.

### Commands and skills

| Tool | Use when | What it does |
|------|----------|--------------|
| **Plan mode** | Always, for the first draft | Cursor generates the structured plan file |
| **Ask mode** | You need to understand existing code before planning | Read-only exploration — no code changes |
| **`/grill-with-docs`** | The plan is vague, terminology is fuzzy, or tradeoffs are unresolved | Runs a structured interview to sharpen scope and decisions; creates or updates `CONTEXT.md` (domain glossary) and ADRs in `docs/adr/` as needed |

**`/grill-with-docs` is for planning, not building.** Run it when you want the plan and domain vocabulary solid before `/implement`.

### Before leaving Plan

- Acceptance criteria are specific enough to check in Review.
- Todos are `pending` and ordered.
- Prior PR docs are linked if the feature builds on earlier work.
- For UI work, `design.md` has been considered.

---

## Phase 2 — Implement

### When

The plan exists and you are ready to write code.

### How

1. Switch to **Agent mode**.
2. Point the agent at the active plan file.
3. Work through todos one at a time; mark each `in_progress` then `completed` as you go.
4. Run tests from `spx-analyst/` (`pytest` for engine; Next.js tooling for web).

### Commands and skills

| Tool | Use when | What it does |
|------|----------|--------------|
| **`/implement`** | Default for building the plan | Proceeds with implementation: simple typed code, proper error handling, concise summary when done |
| **`/tdd`** | Changing `spx-analyst/src/` logic that should have pytest coverage | Test-driven development: one failing test → minimal implementation → repeat (vertical slices, not "write all tests then all code") |
| **`/diagnosing-bugs`** | Something is broken, failing, slow, or behaving unexpectedly | Structured debug loop: build a tight pass/fail signal first, then bisect, hypothesize, and fix |

**Choosing between `/implement` and `/tdd`:**

- **New engine behavior, schema rules, precompute logic, validation** → `/tdd`
- **UI components, wiring, config, docs, straightforward fixes** → `/implement`
- **A test exists but something fails at runtime** → `/diagnosing-bugs` (not `/tdd`)

**`/diagnosing-bugs` vs `/tdd`:** `/tdd` builds correct behavior from tests. `/diagnosing-bugs` finds why existing behavior broke. Use diagnosing when you have a regression or production-style failure; use tdd when you are adding or changing behavior deliberately.

### Repo layout during Implement

| Path | What |
|------|------|
| `spx-analyst/src/` | Python engine, prompts, validation, FastAPI viewer API |
| `spx-analyst/web/` | Next.js 16 publication UI |
| `spx-analyst/tests/` | pytest (run from `spx-analyst/`) |
| `design.md` | Read when touching the publication UI |

---

## Phase 3 — Review

### When

Implementation is complete (or you want a checkpoint before the PR doc).

### How

Run **`/review`**. The agent will:

- Compare changes against the plan and acceptance criteria
- Flag bugs, breaking changes, edge cases, brittle contracts, and security issues
- Propose **minimal, targeted fixes** — not a full rewrite

Fix anything material, then move to Record.

**`/review` is not optional for substantial features.** It is the gate between "code exists" and "work is documented."

---

## Phase 4 — Record

### When

Review is clean (or remaining gaps are explicitly accepted).

### How

Write `spx-analyst/docs/PR-N-<kebab-slug>.md`:

- **Numbering:** next integer `N` after existing `PR-N-*.md` files (next is **PR-9**). Use a decimal (`PR-3.1`) only for a follow-up to that parent PR.
- **Link** to the plan file and any `Builds on` PR docs.
- **Include:** summary, problem, solution, files touched, tests run, acceptance criteria checklist.

Full template: [workflow.md](./workflow.md#pr-doc).

Update `spx-analyst/README.md` implementation records list when the PR doc is substantial.

Mark remaining plan todos `completed`.

---

## Quick reference — all commands and skills

### Your commands (`~/.cursor/commands/`)

These are global Cursor commands you wrote. They apply to any project; this repo uses them as the implementation backbone.

| Command | Phase | Use for |
|---------|-------|---------|
| `/implement` | Implement | Build the plan — default coding command |
| `/review` | Review | Audit changes against plan acceptance criteria |

### Installed agent skills (`~/.agents/skills/`)

These are specialized playbooks the agent loads when invoked.

| Skill | Phase | Use for |
|-------|-------|---------|
| `/grill-with-docs` | Plan | Sharpen plans; resolve terminology; build `CONTEXT.md` |
| `/tdd` | Implement | Test-first engine changes in `spx-analyst/src/` |
| `/diagnosing-bugs` | Implement | Methodical debugging when something breaks |
| `/find-skills` | Any | Search the skills ecosystem and install new capabilities |

### Typical session sequences

**New engine feature:**
```
Plan mode  →  /grill-with-docs (if scope is fuzzy)
/implement or /tdd  →  /review  →  PR doc
```

**Publication UI feature:**
```
Plan mode  →  read design.md
/implement  →  /review  →  PR doc
```

**Regression or pipeline bug:**
```
Ask mode (if unfamiliar)  →  /diagnosing-bugs  →  /implement  →  /review
```

**Exploring the codebase:**
```
Cursor Ask mode
```

---

## Artifacts and where they live

| Artifact | Location | Role |
|----------|----------|------|
| Active plan | `.cursor/plans/<slug>_<id>.plan.md` | Scope, todos, acceptance criteria |
| Implementation record | `spx-analyst/docs/PR-N-<slug>.md` | Completed work history |
| Domain glossary | `CONTEXT.md` (repo root) | SPX vocabulary |
| UI design | `design.md` (repo root) | Publication site intent |
| Engine specs | `spx-analyst/docs/`, `spx-analyst/framework/` | Framework and prior PRs |
| ADRs | `docs/adr/` | Architectural decisions (when present) |

### Plan todo status

| Status | Meaning |
|--------|---------|
| `pending` | Not started |
| `in_progress` | Currently being worked |
| `completed` | Done and verified |
| `cancelled` | Dropped |

---

## What to read before coding

1. Active plan (user points to the file)
2. `CONTEXT.md` — if it exists
3. `design.md` — when touching `spx-analyst/web/`
4. Prior PR docs linked from the plan
5. `spx-analyst/README.md` — pipeline overview
6. `docs/adr/` — when present

Details: [domain.md](./domain.md).

---

## Related docs

| Doc | Contents |
|-----|----------|
| [workflow.md](./workflow.md) | Loop diagram and PR doc template |
| [issue-tracker.md](./issue-tracker.md) | Plan conventions and todo status |
| [domain.md](./domain.md) | Read order, repo layout, vocabulary |
| [AGENTS.md](../../AGENTS.md) | Agent entry point |
