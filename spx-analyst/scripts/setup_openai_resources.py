#!/usr/bin/env python3
"""One-time OpenAI vector store setup for the SPX research assistant.

Usage (from spx-analyst/):
    source .venv/bin/activate
    python scripts/setup_openai_resources.py

Requires OPENAI_API_KEY in .env. Prints OPENAI_VECTOR_STORE_ID to paste into .env.
Chat uses inline instructions via Responses API — no dashboard Assistant object.
"""

from __future__ import annotations

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

    print()
    print("Add these lines to spx-analyst/.env:")
    print(f"OPENAI_VECTOR_STORE_ID={vector_store.id}")
    print("OPENAI_CHAT_MODEL=gpt-5")
    print()
    print("Next: python -m src.cli index-rag --backfill")


if __name__ == "__main__":
    main()
