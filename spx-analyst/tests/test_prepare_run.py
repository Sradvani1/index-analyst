"""Tests for prepare-run: generate charts + manifest + precompute."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from src.chart_pack import CANONICAL_CHART_FILES, CHART_PACK_SIZE
from src.files import InputError, read_json
from src.prepare_run import _assert_can_prepare, _purge_stale_artifacts, prepare_run
from tests.conftest import make_settings
from tests.sample_analysis_context import sample_analysis_context

RUN_DATE = "2026-06-24"
MOCK_CLOSE = 7365.46


def _mock_price_charts(output_dir: Path, run_date=None) -> dict[str, Path]:
    """Write 7 stub price PNGs and return paths dict (matches real signature)."""
    from PIL import Image
    paths: dict[str, Path] = {}
    for name in CANONICAL_CHART_FILES[:7]:
        p = output_dir / name
        Image.new("RGB", (16, 16), color=(0, 0, 0)).save(p)
        paths[name] = p
    return paths


def _mock_fear_greed(output_dir: Path) -> dict[str, Path]:
    """Write 8 stub F&G chart PNGs + raw JSON and return paths."""
    from PIL import Image
    paths: dict[str, Path] = {}
    for name in CANONICAL_CHART_FILES[7:]:
        p = output_dir / name
        Image.new("RGB", (16, 16), color=(255, 0, 0)).save(p)
        paths[name] = p
    raw = output_dir / "fear_greed_raw.json"
    raw.write_text('{"test": true}', encoding="utf-8")
    return paths


def _settings(tmp_path: Path):
    settings = make_settings(tmp_path)
    write_eps(tmp_path)
    return settings


def write_eps(tmp_path: Path) -> Path:
    from tests.conftest import write_eps_history
    return write_eps_history(tmp_path)


@pytest.fixture
def settings(tmp_path: Path):
    return _settings(tmp_path)


# --- _assert_can_prepare ---


def test_assert_can_prepare_empty_dir(tmp_path):
    run_dir = tmp_path / "runs" / RUN_DATE
    run_dir.mkdir(parents=True)
    _assert_can_prepare(run_dir, force=False)


def test_assert_can_prepare_charts_exist_no_manifest(tmp_path):
    run_dir = tmp_path / "runs" / RUN_DATE
    charts = run_dir / "charts"
    charts.mkdir(parents=True)
    (charts / "01_spx_intraday.png").write_bytes(b"foo")
    with pytest.raises(InputError, match="already exist|--force"):
        _assert_can_prepare(run_dir, force=False)


def test_assert_can_prepare_complete_requires_force(tmp_path, settings):
    run_dir = settings.runs_dir / RUN_DATE
    charts = run_dir / "charts"
    charts.mkdir(parents=True)
    _mock_price_charts(charts)
    _mock_fear_greed(charts)
    from src.chart_pack import build_manifest
    from src.files import write_json
    write_json(run_dir / "manifest.json", build_manifest(RUN_DATE, 7400.0))
    (run_dir / "analysis_context.json").write_text("{}", encoding="utf-8")

    with pytest.raises(InputError, match="already prepared"):
        _assert_can_prepare(run_dir, force=False)

    _assert_can_prepare(run_dir, force=True)


# --- _purge_stale_artifacts ---


def test_purge_stale_artifacts_removes_all(settings):
    run_dir = settings.runs_dir / RUN_DATE
    charts = run_dir / "charts"
    charts.mkdir(parents=True)
    (charts / "01_spx_intraday.png").write_bytes(b"a")
    (charts / "fear_greed_raw.json").write_bytes(b"e")
    (run_dir / "manifest.json").write_bytes(b"b")
    (run_dir / "analysis_context.json").write_bytes(b"c")
    (run_dir / "market_history.json").write_bytes(b"d")

    _purge_stale_artifacts(run_dir)

    assert not charts.exists()
    assert not (run_dir / "manifest.json").exists()
    assert not (run_dir / "analysis_context.json").exists()
    assert not (run_dir / "market_history.json").exists()


# --- prepare_run ---


@patch("src.prepare_run.generate_price_charts")
@patch("src.prepare_run.generate_fear_greed")
@patch("src.prepare_run.fetch_market_series")
def test_prepare_run_fails_on_market_fetch(
    mock_fetch, mock_fg, mock_price, settings
):
    mock_price.side_effect = _mock_price_charts
    mock_fg.side_effect = _mock_fear_greed
    mock_fetch.side_effect = ValueError("network unreachable")

    with pytest.raises(InputError, match="market data fetch failed"):
        prepare_run(RUN_DATE, force=True, settings=settings)


@patch("src.prepare_run.generate_price_charts")
@patch("src.prepare_run.generate_fear_greed")
@patch("src.prepare_run.fetch_market_series")
@patch("src.prepare_run.run_precompute")
def test_prepare_run_happy_path(
    mock_precompute, mock_fetch, mock_fg, mock_price, settings
):
    mock_price.side_effect = _mock_price_charts
    mock_fg.side_effect = _mock_fear_greed
    mock_fetch.return_value = _mock_market_series()
    mock_precompute.return_value = sample_analysis_context(RUN_DATE)

    result = prepare_run(RUN_DATE, settings=settings)

    assert result.chart_count == CHART_PACK_SIZE
    charts_dir = result.run_dir / "charts"
    for name in CANONICAL_CHART_FILES:
        assert (charts_dir / name).is_file()
    assert (result.run_dir / "manifest.json").is_file()
    assert (result.run_dir / "market_history.json").is_file()
    assert (result.run_dir / "charts" / "fear_greed_raw.json").is_file()
    assert result.close == MOCK_CLOSE
    assert result.analysis_context.market_data.spx_close == 7450.25
    assert result.warnings == []

    manifest = read_json(result.run_dir / "manifest.json")
    assert manifest["chart_count"] == CHART_PACK_SIZE
    assert manifest["close"] == MOCK_CLOSE


@patch("src.prepare_run.generate_price_charts")
@patch("src.prepare_run.generate_fear_greed")
@patch("src.prepare_run.fetch_market_series")
@patch("src.prepare_run.run_precompute")
def test_prepare_run_already_prepared_fails(
    mock_precompute, mock_fetch, mock_fg, mock_price, settings
):
    mock_price.side_effect = _mock_price_charts
    mock_fg.side_effect = _mock_fear_greed
    mock_fetch.return_value = _mock_market_series()
    mock_precompute.return_value = sample_analysis_context(RUN_DATE)

    prepare_run(RUN_DATE, settings=settings)

    with pytest.raises(InputError, match="already prepared"):
        prepare_run(RUN_DATE, settings=settings)


@patch("src.prepare_run.generate_price_charts")
@patch("src.prepare_run.generate_fear_greed")
@patch("src.prepare_run.fetch_market_series")
@patch("src.prepare_run.run_precompute")
def test_prepare_run_force_overwrites(
    mock_precompute, mock_fetch, mock_fg, mock_price, settings
):
    mock_price.side_effect = _mock_price_charts
    mock_fg.side_effect = _mock_fear_greed
    mock_fetch.return_value = _mock_market_series()
    mock_precompute.return_value = sample_analysis_context(RUN_DATE)

    prepare_run(RUN_DATE, settings=settings)
    result = prepare_run(RUN_DATE, force=True, settings=settings)

    assert result.chart_count == CHART_PACK_SIZE
    assert (result.run_dir / "manifest.json").is_file()


@patch("src.prepare_run.fetch_market_series")
@patch("src.prepare_run.run_precompute")
def test_prepare_run_fails_on_bad_date(mock_precompute, mock_fetch, settings):
    bad_date = "not-a-date"
    with pytest.raises(ValueError):
        prepare_run(bad_date, settings=settings)


@patch("src.prepare_run.generate_price_charts")
@patch("src.prepare_run.generate_fear_greed")
@patch("src.prepare_run.fetch_market_series")
def test_prepare_run_fails_without_eps(mock_fetch, mock_fg, mock_price, settings):
    mock_price.side_effect = _mock_price_charts
    mock_fg.side_effect = _mock_fear_greed
    mock_fetch.return_value = _mock_market_series()

    from src.eps_history import load_eps_history
    eps_path = settings.eps_history_path
    if eps_path.is_file():
        eps_path.unlink()

    with pytest.raises(InputError, match="EPS history file not found"):
        prepare_run(RUN_DATE, force=True, settings=settings)


# --- helpers ---


def _mock_market_series():
    from datetime import date
    import pandas as pd
    from src.market_data import MarketSeries
    from src.structure import PriceBar

    d = date.fromisoformat(RUN_DATE)
    return MarketSeries(
        bars=[
            PriceBar(
                session_date=d, open=7350, high=7380, low=7340, close=MOCK_CLOSE
            )
        ],
        vix=pd.Series([18.0], index=[d]),
        tnx=pd.Series([4.2], index=[d]),
        as_of_date=d,
    )