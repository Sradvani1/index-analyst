"""Tests for market_data context warnings and OHLC sanitization."""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

import pandas as pd
import pytest

from src.market_data import (
    MarketSeries,
    _backfill_close_series_to_target,
    _sanitize_ohlc_df,
    build_market_data_context,
    series_has_valid_bars,
)
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


def test_sanitize_repairs_nan_close_via_session_fetch():
    idx = pd.to_datetime(["2026-06-25", "2026-06-26"])
    df = pd.DataFrame(
        {
            "Open": [7400.0, float("nan")],
            "High": [7410.0, float("nan")],
            "Low": [7300.0, float("nan")],
            "Close": [7357.49, float("nan")],
        },
        index=idx,
    )
    repaired = {
        "Open": 7312.74,
        "High": 7392.95,
        "Low": 7294.18,
        "Close": 7354.02,
    }

    with patch("src.market_data._fetch_session_ohlc", return_value=repaired):
        out = _sanitize_ohlc_df(
            df,
            "^GSPC",
            required_sessions=frozenset({date(2026, 6, 26)}),
        )

    assert float(out.loc[idx[1], "Close"]) == 7354.02


def test_sanitize_raises_when_required_session_unreparable():
    idx = pd.to_datetime(["2026-06-26"])
    df = pd.DataFrame(
        {
            "Open": [float("nan")],
            "High": [float("nan")],
            "Low": [float("nan")],
            "Close": [float("nan")],
        },
        index=idx,
    )

    with patch("src.market_data._fetch_session_ohlc", return_value=None):
        with pytest.raises(ValueError, match="required session"):
            _sanitize_ohlc_df(
                df,
                "^GSPC",
                required_sessions=frozenset({date(2026, 6, 26)}),
            )


def test_backfill_close_series_adds_missing_run_date():
    closes = pd.Series(
        {date(2026, 6, 24): 18.6, date(2026, 6, 25): 18.9},
    )
    with patch("src.market_data._fetch_session_ohlc", return_value={"Close": 18.41}) as mock:
        out = _backfill_close_series_to_target(closes, "^VIX", date(2026, 6, 26))
    mock.assert_called()
    assert date(2026, 6, 26) in out.index
    assert float(out[date(2026, 6, 26)]) == 18.41


def test_cache_covers_run_date_requires_vix_tnx_through_target():
    from src.market_data import _cache_covers_run_date

    target = date(2026, 6, 26)
    incomplete = MarketSeries(
        bars=[
            PriceBar(session_date=target, open=7300, high=7400, low=7200, close=7354.0)
        ],
        vix=pd.Series([18.9], index=[date(2026, 6, 25)]),
        tnx=pd.Series([4.45], index=[date(2026, 6, 18)]),
        as_of_date=target,
    )
    assert not _cache_covers_run_date(incomplete, "2026-06-26")

    complete = MarketSeries(
        bars=incomplete.bars,
        vix=pd.Series([18.41], index=[target]),
        tnx=pd.Series([4.372], index=[target]),
        as_of_date=target,
    )
    assert _cache_covers_run_date(complete, "2026-06-26")


def test_series_has_valid_bars_rejects_nan():
    bad = MarketSeries(
        bars=[
            PriceBar(
                session_date=date(2026, 6, 26),
                open=float("nan"),
                high=1.0,
                low=1.0,
                close=float("nan"),
            )
        ],
        vix=pd.Series([18.0], index=[date(2026, 6, 26)]),
        tnx=pd.Series([4.0], index=[date(2026, 6, 26)]),
        as_of_date=date(2026, 6, 26),
    )
    assert not series_has_valid_bars(bad)
