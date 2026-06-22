"""Integration test for Step 0 precompute with mocked market data."""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import patch

import pandas as pd

from src.market_data import MarketSeries
from src.precompute import run_precompute
from src.schemas import ResolvedEps
from src.structure import PriceBar

from tests.conftest import build_run_dir


def _mock_market_series(run_date: str, close: float = 7450.25) -> MarketSeries:
    start = date.fromisoformat(run_date) - timedelta(days=400)
    bars: list[PriceBar] = []
    for i in range(300):
        d = start + timedelta(days=i)
        c = 6000.0 + i * 5.0
        if i == 299:
            c = close
        bars.append(PriceBar(session_date=d, open=c, high=c + 5, low=c - 5, close=c))
    as_of = bars[-1].session_date
    return MarketSeries(
        bars=bars,
        vix=pd.Series([18.4], index=[as_of]),
        tnx=pd.Series([4.5], index=[as_of]),
        as_of_date=as_of,
    )


@patch("src.precompute.load_or_fetch_market_series")
def test_run_precompute_writes_analysis_context(mock_load, tmp_path, settings):
    run_date = "2026-06-12"
    run_dir = build_run_dir(tmp_path, date=run_date, n=2)
    mock_load.return_value = _mock_market_series(run_date)

    from src.files import load_manifest

    manifest = load_manifest(run_dir)
    external = ResolvedEps(forward_eps=354.0, trailing_eps=220.0, effective_from="2026-06-01")

    ctx = run_precompute(run_date, run_dir, manifest, external, settings=settings)

    assert (run_dir / "analysis_context.json").exists()
    assert ctx.market_data.spx_close == 7450.25
    assert ctx.valuation.forward_pe is not None
    assert ctx.monte_carlo.prob_up_first_raw > 0
    assert "65" in ctx.monte_carlo.threshold_evaluation
    mock_load.assert_called_once()


@patch("src.precompute.load_or_fetch_market_series")
def test_run_precompute_warns_on_manifest_close_drift(mock_load, tmp_path, settings):
    run_date = "2026-06-12"
    run_dir = build_run_dir(tmp_path, date=run_date, n=1)
    mock_load.return_value = _mock_market_series(run_date, close=7500.0)

    from src.files import load_manifest, read_json, write_json

    manifest = load_manifest(run_dir)
    raw = read_json(run_dir / "manifest.json")
    raw["close"] = 7000.0
    write_json(run_dir / "manifest.json", raw)
    manifest = load_manifest(run_dir)

    ctx = run_precompute(
        run_date,
        run_dir,
        manifest,
        ResolvedEps(forward_eps=354.0, trailing_eps=220.0, effective_from="2026-06-01"),
        settings=settings,
    )
    assert any("manifest.close" in w for w in ctx.market_data.precompute_warnings)
