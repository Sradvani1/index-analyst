"""Tests for section-vector RAG indexing."""

from __future__ import annotations

import json

import pytest

from src.prompts import INVESTOR_REPORT_SECTIONS
from src.rag_index import (
    RagIndexError,
    backfill_rag_index,
    index_report_rag,
    prune_retention,
    split_report_sections,
    sweep_store_orphans,
)
from src.schemas import ArcBriefCaps, DailyState

from tests.conftest import SAMPLE_STATE, make_settings
from tests.fixtures.investor_report import assembled_report_for_state


class FakeUploadClient:
    def __init__(self) -> None:
        self.uploads: list[tuple[str, str]] = []
        self.deleted: list[str] = []
        self._counter = 0
        self._live: set[str] = set()

    def upload_section(self, *, filename: str, content: str) -> str:
        self.uploads.append((filename, content))
        file_id = f"file_fake_{self._counter}"
        self._counter += 1
        self._live.add(file_id)
        return file_id

    def delete_file(self, file_id: str) -> None:
        self.deleted.append(file_id)
        self._live.discard(file_id)

    def list_vector_store_files(self) -> list[str]:
        return sorted(self._live)


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


def _write_manifest(settings, date: str, n_sections: int = 2) -> None:
    sections = [
        {"section": f"Section {i}", "openai_file_id": f"file_{date}_{i}"}
        for i in range(n_sections)
    ]
    manifest = {
        "date": date,
        "vector_store_id": "vs_test",
        "sections": sections,
        "indexed_at": f"{date}T00:00:00+00:00",
    }
    path = settings.rag_dir / f"{date}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest), encoding="utf-8")


def _manifest_dates(settings) -> list[str]:
    return sorted(p.name[: -len(".json")] for p in settings.rag_dir.glob("*.json"))


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


def test_reindex_deletes_prior_generation(rag_settings):
    state = DailyState.model_validate({**SAMPLE_STATE, "date": "2026-06-12"})
    report = assembled_report_for_state(state, date="2026-06-12")
    _write_report(rag_settings, "2026-06-12", report)

    client = FakeUploadClient()
    first = index_report_rag("2026-06-12", settings=rag_settings, client=client)
    prior_ids = [e.openai_file_id for e in first.sections]
    assert client.deleted == []

    second = index_report_rag("2026-06-12", settings=rag_settings, client=client)

    assert second.date == "2026-06-12"
    assert sorted(client.deleted) == sorted(prior_ids)
    assert len(client.uploads) == len(INVESTOR_REPORT_SECTIONS) * 2


def test_upload_failure_wrapped_as_rag_index_error(rag_settings):
    class FailingClient:
        def upload_section(self, *, filename: str, content: str) -> str:
            raise RuntimeError("connection reset")

        def delete_file(self, file_id: str) -> None:
            raise RuntimeError("unused")

        def list_vector_store_files(self) -> list[str]:
            raise RuntimeError("unused")

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

        def delete_file(self, file_id: str) -> None:
            raise RuntimeError("unused")

        def list_vector_store_files(self) -> list[str]:
            raise RuntimeError("unused")

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


def test_prune_retention_keeps_newest_dates(rag_settings):
    for i in range(1, 13):
        _write_manifest(rag_settings, f"2026-06-{i:02d}")

    client = FakeUploadClient()
    pruned = prune_retention(settings=rag_settings, client=client, keep=10)

    assert sorted(pruned) == ["2026-06-01", "2026-06-02"]
    assert len(_manifest_dates(rag_settings)) == 10
    assert sorted(client.deleted) == [
        "file_2026-06-01_0",
        "file_2026-06-01_1",
        "file_2026-06-02_0",
        "file_2026-06-02_1",
    ]


def test_prune_retention_defaults_to_arc_sessions(rag_settings, monkeypatch):
    for i in range(1, 6):
        _write_manifest(rag_settings, f"2026-06-{i:02d}")

    monkeypatch.setattr(ArcBriefCaps, "MAX_SESSIONS", 3)
    client = FakeUploadClient()
    pruned = prune_retention(settings=rag_settings, client=client)

    assert len(pruned) == 2
    assert len(_manifest_dates(rag_settings)) == 3


def test_prune_retention_keep_zero_raises(rag_settings):
    with pytest.raises(ValueError, match="keep"):
        prune_retention(settings=rag_settings, client=FakeUploadClient(), keep=0)


def test_index_report_rag_trims_to_retention(rag_settings):
    state = DailyState.model_validate({**SAMPLE_STATE, "date": "2026-06-12"})
    _write_report(rag_settings, "2026-06-12", assembled_report_for_state(state, date="2026-06-12"))
    for i in range(1, 11):
        _write_manifest(rag_settings, f"2026-06-{i:02d}")

    client = FakeUploadClient()
    index_report_rag("2026-06-12", settings=rag_settings, client=client)

    dates = _manifest_dates(rag_settings)
    assert len(dates) == 10
    assert "2026-06-12" in dates
    assert "2026-06-01" not in dates
    assert "file_2026-06-01_0" in client.deleted
    assert "file_2026-06-01_1" in client.deleted


def test_sweep_store_orphans_deletes_unmanifested(rag_settings):
    _write_manifest(rag_settings, "2026-06-12")

    client = FakeUploadClient()
    client.upload_section(filename="stray.md", content="stray")

    swept = sweep_store_orphans(settings=rag_settings, client=client)

    assert swept == ["file_fake_0"]
    assert client.deleted == ["file_fake_0"]
    assert client.list_vector_store_files() == []


def test_sweep_store_orphans_keeps_manifested_files(rag_settings):
    _write_manifest(rag_settings, "2026-06-12")
    client = FakeUploadClient()
    client._live.add("file_2026-06-12_0")

    swept = sweep_store_orphans(settings=rag_settings, client=client)

    assert swept == []
    assert client.deleted == []


def test_index_report_rag_reconciles_store_to_manifests(rag_settings):
    state = DailyState.model_validate({**SAMPLE_STATE, "date": "2026-06-12"})
    _write_report(rag_settings, "2026-06-12", assembled_report_for_state(state, date="2026-06-12"))
    _write_manifest(rag_settings, "2026-06-11")

    client = FakeUploadClient()
    client.upload_section(filename="stray.md", content="stray")

    index_report_rag("2026-06-12", settings=rag_settings, client=client)

    keep_ids = {
        entry["openai_file_id"]
        for path in rag_settings.rag_dir.glob("*.json")
        for entry in json.loads(path.read_text(encoding="utf-8"))["sections"]
    }
    assert "file_fake_0" in client.deleted
    assert set(client.list_vector_store_files()) <= keep_ids
