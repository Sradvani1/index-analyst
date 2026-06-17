"""Tests for market_data context warnings."""

from __future__ import annotations

from datetime import date

from src.market_data import MarketSeries, build_market_data_context
from src.schemas import DailyManifest
from src.structure import PriceBar


def _series(as_of: date, close: float) -> MarketSeries:
    bars = [
        PriceBar(session_date=as_of, open=close, high=close + 1, low=close - 1, close=close)
    ]
    import pandas as pd

    return MarketSeries(
        bars=bars,
        vix=pd.Series([18.0], index=[as_of]),
        tnx=pd.Series([4.5], index=[as_of]),
        as_of_date=as_of,
    )


def test_as_of_date_mismatch_warns():
    manifest = DailyManifest.model_validate(
        {
            "date": "2026-06-14",
            "index_symbol": "SPX",
            "close": 5000.0,
            "chart_count": 1,
            "charts": [{"order": 1, "file": "a.png", "label": "x", "category": "technical"}],
        }
    )
    series = _series(date(2026, 6, 12), 5000.0)
    ctx = build_market_data_context(series, manifest)
    assert any("prior trading day" in w for w in ctx.precompute_warnings)
