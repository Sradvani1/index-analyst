# Work tracking

## Artifacts

| Artifact | Location | Role |
|----------|----------|------|
| **Active plan** | `.cursor/plans/<slug>_<id>.plan.md` | Scope, todos, acceptance criteria |
| **Implementation record** | `spx-analyst/docs/PR-N-<slug>.md` | What was built, how, tests, files touched |
| **Design intent** | `design.md` (repo root) | Publication UI |
| **Engine specs** | `spx-analyst/docs/`, `spx-analyst/framework/` | Framework and prior PRs |

## Plan conventions

- One feature per plan file under `.cursor/plans/`
- YAML frontmatter: `name`, `overview`, `todos[]` with `id`, `content`, `status`
- Body: decision summary, acceptance criteria, files in scope, `Builds on` PR links
- `todos` are vertical slices — independently implementable steps

## Todo status

| Status | Meaning |
|--------|---------|
| `pending` | Not started |
| `in_progress` | Currently being implemented |
| `completed` | Done and verified |
| `cancelled` | Dropped |
