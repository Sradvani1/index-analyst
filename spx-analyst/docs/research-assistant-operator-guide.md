# Research Assistant Operator Guide

The local research assistant uses the OpenAI Responses and Conversations APIs.
It answers from the analyst charter, current house view, and recent local state
history. Vector-store indexing and file-search retrieval are not used.

## Configuration

Set these values in `.env`:

```env
OPENAI_API_KEY=sk-...
OPENAI_CHAT_MODEL=gpt-5
```

The OpenAI key is only required for the optional chat assistant or OpenAI
pipeline. Google is the default analytical and Substack provider.

The assistant preload is assembled locally from:

- `framework/chat-assistant-instructions.md`
- The latest validated daily state
- Recent local daily states and structural-bias history

No OpenAI vector store, file upload, or `file_search` tool is required.

## Start Servers

FastAPI:

```bash
cd spx-analyst
source .venv/bin/activate
uvicorn src.web.app:app --host 127.0.0.1 --port 8000 --reload
```

Next.js:

```bash
cd spx-analyst/web
npm install
npm run dev
```

Open `http://localhost:3000/assistant` for the assistant or use the CLI:

```bash
cd spx-analyst
python -m src.cli chat
```

## Verification

- Confirm the latest daily state exists under `memory/daily_states/`.
- Ask for the current posture and verify it matches the latest state.
- Ask how the current structural bias compares with a recent local date.
- Confirm the assistant does not override the published recommended action.
- Confirm sessions persist under `memory/chat/`.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Missing OpenAI environment variable | Chat is enabled without credentials | Set `OPENAI_API_KEY` and `OPENAI_CHAT_MODEL`, or set `SPX_CHAT_ENABLED=false` |
| No daily states found | No completed analysis or seeded memory | Run an analysis or seed local memory |
| UI cannot reach API | FastAPI is not running | Start uvicorn on `127.0.0.1:8000` |
| Session list is empty | Wrong working directory | Run FastAPI from `spx-analyst/` |
