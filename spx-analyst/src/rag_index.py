"""Section-vector RAG indexing for daily investor reports."""

from __future__ import annotations

import datetime as dt
import json
import logging
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .config import Settings, get_settings
from .files import read_text
from .prompts import INVESTOR_REPORT_SECTIONS
from .schemas import ArcBriefCaps

logger = logging.getLogger(__name__)

_SECTION_HEADING_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
_CANONICAL_SECTIONS = {s.lower(): s for s in INVESTOR_REPORT_SECTIONS}


class RagIndexError(Exception):
    """Hard failure during RAG indexing."""


class RagSectionEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    section: str
    openai_file_id: str


class RagIndexManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: str
    vector_store_id: str
    sections: list[RagSectionEntry]
    indexed_at: str = Field(description="UTC ISO-8601 timestamp")


class OpenAIUploadClient(Protocol):
    def upload_section(self, *, filename: str, content: str) -> str:
        """Upload one section file; return OpenAI file id."""

    def delete_file(self, file_id: str) -> None:
        """Delete one file (removes it from the vector store)."""

    def list_vector_store_files(self) -> list[str]:
        """Return all file IDs currently attached to the vector store."""


def split_report_sections(report_md: str) -> dict[str, str]:
    """Split an assembled investor report into canonical section bodies."""
    matches = list(_SECTION_HEADING_RE.finditer(report_md))
    sections: dict[str, str] = {}
    for idx, match in enumerate(matches):
        raw_title = match.group(1).strip()
        canonical = _CANONICAL_SECTIONS.get(raw_title.lower())
        if canonical is None:
            continue
        start = match.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(report_md)
        sections[canonical] = report_md[start:end].strip()
    return sections


def _section_upload_content(date: str, section: str, body: str) -> str:
    return (
        f"---\n"
        f"report_date: {date}\n"
        f"section: {section}\n"
        f"source: spx-analyst daily report\n"
        f"---\n\n"
        f"{body}\n"
    )


def _atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def _require_openai_settings(settings: Settings) -> None:
    missing = [
        name
        for name, value in (
            ("OPENAI_API_KEY", settings.openai_api_key),
            ("OPENAI_VECTOR_STORE_ID", settings.openai_vector_store_id),
        )
        if not value.strip()
    ]
    if missing:
        raise RagIndexError(f"missing required OpenAI env var(s): {', '.join(missing)}")


class LiveOpenAIUploadClient:
    """Upload section files to OpenAI and attach them to the configured vector store."""

    def __init__(self, settings: Settings) -> None:
        _require_openai_settings(settings)
        self._settings = settings
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RagIndexError(
                "openai package not installed; add openai>=1.40.0 to dependencies"
            ) from exc
        self._client = OpenAI(api_key=settings.openai_api_key)
        self._vector_store_id = settings.openai_vector_store_id

    def upload_section(self, *, filename: str, content: str) -> str:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".md",
            delete=False,
        ) as handle:
            handle.write(content)
            temp_path = Path(handle.name)

        try:
            with temp_path.open("rb") as handle:
                file_obj = self._client.files.create(file=handle, purpose="assistants")
            self._client.vector_stores.files.create(
                vector_store_id=self._vector_store_id,
                file_id=file_obj.id,
            )
            return file_obj.id
        except RagIndexError:
            raise
        except Exception as exc:
            raise RagIndexError(f"OpenAI upload failed for {filename}: {exc}") from exc
        finally:
            temp_path.unlink(missing_ok=True)

    def delete_file(self, file_id: str) -> None:
        try:
            self._client.vector_stores.files.delete(
                vector_store_id=self._vector_store_id,
                file_id=file_id,
            )
        except RagIndexError:
            raise
        except Exception as exc:
            raise RagIndexError(f"OpenAI delete failed for {file_id}: {exc}") from exc

    def list_vector_store_files(self) -> list[str]:
        file_ids: list[str] = []
        cursor: str | None = None
        while True:
            kwargs: dict[str, str] = {"vector_store_id": self._vector_store_id}
            if cursor:
                kwargs["after"] = cursor
            page = self._client.vector_stores.files.list(**kwargs)
            file_ids.extend(f.id for f in page.data)
            if not page.has_more:
                break
            cursor = page.data[-1].id
        return file_ids


