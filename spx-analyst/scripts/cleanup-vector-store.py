#!/usr/bin/env python3
"""Drain orphaned files from the OpenAI vector store.

Keeps exactly the section files recorded in `memory/rag/*.json` manifests (the
canonical current corpus) and deletes everything else — including any
superseded generations left by append-only indexing.

Optional retention: `--keep N` trims the manifests (and their store files) down
to the N newest trade dates before the orphan sweep, matching the chat arc.

Usage (from spx-analyst/):
    source .venv/bin/activate
    python scripts/cleanup-vector-store.py [--dry-run] [--keep N]

Requires OPENAI_API_KEY and OPENAI_VECTOR_STORE_ID in .env.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from src.config import get_settings  # noqa: E402
from src.rag_index import prune_retention  # noqa: E402


def _list_vector_store_files(client, vector_store_id: str) -> list:
    files: list = []
    cursor: str | None = None
    while True:
        kwargs = {"vector_store_id": vector_store_id}
        if cursor:
            kwargs["after"] = cursor
        page = client.vector_stores.files.list(**kwargs)
        data = page.data if hasattr(page, "data") else page
        files.extend(data)
        if not getattr(page, "has_more", False):
            break
        cursor = getattr(page, "last_id", None) or data[-1].id
    return files


def _manifest_file_ids(rag_dir: Path) -> set[str]:
    keep: set[str] = set()
    for path in sorted(rag_dir.glob("*.json")):
        try:
            manifest = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            print(f"WARN: skipping unreadable manifest {path}: {exc}", file=sys.stderr)
            continue
        keep.update(entry["openai_file_id"] for entry in manifest.get("sections", []))
    return keep


def _manifest_ids_for_dates(rag_dir: Path, dates: list[str]) -> set[str]:
    ids: set[str] = set()
    for date in dates:
        try:
            manifest = json.loads((rag_dir / f"{date}.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        ids.update(entry["openai_file_id"] for entry in manifest.get("sections", []))
    return ids


def main() -> None:
    parser = argparse.ArgumentParser(description="Drain orphaned files from the vector store.")
    parser.add_argument("--dry-run", action="store_true", help="report without deleting")
    parser.add_argument(
        "--workers", type=int, default=8, help="parallel delete workers (default 8)"
    )
    parser.add_argument(
        "--keep",
        type=int,
        default=None,
        help="trim manifests to the N newest trade dates before sweeping (matches the arc)",
    )
    args = parser.parse_args()
    if args.keep is not None and args.keep < 1:
        parser.error("--keep must be >= 1")

    settings = get_settings()
    api_key = settings.openai_api_key.strip()
    vector_store_id = settings.openai_vector_store_id.strip()
    if not api_key:
        print("ERROR: set OPENAI_API_KEY in spx-analyst/.env first", file=sys.stderr)
        sys.exit(1)
    if not vector_store_id:
        print("ERROR: set OPENAI_VECTOR_STORE_ID in spx-analyst/.env first", file=sys.stderr)
        sys.exit(1)

    try:
        from openai import OpenAI
    except ImportError as exc:
        print("ERROR: openai package not installed", file=sys.stderr)
        raise SystemExit(1) from exc

    # Optional retention trim: prune manifests older than the N newest dates.
    stale_dates: list[str] = []
    if args.keep is not None:
        dates = sorted(
            (p.name[: -len(".json")] for p in settings.rag_dir.glob("*.json")),
            reverse=True,
        )
        stale_dates = dates[args.keep :]
        if stale_dates:
            stale_ids = _manifest_ids_for_dates(settings.rag_dir, stale_dates)
            print(
                f"retention: keep newest {args.keep} date(s); prune "
                f"{len(stale_dates)} manifest(s) / {len(stale_ids)} file(s)",
                flush=True,
            )
            if not args.dry_run:
                pruned = prune_retention(settings=settings, keep=args.keep)
                print(f"pruned {len(pruned)} manifest(s)", flush=True)

    client = OpenAI(api_key=api_key)
    all_files = _list_vector_store_files(client, vector_store_id)
    keep_ids = _manifest_file_ids(settings.rag_dir)
    if args.dry_run and stale_dates:
        keep_ids -= _manifest_ids_for_dates(settings.rag_dir, stale_dates)
    delete_ids = [f.id for f in all_files if f.id not in keep_ids]

    print(
        f"vector store: {len(all_files)} files | keep (manifest): {len(keep_ids)} "
        f"| delete: {len(delete_ids)}",
        flush=True,
    )
    if args.dry_run:
        print("dry-run; no files deleted", flush=True)
        return

    from concurrent.futures import ThreadPoolExecutor, as_completed

    def _delete(file_id: str) -> tuple[str, bool]:
        try:
            client.vector_stores.files.delete(
                vector_store_id=vector_store_id, file_id=file_id
            )
            return file_id, True
        except Exception as exc:  # noqa: BLE001 - best-effort sweep
            message = str(exc)
            if "does not exist" in message or "not found" in message.lower():
                return file_id, True
            return file_id, False

    done = 0
    failures = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(_delete, fid) for fid in delete_ids]
        for future in as_completed(futures):
            file_id, ok = future.result()
            done += 1
            if not ok:
                failures += 1
                print(f"  FAILED {file_id}", file=sys.stderr, flush=True)
            if done % 50 == 0:
                print(f"  deleted {done}/{len(delete_ids)}", flush=True)

    print(f"done: deleted {len(delete_ids) - failures}, failed {failures}", flush=True)
    remaining = _list_vector_store_files(client, vector_store_id)
    print(f"remaining in store: {len(remaining)}", flush=True)


if __name__ == "__main__":
    main()
