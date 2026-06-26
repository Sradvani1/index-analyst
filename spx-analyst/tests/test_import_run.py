"""Tests for import-run: intake screenshots → production run directory."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image

from src.chart_pack import CHART_PACK, CANONICAL_CHART_FILES, CHART_PACK_SIZE, build_manifest
from src.files import ANALYSIS_CONTEXT_FILENAME, InputError, read_json, write_json
from src.import_run import import_run
from src.market_data import MARKET_HISTORY_FILENAME, MarketSeries
from src.structure import PriceBar
from tests.conftest import make_settings

RUN_DATE = "2026-06-24"
MOCK_CLOSE = 7365.46


def _mock_series(run_date: str = RUN_DATE, close: float = MOCK_CLOSE) -> MarketSeries:
    import pandas as pd
    from datetime import date

    d = date.fromisoformat(run_date)
    return MarketSeries(
        bars=[
            PriceBar(
                session_date=d,
                open=close - 10,
                high=close + 5,
                low=close - 15,
                close=close,
            )
        ],
        vix=pd.Series([18.0], index=[d]),
        tnx=pd.Series([4.2], index=[d]),
        as_of_date=d,
    )


def _write_intake_images(images_dir: Path, count: int = CHART_PACK_SIZE, *, prefix: str = "IMG") -> None:
    images_dir.mkdir(parents=True, exist_ok=True)
    for i in range(count):
        path = images_dir / f"{prefix}_{1200 + i:04d}.png"
        Image.new("RGB", (16, 16), color=(i * 10, 0, 0)).save(path)


def _settings(tmp_path: Path):
    return make_settings(tmp_path)


@patch("src.import_run.fetch_market_series")
def test_import_run_happy_path(mock_fetch, tmp_path: Path):
    mock_fetch.return_value = _mock_series()
    settings = _settings(tmp_path)
    images_dir = tmp_path / "Images" / RUN_DATE
    _write_intake_images(images_dir)

    result = import_run(RUN_DATE, images_dir=images_dir, settings=settings)

    assert result.manifest.chart_count == CHART_PACK_SIZE
    assert result.close == MOCK_CLOSE
    charts_dir = result.run_dir / "charts"
    for name in CANONICAL_CHART_FILES:
        assert (charts_dir / name).is_file()
    assert not (charts_dir / "00_placeholder.png").exists()
    assert (result.run_dir / "market_history.json").is_file()


@patch("src.import_run.fetch_market_series")
def test_import_run_wrong_count(mock_fetch, tmp_path: Path):
    mock_fetch.return_value = _mock_series()
    settings = _settings(tmp_path)
    images_dir = tmp_path / "Images" / RUN_DATE
    _write_intake_images(images_dir, count=14)

    with pytest.raises(InputError, match="expected 15 PNG"):
        import_run(RUN_DATE, images_dir=images_dir, settings=settings)


@patch("src.import_run.fetch_market_series")
def test_import_run_rejects_non_png(mock_fetch, tmp_path: Path):
    mock_fetch.return_value = _mock_series()
    settings = _settings(tmp_path)
    images_dir = tmp_path / "Images" / RUN_DATE
    _write_intake_images(images_dir)
    (images_dir / "extra.jpg").write_bytes(b"not a png")

    with pytest.raises(InputError, match="non-PNG"):
        import_run(RUN_DATE, images_dir=images_dir, settings=settings)


@patch("src.import_run.fetch_market_series")
def test_import_run_requires_force_to_overwrite(mock_fetch, tmp_path: Path):
    mock_fetch.return_value = _mock_series()
    settings = _settings(tmp_path)
    images_dir = tmp_path / "Images" / RUN_DATE
    _write_intake_images(images_dir)

    import_run(RUN_DATE, images_dir=images_dir, settings=settings)

    with pytest.raises(InputError, match="already imported"):
        import_run(RUN_DATE, images_dir=images_dir, settings=settings)

    result = import_run(RUN_DATE, images_dir=images_dir, settings=settings, force=True)
    assert result.manifest.chart_count == CHART_PACK_SIZE


@patch("src.import_run.fetch_market_series")
def test_import_run_fetch_failure_leaves_no_canonical_charts(mock_fetch, tmp_path: Path):
    mock_fetch.side_effect = ValueError("no network")
    settings = _settings(tmp_path)
    images_dir = tmp_path / "Images" / RUN_DATE
    _write_intake_images(images_dir)

    with pytest.raises(InputError, match="market data fetch failed"):
        import_run(RUN_DATE, images_dir=images_dir, settings=settings)

    assert not (settings.runs_dir / RUN_DATE / "charts" / "01_spx_intraday.png").exists()


@patch("src.import_run.fetch_market_series")
def test_import_run_fetch_failure_with_close_deletes_stale_cache(mock_fetch, tmp_path: Path):
    mock_fetch.side_effect = ValueError("no network")
    settings = _settings(tmp_path)
    images_dir = tmp_path / "Images" / RUN_DATE
    _write_intake_images(images_dir)
    run_dir = settings.runs_dir / RUN_DATE
    run_dir.mkdir(parents=True)
    stale = run_dir / MARKET_HISTORY_FILENAME
    stale.write_text("{}", encoding="utf-8")

    result = import_run(
        RUN_DATE, images_dir=images_dir, settings=settings, close_override=7500.0
    )

    assert result.close == 7500.0
    assert not stale.exists()
    assert any("market_history.json not written" in w for w in result.warnings)


@patch("src.import_run.fetch_market_series")
def test_import_run_ignores_dotfiles(mock_fetch, tmp_path: Path):
    mock_fetch.return_value = _mock_series()
    settings = _settings(tmp_path)
    images_dir = tmp_path / "Images" / RUN_DATE
    _write_intake_images(images_dir)
    (images_dir / ".DS_Store").write_bytes(b"macos junk")

    result = import_run(RUN_DATE, images_dir=images_dir, settings=settings)
    assert result.manifest.chart_count == CHART_PACK_SIZE


@patch("src.import_run.fetch_market_series")
def test_import_run_incomplete_import_requires_force(mock_fetch, tmp_path: Path):
    mock_fetch.return_value = _mock_series()
    settings = _settings(tmp_path)
    images_dir = tmp_path / "Images" / RUN_DATE
    _write_intake_images(images_dir)

    run_dir = settings.runs_dir / RUN_DATE
    charts = run_dir / "charts"
    charts.mkdir(parents=True)
    Image.new("RGB", (8, 8), color=(1, 1, 1)).save(charts / "01_spx_intraday.png")
    write_json(
        run_dir / "manifest.json",
        {
            "date": RUN_DATE,
            "index_symbol": "SPX",
            "close": 0.0,
            "chart_count": 1,
            "charts": [
                {
                    "order": 1,
                    "file": "01_spx_intraday.png",
                    "label": "partial",
                    "category": "technical",
                }
            ],
        },
    )

    with pytest.raises(InputError, match="incomplete import"):
        import_run(RUN_DATE, images_dir=images_dir, settings=settings)


@patch("src.import_run.fetch_market_series")
def test_import_run_force_purges_analysis_context(mock_fetch, tmp_path: Path):
    mock_fetch.return_value = _mock_series()
    settings = _settings(tmp_path)
    images_dir = tmp_path / "Images" / RUN_DATE
    _write_intake_images(images_dir)

    import_run(RUN_DATE, images_dir=images_dir, settings=settings)
    stale = settings.runs_dir / RUN_DATE / ANALYSIS_CONTEXT_FILENAME
    stale.write_text("{}", encoding="utf-8")

    import_run(RUN_DATE, images_dir=images_dir, settings=settings, force=True)
    assert not stale.exists()


@patch("src.import_run.fetch_market_series")
def test_import_run_close_override(mock_fetch, tmp_path: Path):
    mock_fetch.return_value = _mock_series(close=7000.0)
    settings = _settings(tmp_path)
    images_dir = tmp_path / "Images" / RUN_DATE
    _write_intake_images(images_dir)

    result = import_run(
        RUN_DATE, images_dir=images_dir, settings=settings, close_override=7500.0
    )
    assert result.close == 7500.0
    manifest = read_json(settings.runs_dir / RUN_DATE / "manifest.json")
    assert manifest["close"] == 7500.0


def test_build_manifest_matches_reference_template():
    reference_path = (
        Path(__file__).resolve().parent.parent / "data" / "runs" / "2026-06-23" / "manifest.json"
    )
    if not reference_path.is_file():
        pytest.skip("reference manifest not available")
    reference = json.loads(reference_path.read_text(encoding="utf-8"))

    built = build_manifest("2026-06-23", reference["close"])
    assert built["charts"] == reference["charts"]
    assert built["chart_count"] == reference["chart_count"]
    assert len(CHART_PACK) == CHART_PACK_SIZE
