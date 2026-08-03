# Shadow Run: OpenAI Pipeline Testing

## Purpose

Side-by-side comparison of OpenAI (gpt-5.6-terra) vs Anthropic (claude-opus-5) for the analytical pipeline.

## Setup

### Environment File

`.env.shadow-openai` contains all settings for the shadow run:

| Setting | Value |
|---------|-------|
| `SPX_LLM_PROVIDER` | `openai` |
| `SPX_OPENAI_PIPELINE_MODEL` | `gpt-5.6-terra` |
| `SPX_OUTPUT_DIR` | `output/shadow-openai` |
| `SPX_MEMORY_DIR` | `output/shadow-openai-memory` |
| `SPX_INCLUDE_MEMORY` | `false` (isolated run) |

### Output Directories

- **Reports & states**: `output/shadow-openai/{date}/`
- **Memory snapshots**: `output/shadow-openai-memory/`
- **No memory injection**: Ensures clean comparison with standard run

## Running the Shadow Test

### Using the Script

```bash
cd spx-analyst
bash scripts/shadow-openai-run.sh
```

### Manual Run

```bash
# Load shadow environment and run
set -a; source .env.shadow-openai; set +a
python -m src.cli run --date 2026-07-21
```

### Direct Command

```bash
SPX_OUTPUT_DIR=output/shadow-openai \
SPX_MEMORY_DIR=output/shadow-openai-memory \
SPX_INCLUDE_MEMORY=false \
SPX_LLM_PROVIDER=openai \
SPX_OPENAI_PIPELINE_MODEL=gpt-5.6-terra \
python -m src.cli run --date 2026-07-21
```

## Comparison

After both runs complete, compare:

| Location | Standard Run | Shadow Run |
|----------|-------------|------------|
| Report | `output/2026-07-21/2026-07-21-analysis.md` | `output/shadow-openai/2026-07-21/2026-07-21-analysis.md` |
| State | `output/2026-07-21/2026-07-21-state.json` | `output/shadow-openai/2026-07-21/2026-07-21-state.json` |
| Request log | `output/2026-07-21/request_snapshot.json` | `output/shadow-openai/2026-07-21/request_snapshot.json` |
| Run log | `output/2026-07-21/run_log.json` | `output/shadow-openai/2026-07-21/run_log.json` |

## Notes

- Uses `gpt-5.6-terra` model with max reasoning
- Isolated memory prevents contamination between runs
- Logs written to `logs/shadow-openai-{date}.log`