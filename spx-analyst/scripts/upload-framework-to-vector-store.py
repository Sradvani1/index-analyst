#!/usr/bin/env python3
"""One-time: upload SPX-Daily-Analysis-Framework.md to the OpenAI vector store.

Usage (from spx-analyst/):
    source .venv/bin/activate
    python scripts/upload-framework-to-vector-store.py

Requires OPENAI_API_KEY and OPENAI_VECTOR_STORE_ID in .env.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from src.config import get_settings  # noqa: E402


def main() -> None:
    settings = get_settings()
    api_key = settings.openai_api_key.strip()
    vector_store_id = settings.openai_vector_store_id.strip()
    if not api_key:
        print("ERROR: set OPENAI_API_KEY in spx-analyst/.env first", file=sys.stderr)
        sys.exit(1)
    if not vector_store_id:
        print("ERROR: set OPENAI_VECTOR_STORE_ID in spx-analyst/.env first", file=sys.stderr)
        sys.exit(1)

    framework_path = settings.framework_path
    if not framework_path.is_file():
        print(f"ERROR: framework not found at {framework_path}", file=sys.stderr)
        sys.exit(1)

    try:
        from openai import OpenAI
    except ImportError as exc:
        print("ERROR: openai package not installed", file=sys.stderr)
        raise SystemExit(1) from exc

    client = OpenAI(api_key=api_key)
    content = framework_path.read_text(encoding="utf-8")

    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", suffix=".md", delete=False,
    ) as handle:
        handle.write(content)
        temp_path = Path(handle.name)

    try:
        with temp_path.open("rb") as handle:
            file_obj = client.files.create(file=handle, purpose="assistants")

        client.vector_stores.files.create(
            vector_store_id=vector_store_id,
            file_id=file_obj.id,
        )

        print(f"Uploaded: {framework_path.name} → file {file_obj.id}")
        print(f"Attached to vector store: {vector_store_id}")
    except Exception as exc:
        print(f"ERROR: upload failed: {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        temp_path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
