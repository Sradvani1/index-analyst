# Domain Docs

How agents should read this repo before exploring or implementing.

## Read order for a new feature

1. **Active plan** — `.cursor/plans/` (user will point to the file)
2. **`CONTEXT.md`** at repo root — if it exists; SPX domain glossary
3. **`design.md`** — when touching `spx-analyst/web/` (publication UI)
4. **Prior PR docs** — `spx-analyst/docs/PR-*.md` linked from the plan's "Builds on"
5. **`spx-analyst/README.md`** — pipeline overview, run commands
6. **`docs/adr/`** — architectural decisions (when present)

If `CONTEXT.md` does not exist, proceed silently. `/grill-with-docs` creates it when terminology gets resolved.

## Repo layout

```
index-analyst/
├── .cursor/plans/           ← plans (source of truth for active work)
├── AGENTS.md                ← agent config index
├── CONTEXT.md               ← domain glossary (lazy)
├── design.md                ← publication UI design
├── docs/
│   ├── agents/              ← guide.md, workflow.md, issue-tracker.md
│   └── adr/                 ← architectural decisions
└── spx-analyst/
    ├── docs/PR-*.md         ← implementation records (completed work)
    ├── framework/           ← SPX analysis framework specs
    ├── src/                 ← Python engine + FastAPI viewer API
    ├── web/                 ← Next.js publication UI
    └── tests/               ← pytest
```

## Vocabulary

Use terms from `CONTEXT.md` when it exists. Until then, follow naming in `spx-analyst/docs/` PR records and framework docs (e.g. Pass 1, Pass 2, `signals` contract, decision matrix, `analysis_context`).

If a term is ambiguous, run `/grill-with-docs` or ask before inventing new names.

## ADR conflicts

If a change contradicts `docs/adr/`, say so explicitly rather than silently overriding.
