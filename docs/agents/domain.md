# Domain docs

## Read order

1. **Active plan** — or the request in chat for small changes
2. **`design.md`** — when touching `spx-analyst/web/`
3. **Prior PR docs** — `spx-analyst/docs/PR-*.md` linked from the plan
4. **`spx-analyst/README.md`** — pipeline overview, run commands
5. **`spx-analyst/framework/`** — analysis framework specs

## Repo layout

```
index-analyst/
├── .cursor/plans/           ← active work
├── AGENTS.md
├── design.md                ← publication UI
├── docs/agents/             ← workflow docs
└── spx-analyst/
    ├── docs/PR-*.md         ← completed work
    ├── framework/
    ├── src/
    ├── web/
    └── tests/
```

## Vocabulary

Follow naming in `spx-analyst/docs/` PR records and `spx-analyst/framework/` (e.g. Pass 1, Pass 2, `signals` contract, decision matrix, `analysis_context`).

If a term is ambiguous, use Ask mode to explore the codebase or ask before inventing new names.
