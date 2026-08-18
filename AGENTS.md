# Index Analyst — agent guide

Daily SPX tactical analysis: Python engine + Next.js publication UI.

**Workflow:** [docs/agents/guide.md](docs/agents/guide.md) — Plan / Implement / Review / Record loop.

## Commands

| Command | When |
|---------|------|
| `/sharpen-plan` | Stress-test a plan before implementation |
| `/implement` | Build — planned work or small follow-ups |
| `/review` | Check work against requirements before recording |

## Skills

| Skill | When |
|-------|------|
| `/tdd` | Test-first engine changes in `spx-analyst/src/` |
| `/diagnosing-bugs` | Something broken, failing, or regressing |

## Repository structure

Two packages under `spx-analyst/`:
- **`src/`** — Python engine (CLI entrypoint, schemas, pipeline, FastAPI web API)
- **`web/`** — Next.js 16 + React 19 + Tailwind v4 + shadcn publication UI

Root `design.md` governs all web UI work (color, typography, layout tokens).

## Python engine

```bash
cd spx-analyst && source .venv/bin/activate

# Entrypoints (both equivalent):
python -m src.cli --help
spx-analyst --help                   # after pip install -e ".[dev]"

# Daily pipeline:
python -m src.cli import-run --date YYYY-MM-DD    # import charts from Images/<date>/
python -m src.cli run --date YYYY-MM-DD           # full two-pass analysis
python -m src.cli generate-podcast --date YYYY-MM-DD  # ~3-min podcast MP3 + script from the Substack article

# Tests:
pytest                                          # all tests (mock provider, offline)
pytest -m live                                  # tests requiring live API keys
```

Key env vars (`.env`): `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `OPENAI_VECTOR_STORE_ID`. Podcast extras: `GOOGLE_API_KEY`, `SPX_GOOGLE_TTS_MODEL` (default `gemini-3.1-flash-tts-preview`), `SPX_PODCAST_VOICE` (default `Orus`). ffmpeg/ffprobe are required for MP3 encoding.

Run artifacts are gitignored (`output/*/`, `data/runs/*/charts/`, `memory/`). `memory/` dirs exist for the web viewer but their JSON/MD content is not committed; the podcast MP3 lives in `output/<date>/` (gitignored), while the script text is mirrored to `memory/daily_reports/` for the web viewer.

## Web UI

```bash
cd spx-analyst/web && npm run dev          # Next.js on :3000
cd spx-analyst && uvicorn src.web.app:app --host 127.0.0.1 --port 8000   # FastAPI

npm run lint                               # eslint only (no typecheck command)
```

Next.js rewrites `/api/*` → FastAPI at `http://127.0.0.1:8000/api/*`. Both servers required for full UI.

## PR docs

`spx-analyst/docs/PR-N-<slug>.md` — highest existing: PR-22. Use next integer; decimal for follow-ups (e.g. PR-4.1). Update `spx-analyst/README.md` for substantial changes.

## Design

`design.md` at repo root has the full design system (color palette, typography scale, spacing, component styling, responsive breakpoints). Consult before any web UI work.
