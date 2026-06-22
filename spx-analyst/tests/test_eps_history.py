"""Tests for master EPS history resolution."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from src.eps_history import (
    get_eps_for_run,
    load_eps_history,
    require_eps_for_run,
    resolve_eps_for_date,
)
from src.files import InputError
from src.schemas import EpsHistory
from tests.conftest import make_settings, write_eps_history, build_run_dir


def _history(entries: list[dict]) -> EpsHistory:
    return EpsHistory.model_validate({"entries": entries})


def test_resolve_single_entry_on_or_after_effective_from():
    history = _history(
        [{"effective_from": "2026-06-01", "forward_eps": 354.0, "trailing_eps": 220.0}]
    )
    entry = resolve_eps_for_date("2026-06-08", history)
    assert entry is not None
    assert entry.forward_eps == 354.0


def test_resolve_fails_before_first_entry():
    history = _history(
        [{"effective_from": "2026-06-01", "forward_eps": 354.0, "trailing_eps": 220.0}]
    )
    assert resolve_eps_for_date("2026-05-01", history) is None


def test_resolve_picks_older_entry_between_revisions():
    history = _history(
        [
            {"effective_from": "2026-06-01", "forward_eps": 350.0, "trailing_eps": 218.0},
            {"effective_from": "2026-06-15", "forward_eps": 358.0, "trailing_eps": 222.0},
        ]
    )
    entry = resolve_eps_for_date("2026-06-10", history)
    assert entry is not None
    assert entry.forward_eps == 350.0


def test_resolve_picks_latest_entry_after_revision():
    history = _history(
        [
            {"effective_from": "2026-06-01", "forward_eps": 350.0, "trailing_eps": 218.0},
            {"effective_from": "2026-06-15", "forward_eps": 358.0, "trailing_eps": 222.0},
        ]
    )
    entry = resolve_eps_for_date("2026-06-20", history)
    assert entry is not None
    assert entry.forward_eps == 358.0


def test_unsorted_entries_resolve_same_as_sorted():
    unsorted = _history(
        [
            {"effective_from": "2026-06-15", "forward_eps": 358.0, "trailing_eps": 222.0},
            {"effective_from": "2026-06-01", "forward_eps": 350.0, "trailing_eps": 218.0},
        ]
    )
    entry = resolve_eps_for_date("2026-06-10", unsorted)
    assert entry is not None
    assert entry.forward_eps == 350.0


def test_duplicate_effective_from_rejected():
    with pytest.raises(ValueError, match="duplicate effective_from"):
        _history(
            [
                {"effective_from": "2026-06-01", "forward_eps": 350.0, "trailing_eps": 218.0},
                {"effective_from": "2026-06-01", "forward_eps": 358.0, "trailing_eps": 222.0},
            ]
        )


def test_get_eps_for_run_missing_master_file(tmp_path):
    settings = make_settings(tmp_path)
    resolution = get_eps_for_run("2026-06-08", settings=settings)
    assert resolution.eps is None
    assert resolution.source == "missing"


def test_require_eps_for_run_raises_when_unresolved(tmp_path):
    settings = make_settings(tmp_path)
    write_eps_history(tmp_path)
    with pytest.raises(InputError, match="No qualifying EPS entry"):
        require_eps_for_run("2026-05-01", settings=settings)


def test_get_eps_for_run_loads_from_settings_path(tmp_path):
    settings = make_settings(tmp_path)
    write_eps_history(tmp_path)
    resolution = get_eps_for_run("2026-06-08", settings=settings)
    assert resolution.eps is not None
    assert resolution.source == "master"
    assert resolution.effective_from == "2026-06-01"


def test_load_eps_history_reads_file(tmp_path):
    settings = make_settings(tmp_path)
    path = write_eps_history(tmp_path)
    history = load_eps_history(settings)
    assert history is not None
    assert len(history.entries) == 1
    assert path.exists()


def test_setup_run_precompute_fails_without_eps(tmp_path, monkeypatch):
    from src.cli import app

    settings = make_settings(tmp_path)
    monkeypatch.setenv("SPX_EPS_HISTORY_PATH", str(tmp_path / "missing" / "eps_history.json"))
    monkeypatch.setenv("SPX_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("SPX_FRAMEWORK_PATH", settings.framework_path_raw)
    monkeypatch.setenv("SPX_ROLE_PATH", settings.role_path_raw)
    monkeypatch.setenv("SPX_MEMORY_DIR", str(tmp_path / "memory"))
    monkeypatch.setenv("SPX_OUTPUT_DIR", str(tmp_path / "output"))

    from src.config import get_settings

    get_settings.cache_clear()

    runner = CliRunner()
    result = runner.invoke(app, ["setup-run", "--date", "2026-06-08", "--precompute"])
    assert result.exit_code == 1


def test_show_eps_exit_codes(tmp_path, monkeypatch):
    from src.cli import app

    settings = make_settings(tmp_path)
    monkeypatch.setenv("SPX_EPS_HISTORY_PATH", str(tmp_path / "data" / "master" / "eps_history.json"))
    monkeypatch.setenv("SPX_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("SPX_FRAMEWORK_PATH", settings.framework_path_raw)
    monkeypatch.setenv("SPX_ROLE_PATH", settings.role_path_raw)
    monkeypatch.setenv("SPX_MEMORY_DIR", str(tmp_path / "memory"))
    monkeypatch.setenv("SPX_OUTPUT_DIR", str(tmp_path / "output"))

    from src.config import get_settings

    get_settings.cache_clear()
    runner = CliRunner()

    missing = runner.invoke(app, ["show-eps", "--date", "2026-06-08"])
    assert missing.exit_code == 1

    write_eps_history(tmp_path)
    get_settings.cache_clear()
    resolved = runner.invoke(app, ["show-eps", "--date", "2026-06-08"])
    assert resolved.exit_code == 0
    assert "forward=354" in resolved.stdout


def test_show_eps_invalid_history_file(tmp_path, monkeypatch):
    from src.cli import app

    settings = make_settings(tmp_path)
    path = settings.eps_history_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"entries": []}', encoding="utf-8")

    monkeypatch.setenv("SPX_EPS_HISTORY_PATH", str(path))
    monkeypatch.setenv("SPX_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("SPX_FRAMEWORK_PATH", settings.framework_path_raw)
    monkeypatch.setenv("SPX_ROLE_PATH", settings.role_path_raw)
    monkeypatch.setenv("SPX_MEMORY_DIR", str(tmp_path / "memory"))
    monkeypatch.setenv("SPX_OUTPUT_DIR", str(tmp_path / "output"))

    from src.config import get_settings

    get_settings.cache_clear()
    result = CliRunner().invoke(app, ["show-eps", "--date", "2026-06-08"])
    assert result.exit_code == 1
    assert "invalid eps history" in result.stderr.lower() or "invalid eps history" in result.stdout.lower()


def test_get_eps_for_run_invalid_history_returns_missing(tmp_path):
    settings = make_settings(tmp_path)
    path = settings.eps_history_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"entries": []}', encoding="utf-8")

    resolution = get_eps_for_run("2026-06-08", settings=settings)
    assert resolution.eps is None
    assert resolution.source == "missing"
    assert any("invalid EPS history" in w for w in resolution.warnings)


def test_load_eps_history_rejects_duplicate_dates(tmp_path):
    settings = make_settings(tmp_path)
    path = settings.eps_history_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "entries": [
                    {"effective_from": "2026-06-01", "forward_eps": 350, "trailing_eps": 220},
                    {"effective_from": "2026-06-01", "forward_eps": 358, "trailing_eps": 222},
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(InputError, match="invalid EPS history"):
        load_eps_history(settings)


def test_eps_history_rejects_non_positive_values():
    with pytest.raises(ValueError):
        _history([{"effective_from": "2026-06-01", "forward_eps": 0, "trailing_eps": 220}])


def test_run_cli_fails_without_eps(tmp_path, monkeypatch):
    from src.cli import app

    settings = make_settings(tmp_path)
    run_dir = build_run_dir(tmp_path, date="2026-06-08", n=1)
    monkeypatch.setenv("SPX_EPS_HISTORY_PATH", str(tmp_path / "missing" / "eps_history.json"))
    monkeypatch.setenv("SPX_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("SPX_FRAMEWORK_PATH", settings.framework_path_raw)
    monkeypatch.setenv("SPX_ROLE_PATH", settings.role_path_raw)
    monkeypatch.setenv("SPX_MEMORY_DIR", str(tmp_path / "memory"))
    monkeypatch.setenv("SPX_OUTPUT_DIR", str(tmp_path / "output"))

    from src.config import get_settings

    get_settings.cache_clear()
    result = CliRunner().invoke(
        app, ["run", "--date", "2026-06-08", "--input-dir", str(run_dir)]
    )
    assert result.exit_code == 1
    combined = (result.stdout + result.stderr).lower()
    assert "eps history file not found" in combined
