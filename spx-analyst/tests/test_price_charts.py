"""Tests for SPX price chart generation (01–07)."""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
from PIL import Image

from src.price_charts import (
    W,
    H,
    _bbands,
    _mfi,
    _rsi,
    _sma,
    fetch_and_generate,
    generate_intraday_chart,
    generate_hourly_five_day,
    PriceData,
)


def _fake_daily_df(n_days: int = 2000, start_price: float = 5000) -> pd.DataFrame:
    dr = pd.date_range(end=date.today(), periods=n_days, freq="B")
    rng = np.random.default_rng(42)
    closes = start_price * (1 + rng.normal(0, 0.005, n_days)).cumprod()
    opens = closes * (1 + rng.normal(0, 0.002, n_days))
    highs = np.maximum(opens, closes) * (1 + np.abs(rng.normal(0, 0.003, n_days)))
    lows = np.minimum(opens, closes) * (1 - np.abs(rng.normal(0, 0.003, n_days)))
    volumes = rng.integers(50_000_000, 80_000_000, n_days)
    return pd.DataFrame(
        {"Open": opens, "High": highs, "Low": lows, "Close": closes, "Volume": volumes},
        index=dr,
    )


def _fake_weekly_df(daily: pd.DataFrame) -> pd.DataFrame:
    weekly = daily.resample("W-FRI", label="right", closed="right").agg({
        "Open": "first", "High": "max", "Low": "min",
        "Close": "last", "Volume": "sum",
    })
    return weekly.dropna()


def _fake_hourly_df() -> pd.DataFrame:
    today = date.today()
    dr = pd.date_range(end=today, periods=120, freq="h", normalize=False)
    closes = 5000 + np.random.default_rng(50).normal(0, 5, 120).cumsum()
    opens = closes - np.random.default_rng(51).normal(0, 2, 120)
    highs = closes + np.abs(np.random.default_rng(52).normal(0, 3, 120))
    lows = closes - np.abs(np.random.default_rng(53).normal(0, 3, 120))
    volumes = np.random.default_rng(54).integers(1_000_000, 5_000_000, 120)
    return pd.DataFrame(
        {"Open": opens, "High": highs, "Low": lows, "Close": closes, "Volume": volumes},
        index=dr,
    )


def _fake_intraday_df() -> pd.DataFrame:
    today = date.today()
    market_open = pd.Timestamp(today).replace(hour=9, minute=30)
    n_bars = 78  # 6.5 hours * 12 bars/hour for 5-min (fewer than 390 1-min)
    dr = pd.date_range(end=market_open + timedelta(minutes=n_bars * 5 - 5), periods=n_bars, freq="5min")
    closes = 5000 + np.random.default_rng(5).normal(0, 10, n_bars).cumsum()
    opens = closes - np.random.default_rng(6).normal(0, 2, n_bars)
    highs = closes + np.abs(np.random.default_rng(7).normal(0, 3, n_bars))
    lows = closes - np.abs(np.random.default_rng(8).normal(0, 3, n_bars))
    volumes = np.random.default_rng(9).integers(1_000, 5_000, n_bars)
    return pd.DataFrame(
        {"Open": opens, "High": highs, "Low": lows, "Close": closes, "Volume": volumes},
        index=dr,
    )


@pytest.fixture
def fake_price_data() -> PriceData:
    daily = _fake_daily_df()
    weekly = _fake_weekly_df(daily)

    def _c(col: str) -> np.ndarray:
        return daily[col].to_numpy(dtype=float)

    def _wc(col: str) -> np.ndarray:
        return weekly[col].to_numpy(dtype=float)

    return PriceData(
        run_date=date.today(),
        close=float(_c("Close")[-1]),
        dates=[d.date() for d in daily.index],
        opens=_c("Open"),
        highs=_c("High"),
        lows=_c("Low"),
        closes=_c("Close"),
        volumes=_c("Volume"),
        weekly_dates=[d.date() for d in weekly.index],
        weekly_opens=_wc("Open"),
        weekly_highs=_wc("High"),
        weekly_lows=_wc("Low"),
        weekly_closes=_wc("Close"),
        weekly_volumes=_wc("Volume"),
        intraday=_fake_intraday_df(),
        hourly=_fake_hourly_df(),
    )


# --- Indicator tests ----------------------------------------------------------


