#!/usr/bin/env python3
"""One-time OpenAI vector store + assistant setup for the SPX research assistant.

Usage (from spx-analyst/):
    source .venv/bin/activate
    python scripts/setup_openai_assistant.py

Requires OPENAI_API_KEY in .env. Prints OPENAI_VECTOR_STORE_ID and
OPENAI_ASSISTANT_ID to paste into .env.

Optional: OPENAI_SETUP_MODEL=gpt-4o-mini
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from src.config import get_settings  # noqa: E402


def main() -> None:
    settings = get_settings()
    api_key = settings.openai_api_key.strip()
    if not api_key:
        print("ERROR: set OPENAI_API_KEY in spx-analyst/.env first", file=sys.stderr)
        sys.exit(1)

    try:
        from openai import OpenAI
    except ImportError as exc:
        print("ERROR: openai package not installed", file=sys.stderr)
        raise SystemExit(1) from exc

    instructions_path = settings.chat_assistant_instructions_path
    if not instructions_path.is_file():
        print(f"ERROR: instructions not found: {instructions_path}", file=sys.stderr)
        sys.exit(1)

    instructions = instructions_path.read_text(encoding="utf-8").strip()
    model = os.environ.get("OPENAI_SETUP_MODEL", "gpt-4o").strip() or "gpt-4o"

    client = OpenAI(api_key=api_key)

    print("Creating vector store (max_chunk_size_tokens=1024)...")
    vector_store = client.vector_stores.create(
        name="SPX Analyst daily reports",
        chunking_strategy={
            "type": "static",
            "static": {
                "max_chunk_size_tokens": 1024,
                "chunk_overlap_tokens": 200,
            },
        },
    )

    print(f"Creating assistant (model={model}, file_search)...")
    assistant = client.beta.assistants.create(
        name="SPX Research Assistant",
        instructions=instructions,
        model=model,
        tools=[{"type": "file_search"}],
        tool_resources={"file_search": {"vector_store_ids": [vector_store.id]}},
    )

    print()
    print("Add these lines to spx-analyst/.env:")
    print(f"OPENAI_VECTOR_STORE_ID={vector_store.id}")
    print(f"OPENAI_ASSISTANT_ID={assistant.id}")
    print()
    print("Next: python -m src.cli index-rag --backfill")


if __name__ == "__main__":
    main()