def index_report_rag(
    date: str,
    *,
    settings: Settings | None = None,
    client: OpenAIUploadClient | None = None,
) -> RagIndexManifest:
    """Split, upload, and persist manifest for one daily report."""
    settings = settings or get_settings()
    report_path = settings.daily_reports_dir / f"{date}-analysis.md"
    if not report_path.is_file():
        raise RagIndexError(f"report not found for {date}: {report_path}")

    sections = split_report_sections(read_text(report_path))
    missing = [s for s in INVESTOR_REPORT_SECTIONS if s not in sections]
    if missing:
        raise RagIndexError(
            f"report for {date} is missing section(s): {', '.join(missing)}"
        )

    upload_client = client or LiveOpenAIUploadClient(settings)
    manifest_path = settings.rag_dir / f"{date}.json"
    old_ids: list[str] = []
    if manifest_path.is_file():
        try:
            old = RagIndexManifest.model_validate_json(
                manifest_path.read_text(encoding="utf-8")
            )
            old_ids = [e.openai_file_id for e in old.sections]
        except (ValidationError, ValueError):
            logger.warning("could not read prior manifest %s; skipping cleanup", manifest_path)

    entries: list[RagSectionEntry] = []
    for section in INVESTOR_REPORT_SECTIONS:
        body = sections[section]
        content = _section_upload_content(date, section, body)
        slug = section.lower().replace(" ", "_").replace("/", "_")
        try:
            file_id = upload_client.upload_section(
                filename=f"{date}_{slug}.md",
                content=content,
            )
        except RagIndexError:
            raise
        except Exception as exc:
            raise RagIndexError(
                f"upload failed for section '{section}': {exc}"
            ) from exc
        entries.append(RagSectionEntry(section=section, openai_file_id=file_id))

    manifest = RagIndexManifest(
        date=date,
        vector_store_id=settings.openai_vector_store_id,
        sections=entries,
        indexed_at=dt.datetime.now(dt.timezone.utc).isoformat(),
    )
    _atomic_write_json(manifest_path, manifest.model_dump(mode="json"))

    for file_id in old_ids:
        try:
            upload_client.delete_file(file_id)
        except RagIndexError as exc:
            logger.warning("could not delete superseded file %s: %s", file_id, exc)

    pruned = prune_retention(settings=settings, client=upload_client)
    if pruned:
        logger.info("retention pruned %d old date(s): %s", len(pruned), ", ".join(pruned))

    swept = sweep_store_orphans(settings=settings, client=upload_client)
    if swept:
        logger.info("store sweep removed %d orphan file(s)", len(swept))

    logger.info("indexed %d sections for %s → %s", len(entries), date, manifest_path)
    return manifest


def list_report_dates(settings: Settings | None = None) -> list[str]:
    settings = settings or get_settings()
    reports_dir = settings.daily_reports_dir
    if not reports_dir.is_dir():
        return []
    dates = [
        p.name.replace("-analysis.md", "")
        for p in reports_dir.glob("*-analysis.md")
    ]
    return sorted(dates)


def backfill_rag_index(
    *,
    settings: Settings | None = None,
    client: OpenAIUploadClient | None = None,
) -> list[RagIndexManifest]:
    settings = settings or get_settings()
    manifests: list[RagIndexManifest] = []
    for date in list_report_dates(settings):
        manifests.append(index_report_rag(date, settings=settings, client=client))
    return manifests


def prune_retention(
    *,
    settings: Settings | None = None,
    client: OpenAIUploadClient | None = None,
    keep: int | None = None,
) -> list[str]:
    """Delete manifests (and their vector-store files) older than the newest ``keep`` dates.

    ``keep`` defaults to ``ArcBriefCaps.MAX_SESSIONS`` so the retrievable window stays
    aligned with the chat assistant's recent arc. Unreadable manifests are removed
    without file deletion (their files surface as orphans in the cleanup sweep).
    """
    settings = settings or get_settings()
    if keep is None:
        keep = ArcBriefCaps.MAX_SESSIONS
    if keep < 1:
        raise ValueError("keep must be >= 1")

    dates = sorted(
        (p.name[: -len(".json")] for p in settings.rag_dir.glob("*.json")),
        reverse=True,
    )
    stale = dates[keep:]
    if not stale:
        return []

    upload_client = client or LiveOpenAIUploadClient(settings)
    pruned: list[str] = []
    for date in stale:
        path = settings.rag_dir / f"{date}.json"
        try:
            manifest = RagIndexManifest.model_validate_json(
                path.read_text(encoding="utf-8")
            )
        except (ValidationError, ValueError, OSError):
            logger.warning("could not read manifest %s; removing without file cleanup", path)
        else:
            for entry in manifest.sections:
                try:
                    upload_client.delete_file(entry.openai_file_id)
                except RagIndexError as exc:
                    logger.warning(
                        "could not delete pruned file %s: %s", entry.openai_file_id, exc
                    )
        path.unlink(missing_ok=True)
        pruned.append(date)
    return pruned


def sweep_store_orphans(
    *,
    settings: Settings | None = None,
    client: OpenAIUploadClient | None = None,
) -> list[str]:
    """Delete vector-store files not referenced by any manifest.

    Reconciles the physical store to the current manifest corpus so the store
    holds exactly the retained dates. Runs after every successful index.
    """
    settings = settings or get_settings()
    keep_ids: set[str] = set()
    for path in settings.rag_dir.glob("*.json"):
        try:
            manifest = RagIndexManifest.model_validate_json(
                path.read_text(encoding="utf-8")
            )
        except (ValidationError, ValueError, OSError):
            continue
        keep_ids.update(entry.openai_file_id for entry in manifest.sections)

    upload_client = client or LiveOpenAIUploadClient(settings)
    orphan_ids = sorted(set(upload_client.list_vector_store_files()) - keep_ids)
    for file_id in orphan_ids:
        try:
            upload_client.delete_file(file_id)
        except RagIndexError as exc:
            logger.warning("could not delete orphan file %s: %s", file_id, exc)
    return orphan_ids


def format_index_failure_message(date: str) -> str:
    return (
        f"ERROR: RAG indexing failed for {date} (report saved to memory/).\n"
        f"Retry: python -m src.cli index-rag --date {date}"
    )


def emit_index_failure(date: str, exc: Exception) -> None:
    print(format_index_failure_message(date), file=sys.stderr)
    logger.error("RAG indexing failed for %s: %s", date, exc)


def index_rag_or_fail(
    date: str,
    *,
    settings: Settings | None = None,
    client: OpenAIUploadClient | None = None,
) -> RagIndexManifest:
    """Index report sections; on failure emit stderr retry hint and re-raise."""
    try:
        return index_report_rag(date, settings=settings, client=client)
    except RagIndexError as exc:
        emit_index_failure(date, exc)
        raise
