"""Tests for section-vector RAG indexing."""

from __future__ import annotations

import json

import pytest

from src.prompts import INVESTOR_REPORT_SECTIONS
from src.rag_index import (
    RagIndexError,
    backfill_rag_index,
    index_report_rag,
    split_report_sections,
)
from src.schemas import DailyState

from tests.conftest import SAMPLE_STATE, make_settings
from tests.fixtures.investor_report import assembled_report_for_state


class FakeUploadClient:
    def __init__(self) -> None:
        self.uploads: list[tuple[str, str]] = []
        self._counter = 0

    def upload_section(self, *, filename: str, content: str) -> str:
        self.uploads.append((filename, content))
        self._counter += 1
        return f"file_fake_{self._counter}"


@pytest.fixture
def rag_settings(tmp_path):
    settings = make_settings(tmp_path)
    return settings.model_copy(
        update={
            "openai_api_key": "test-key",
            "openai_vector_store_id": "vs_test",
        }
    )


def _write_report(settings, date: str, report_md: str) -> None:
    path = settings.daily_reports_dir / f"{date}-analysis.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report_md, encoding="utf-8")


def test_split_report_sections_all_nine(rag_settings):
    state = DailyState.model_validate({**SAMPLE_STATE, "date": "2026-06-12"})
    report = assembled_report_for_state(state, date="2026-06-12")
    sections = split_report_sections(report)

    assert set(sections) == set(INVESTOR_REPORT_SECTIONS)
    for section in INVESTOR_REPORT_SECTIONS:
        assert sections[section].startswith(f"## {section}")


def test_index_report_rag_writes_manifest(rag_settings):
    state = DailyState.model_validate({**SAMPLE_STATE, "date": "2026-06-12"})
    report = assembled_report_for_state(state, date="2026-06-12")
    _write_report(rag_settings, "2026-06-12", report)

    client = FakeUploadClient()
    manifest = index_report_rag("2026-06-12", settings=rag_settings, client=client)

    assert manifest.date == "2026-06-12"
    assert manifest.vector_store_id == "vs_test"
    assert len(manifest.sections) == len(INVESTOR_REPORT_SECTIONS)
    assert len(client.uploads) == len(INVESTOR_REPORT_SECTIONS)

    manifest_path = rag_settings.rag_dir / "2026-06-12.json"
    assert manifest_path.is_file()
    saved = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert saved["date"] == "2026-06-12"
    assert len(saved["sections"]) == len(INVESTOR_REPORT_SECTIONS)

    _, first_content = client.uploads[0]
    assert "report_date: 2026-06-12" in first_content
    assert "section:" in first_content


def test_index_report_rag_missing_report_raises(rag_settings):
    with pytest.raises(RagIndexError, match="report not found"):
        index_report_rag("2026-06-12", settings=rag_settings, client=FakeUploadClient())


def test_index_report_rag_missing_section_raises(rag_settings):
    _write_report(rag_settings, "2026-06-12", "## Today's Posture\n\nOnly one section.\n")
    with pytest.raises(RagIndexError, match="missing section"):
        index_report_rag("2026-06-12", settings=rag_settings, client=FakeUploadClient())


def test_backfill_rag_index_indexes_all_reports(rag_settings):
    for date in ("2026-06-10", "2026-06-12"):
        state = DailyState.model_validate({**SAMPLE_STATE, "date": date})
        _write_report(rag_settings, date, assembled_report_for_state(state, date=date))

    client = FakeUploadClient()
    manifests = backfill_rag_index(settings=rag_settings, client=client)

    assert [m.date for m in manifests] == ["2026-06-10", "2026-06-12"]
    assert len(client.uploads) == len(INVESTOR_REPORT_SECTIONS) * 2


def test_upload_failure_wrapped_as_rag_index_error(rag_settings):
    class FailingClient:
        def upload_section(self, *, filename: str, content: str) -> str:
            raise RuntimeError("connection reset")

    state = DailyState.model_validate({**SAMPLE_STATE, "date": "2026-06-12"})
    _write_report(
        rag_settings,
        "2026-06-12",
        assembled_report_for_state(state, date="2026-06-12"),
    )

    with pytest.raises(RagIndexError, match="upload failed for section"):
        index_report_rag("2026-06-12", settings=rag_settings, client=FailingClient())


def test_index_rag_or_fail_emits_retry_hint(rag_settings, capsys):
    class FailingClient:
        def upload_section(self, *, filename: str, content: str) -> str:
            raise RuntimeError("connection reset")

    state = DailyState.model_validate({**SAMPLE_STATE, "date": "2026-06-12"})
    _write_report(
        rag_settings,
        "2026-06-12",
        assembled_report_for_state(state, date="2026-06-12"),
    )

    from src.rag_index import index_rag_or_fail

    with pytest.raises(RagIndexError):
        index_rag_or_fail("2026-06-12", settings=rag_settings, client=FailingClient())

    err = capsys.readouterr().err
    assert "Retry: python -m src.cli index-rag --date 2026-06-12" in err
