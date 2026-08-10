"""Tests for the StreetStats EPS source adapter and sync behavior."""

from __future__ import annotations

import json
from urllib.error import URLError

import pytest

from src import streetstats_eps
from src.eps_sync import sync_eps_for_date
from src.schemas import EpsHistory, EpsHistoryEntry
from src.streetstats_eps import StreetStatsError, StreetStatsFetch, fetch_streetstats_history
from tests.conftest import make_settings, write_eps_history


class _FakeResponse:
    status = 200

    def __init__(self, payload: object):
        self.headers: dict[str, str] = {}
        self._body = payload if isinstance(payload, bytes) else json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self) -> bytes:
        return self._body


def _growth_payload() -> dict[str, object]:
    return {
        "growthHistory": [
            {"Date": "2026-08-07", "ntmE": 384.63, "ltmE": 326.52},
            {"Date": "2026-08-06", "ntmE": 384.01, "ltmE": 325.75},
            {"Date": "2026-08-08", "ntmE": 385.0, "ltmE": 327.0},
        ]
    }


def test_fetch_normalizes_full_history_and_selects_row_for_run_date(monkeypatch, settings):
    calls = []

    def fake_urlopen(request, timeout):
        calls.append((request, timeout))
        if request.full_url.endswith("/api/token"):
            return _FakeResponse({"token": "guest-token"})
        return _FakeResponse(_growth_payload())

    monkeypatch.setattr(streetstats_eps, "urlopen", fake_urlopen)

    result = fetch_streetstats_history("2026-08-07", settings=settings)

    assert [e.effective_from for e in result.history.entries] == [
        "2026-08-06",
        "2026-08-07",
        "2026-08-08",
    ]
    assert result.source_as_of_date == "2026-08-07"
    assert result.forward_eps == 384.63
    assert result.trailing_eps == 326.52
    assert len(result.history_sha256) == 64
    assert len(calls) == 2
    assert calls[1][0].headers["Authorization"] == "Bearer guest-token"


def test_fetch_does_not_retry_after_transport_failure(monkeypatch, settings):
    calls = []

    def fake_urlopen(request, timeout):
        calls.append(request.full_url)
        if request.full_url.endswith("/api/token"):
            return _FakeResponse({"token": "guest-token"})
        raise URLError("network unavailable")

    monkeypatch.setattr(streetstats_eps, "urlopen", fake_urlopen)

    with pytest.raises(StreetStatsError, match="request failed"):
        fetch_streetstats_history("2026-08-07", settings=settings)

    assert calls == [
        "https://streetstats.finance/api/token",
        "https://streetstats.finance/api/valuation/market/growth",
    ]


def test_fetch_invalid_utf8_is_reported_as_source_error(monkeypatch, settings):
    def fake_urlopen(request, timeout):
        if request.full_url.endswith("/api/token"):
            return _FakeResponse({"token": "guest-token"})
        return _FakeResponse(b"\xff")

    monkeypatch.setattr(streetstats_eps, "urlopen", fake_urlopen)

    with pytest.raises(StreetStatsError, match="invalid JSON"):
        fetch_streetstats_history("2026-08-07", settings=settings)


def test_sync_replaces_entire_master_history(tmp_path, settings, monkeypatch):
    path = write_eps_history(
        tmp_path,
        [{"effective_from": "2026-08-06", "forward_eps": 380, "trailing_eps": 321}],
    )
    fetched = StreetStatsFetch(
        history=EpsHistory(
            entries=[
                EpsHistoryEntry(
                    effective_from="2026-08-06", forward_eps=384.01, trailing_eps=325.75
                ),
                EpsHistoryEntry(
                    effective_from="2026-08-07", forward_eps=384.63, trailing_eps=326.52
                ),
            ]
        ),
        source_as_of_date="2026-08-07",
        forward_eps=384.63,
        trailing_eps=326.52,
        retrieved_at="2026-08-09T00:00:00+00:00",
        response_sha256="abc123",
        history_sha256="def456",
    )
    monkeypatch.setattr("src.eps_sync.fetch_streetstats_history", lambda *args, **kwargs: fetched)

    result = sync_eps_for_date("2026-08-07", settings=settings)

    assert result.status == "updated"
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "entries": [
            {"effective_from": "2026-08-06", "forward_eps": 384.01, "trailing_eps": 325.75},
            {"effective_from": "2026-08-07", "forward_eps": 384.63, "trailing_eps": 326.52},
        ]
    }
    artifact = json.loads(
        (settings.runs_dir / "2026-08-07" / "eps_source.json").read_text(encoding="utf-8")
    )
    assert artifact["status"] == "updated"
    assert artifact["source_as_of_date"] == "2026-08-07"
    assert artifact["history_sha256"] == "def456"


def test_sync_rejects_truncated_history_and_keeps_master(tmp_path, settings, monkeypatch):
    path = write_eps_history(
        tmp_path,
        [
            {"effective_from": "2026-08-06", "forward_eps": 384.01, "trailing_eps": 325.75},
            {"effective_from": "2026-08-07", "forward_eps": 384.63, "trailing_eps": 326.52},
        ],
    )
    before = path.read_text(encoding="utf-8")
    fetched = StreetStatsFetch(
        history=EpsHistory(
            entries=[
                EpsHistoryEntry(
                    effective_from="2026-08-07", forward_eps=384.63, trailing_eps=326.52
                )
            ]
        ),
        source_as_of_date="2026-08-07",
        forward_eps=384.63,
        trailing_eps=326.52,
        retrieved_at="2026-08-09T00:00:00+00:00",
        response_sha256="abc123",
        history_sha256="def456",
    )
    monkeypatch.setattr("src.eps_sync.fetch_streetstats_history", lambda *args, **kwargs: fetched)

    result = sync_eps_for_date("2026-08-07", settings=settings)

    assert result.status == "fallback"
    assert result.error is not None
    assert "truncated" in result.error
    assert path.read_text(encoding="utf-8") == before


def test_sync_failure_leaves_existing_history_unchanged(tmp_path, settings, monkeypatch):
    path = write_eps_history(tmp_path)
    before = path.read_text(encoding="utf-8")
    monkeypatch.setattr(
        "src.eps_sync.fetch_streetstats_history",
        lambda *args, **kwargs: (_ for _ in ()).throw(StreetStatsError("unavailable")),
    )

    result = sync_eps_for_date("2026-08-07", settings=settings)

    assert result.status == "fallback"
    assert path.read_text(encoding="utf-8") == before
    assert result.source_as_of_date == "2026-06-01"
