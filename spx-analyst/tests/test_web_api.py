"""Tests for the Phase 2 web viewer API."""

from __future__ import annotations

from fastapi.testclient import TestClient

from src.config import Settings
from src.web.app import app
from tests.conftest import SAMPLE_STATE, make_settings, write_state


def _write_report(settings: Settings, date: str, body: str = "# Report\n\nBody.") -> None:
    path = settings.daily_reports_dir / f"{date}-analysis.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def test_health() -> None:
    client = TestClient(app)
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_list_runs_empty(tmp_path, monkeypatch) -> None:
    settings = make_settings(tmp_path)
    monkeypatch.setattr("src.web.service.get_settings", lambda: settings)

    client = TestClient(app)
    response = client.get("/api/runs")
    assert response.status_code == 200
    assert response.json() == []


def test_list_runs_sorted_descending(tmp_path, monkeypatch) -> None:
    settings = make_settings(tmp_path)
    monkeypatch.setattr("src.web.service.get_settings", lambda: settings)

    for date, close in [("2026-06-10", 7200.0), ("2026-06-12", 7431.46), ("2026-06-11", 7300.0)]:
        write_state(settings, date, spx_close=close)
        _write_report(settings, date)

    client = TestClient(app)
    response = client.get("/api/runs")
    assert response.status_code == 200
    data = response.json()
    assert [r["date"] for r in data] == ["2026-06-12", "2026-06-11", "2026-06-10"]
    assert data[0]["spx_close"] == 7431.46
    assert data[0]["recommended_action"] == "hold_and_monitor"


def test_list_runs_excludes_orphan_state(tmp_path, monkeypatch) -> None:
    settings = make_settings(tmp_path)
    monkeypatch.setattr("src.web.service.get_settings", lambda: settings)

    write_state(settings, "2026-06-12")
    write_state(settings, "2026-06-11")
    _write_report(settings, "2026-06-11")

    client = TestClient(app)
    response = client.get("/api/runs")
    assert response.status_code == 200
    assert [r["date"] for r in response.json()] == ["2026-06-11"]


def test_list_runs_skips_corrupt_state(tmp_path, monkeypatch) -> None:
    settings = make_settings(tmp_path)
    monkeypatch.setattr("src.web.service.get_settings", lambda: settings)

    write_state(settings, "2026-06-11")
    _write_report(settings, "2026-06-11")
    corrupt = settings.daily_states_dir / "2026-06-12-state.json"
    corrupt.write_text("{not json", encoding="utf-8")
    _write_report(settings, "2026-06-12")

    client = TestClient(app)
    response = client.get("/api/runs")
    assert response.status_code == 200
    assert [r["date"] for r in response.json()] == ["2026-06-11"]


def test_get_run_success(tmp_path, monkeypatch) -> None:
    settings = make_settings(tmp_path)
    monkeypatch.setattr("src.web.service.get_settings", lambda: settings)

    date = "2026-06-12"
    write_state(settings, date)
    report_body = "# SPX Analysis\n\nHold and monitor."
    _write_report(settings, date, report_body)

    client = TestClient(app)
    response = client.get(f"/api/runs/{date}")
    assert response.status_code == 200
    data = response.json()
    assert data["date"] == date
    assert data["report_markdown"] == report_body
    assert data["daily_state"]["date"] == date
    assert data["daily_state"]["spx_close"] == SAMPLE_STATE["spx_close"]


def test_get_run_not_found(tmp_path, monkeypatch) -> None:
    settings = make_settings(tmp_path)
    monkeypatch.setattr("src.web.service.get_settings", lambda: settings)

    client = TestClient(app)
    response = client.get("/api/runs/2099-01-01")
    assert response.status_code == 404


def test_get_run_missing_report(tmp_path, monkeypatch) -> None:
    settings = make_settings(tmp_path)
    monkeypatch.setattr("src.web.service.get_settings", lambda: settings)

    write_state(settings, "2026-06-12")

    client = TestClient(app)
    response = client.get("/api/runs/2026-06-12")
    assert response.status_code == 404


def test_get_run_rejects_invalid_date(tmp_path, monkeypatch) -> None:
    settings = make_settings(tmp_path)
    monkeypatch.setattr("src.web.service.get_settings", lambda: settings)

    client = TestClient(app)
    response = client.get("/api/runs/not-a-date")
    assert response.status_code == 404


def test_get_run_rejects_path_traversal(tmp_path, monkeypatch) -> None:
    settings = make_settings(tmp_path)
    monkeypatch.setattr("src.web.service.get_settings", lambda: settings)

    client = TestClient(app)
    response = client.get("/api/runs/..%2F..%2Fetc%2Fpasswd")
    assert response.status_code == 404
