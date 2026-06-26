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

from pydantic import BaseModel, ConfigDict, Field

from .config import Settings, get_settings
from .files import read_text
from .prompts import INVESTOR_REPORT_SECTIONS

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
    manifest_path = settings.rag_dir / f"{date}.json"
    _atomic_write_json(manifest_path, manifest.model_dump(mode="json"))
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
