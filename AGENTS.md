# Index Analyst — agent guide

Daily SPX tactical analysis: Python engine + Next.js publication UI.

**Start here:** [docs/agents/guide.md](docs/agents/guide.md) — workflow, commands, skills, and when to use each.

## Quick reference

| Command / skill | When |
|-----------------|------|
| `/implement` | Building the plan |
| `/review` | Checking work against plan before the PR doc |
| `/grill-with-docs` | Sharpening a plan; building `CONTEXT.md` |
| `/tdd` | Test-first engine changes |
| `/diagnosing-bugs` | Methodical debugging |
| `/find-skills` | Discover or install agent skills |

## Further reading

| Doc | Covers |
|-----|----------|
| [guide.md](docs/agents/guide.md) | Full workflow and tool usage |
| [workflow.md](docs/agents/workflow.md) | Loop diagram and PR doc template |
| [issue-tracker.md](docs/agents/issue-tracker.md) | Plans, todos, artifacts |
| [domain.md](docs/agents/domain.md) | Read order, repo layout, vocabulary |

## Cursor Cloud specific instructions

The startup update script provisions the Python venv at `spx-analyst/.venv` and runs `npm install` in `spx-analyst/web`. Activate the venv (`source spx-analyst/.venv/bin/activate`) before any `python`/`pytest`/`uvicorn` command. Standard commands live in `spx-analyst/README.md`.

- **Engine tests/lint:** run `pytest` and `npm run lint` (in `web/`) — both run fully offline; tests mock Anthropic + yfinance, so no secrets/network are needed.
- **Live engine runs** (`python -m src.cli run`) need `ANTHROPIC_API_KEY` in `spx-analyst/.env` plus internet for yfinance; not required for viewer or test work.
- **Running the web viewer needs two services:** FastAPI API on `:8000` (`uvicorn src.web.app:app --host 127.0.0.1 --port 8000`) and Next.js on `:3000` (`npm run dev` in `web/`). The UI shows a "backend unavailable" page if the API is not up; `web/next.config.ts` rewrites `/api/*` to `127.0.0.1:8000`.
- **The viewer needs seeded `memory/` data** (≥1 state+report pair) or pages are empty. Without a live engine run, seed offline with the snippet in `README.md` (`## Phase 2 web viewer` → "Prerequisites — seed `memory/`"), which uses `tests.conftest.SAMPLE_STATE`. Do not use `memory-archive/` legacy samples — the API skips them.