class TestIndicators:
    def test_sma_window(self):
        x = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        result = _sma(x, 3)
        assert np.isnan(result[0])
        assert np.isnan(result[1])
        assert result[2] == pytest.approx(2.0)
        assert result[3] == pytest.approx(3.0)
        assert result[4] == pytest.approx(4.0)

    def test_sma_insufficient_data(self):
        x = np.array([1.0, 2.0])
        result = _sma(x, 3)
        assert all(np.isnan(result))

    def test_rsi_all_up(self):
        x = np.array([10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24], dtype=float)
        result = _rsi(x, 14)
        assert result[-1] == pytest.approx(100.0, abs=1e-6)

    def test_rsi_all_down(self):
        x = np.array([24, 23, 22, 21, 20, 19, 18, 17, 16, 15, 14, 13, 12, 11, 10], dtype=float)
        result = _rsi(x, 14)
        assert result[-1] == pytest.approx(0.0, abs=1e-6)

    def test_rsi_bounds(self, fake_price_data):
        rsi = _rsi(fake_price_data.closes, 14)
        assert np.nanmax(rsi) <= 100.0
        assert np.nanmin(rsi) >= 0.0

    def test_mfi_bounds(self, fake_price_data):
        mfi = _mfi(fake_price_data.highs, fake_price_data.lows, fake_price_data.closes,
                   fake_price_data.volumes, 14)
        assert np.nanmax(mfi) <= 100.0
        assert np.nanmin(mfi) >= 0.0

    def test_bbands_middle_is_sma(self, fake_price_data):
        bb_u, bb_m, bb_l = _bbands(fake_price_data.closes, 20, 2.0)
        sma20 = _sma(fake_price_data.closes, 20)
        last_valid = ~np.isnan(bb_m)
        assert np.allclose(bb_m[last_valid], sma20[last_valid])

    def test_bbands_upper_above_lower(self, fake_price_data):
        bb_u, bb_m, bb_l = _bbands(fake_price_data.closes, 20, 2.0)
        valid = ~np.isnan(bb_u)
        assert np.all(bb_u[valid] >= bb_m[valid])
        assert np.all(bb_m[valid] >= bb_l[valid])


# --- Chart generation tests ---------------------------------------------------


class TestChartGeneration:
    def test_intraday_chart_generates_png(self, fake_price_data, tmp_path):
        p = tmp_path / "01_spx_intraday.png"
        generate_intraday_chart(fake_price_data, p)
        assert p.is_file()
        img = Image.open(p)
        assert img.size == (W, H), f"got {img.size}"

    def test_intraday_skips_when_no_data(self, tmp_path):
        empty = PriceData(
            run_date=date.today(),
            close=5000.0,
            dates=[date.today()],
            opens=np.array([5000.0]),
            highs=np.array([5010.0]),
            lows=np.array([4990.0]),
            closes=np.array([5000.0]),
            volumes=np.array([60_000_000]),
            weekly_dates=[date.today()],
            weekly_opens=np.array([5000.0]),
            weekly_highs=np.array([5010.0]),
            weekly_lows=np.array([4990.0]),
            weekly_closes=np.array([5000.0]),
            weekly_volumes=np.array([60_000_000]),
            intraday=None,
            hourly=None,
        )
        p = tmp_path / "01_spx_intraday.png"
        generate_intraday_chart(empty, p)
        assert not p.is_file()

    def test_hourly_five_day_generates_png(self, fake_price_data, tmp_path):
        p = tmp_path / "02_spx_5day.png"
        generate_hourly_five_day(fake_price_data, p)
        assert p.is_file()
        img = Image.open(p)
        assert img.size == (W, H), f"got {img.size}"

    def test_hourly_five_day_skips_when_no_data(self, tmp_path):
        empty = PriceData(
            run_date=date.today(),
            close=5000.0,
            dates=[date.today()],
            opens=np.array([5000.0]),
            highs=np.array([5010.0]),
            lows=np.array([4990.0]),
            closes=np.array([5000.0]),
            volumes=np.array([60_000_000]),
            weekly_dates=[date.today()],
            weekly_opens=np.array([5000.0]),
            weekly_highs=np.array([5010.0]),
            weekly_lows=np.array([4990.0]),
            weekly_closes=np.array([5000.0]),
            weekly_volumes=np.array([60_000_000]),
            intraday=None,
            hourly=None,
        )
        p = tmp_path / "02_spx_5day.png"
        generate_hourly_five_day(empty, p)
        assert not p.is_file()


# --- Integration test ---------------------------------------------------------


@patch("src.price_charts.yf.download")
def test_fetch_and_generate_all(mock_download, tmp_path):
    daily_df = _fake_daily_df()
    intraday_df = _fake_intraday_df()
    hourly_df = _fake_hourly_df()

    call_count = [0]

    def _side_effect(*args, **kwargs):
        call_count[0] += 1
        interval = kwargs.get("interval")
        if interval == "1m":
            return intraday_df
        if interval == "1h":
            return hourly_df
        return daily_df

    mock_download.side_effect = _side_effect
    run_date = date.today()
    paths = fetch_and_generate(tmp_path, run_date)
    expected = [
        "01_spx_intraday.png",
        "02_spx_5day.png",
        "03_spx_1month.png",
        "04_spx_3month.png",
        "05_spx_6month.png",
        "06_spx_1year.png",
        "07_spx_3year.png",
    ]
    for name in expected:
        assert name in paths, f"{name} missing"
        p = paths[name]
        assert p.is_file(), f"{name} not on disk"
        img = Image.open(p)
        assert img.size == (W, H), f"{name}: got {img.size}"
