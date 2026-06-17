"""Tests for DL-3 structure detection."""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np

from src.structure import PriceBar, compute_structure


def _bars_from_closes(closes: list[float], start: date | None = None) -> list[PriceBar]:
    start = start or date(2025, 1, 2)
    bars: list[PriceBar] = []
    for i, c in enumerate(closes):
        d = start + timedelta(days=i)
        bars.append(PriceBar(session_date=d, open=c, high=c + 5, low=c - 5, close=c))
    return bars


def test_leg_uptrend_fib382_downside():
    # Trough then rally to peak with 3% pullback confirmation
    n = 120
    closes = [4000.0] * 20
    for i in range(20, 60):
        closes.append(4000 + (i - 20) * 20)
    peak = closes[-1]
    closes.extend([peak - 10, peak - peak * 0.04, peak - peak * 0.02])
    closes.extend([peak - peak * 0.02] * (n - len(closes)))
    bars = _bars_from_closes(closes[:n])
    sma50 = np.full(len(bars), np.nan)
    for i in range(49, len(bars)):
        sma50[i] = float(np.mean([b.close for b in bars[i - 49 : i + 1]]))
    result = compute_structure(bars, sma50=sma50, pct_above_200dma=5.0)
    assert result.downside_target_rule in ("fib_382", "fib_500", "first_liquidation_zone")
    assert result.active_swing_high_price > result.active_swing_low_price
    assert result.fib_382 < result.active_swing_high_price


def test_leg_extended_uses_resistance_above_close():
    n = 100
    closes = list(np.linspace(5000, 6000, 80)) + [6100, 6200, 6300, 6400, 6500]
    closes += [6450] * (n - len(closes))
    bars = _bars_from_closes(closes[:n])
    sma50 = np.full(len(bars), np.nan)
    for i in range(49, len(bars)):
        sma50[i] = float(np.mean([b.close for b in bars[i - 49 : i + 1]]))
    result = compute_structure(bars, sma50=sma50, pct_above_200dma=8.0)
    if bars[-1].close >= result.active_swing_high_price:
        assert result.upside_target_rule in ("next_local_max", "pct_extension")
        assert result.upside_target > bars[-1].close


def test_shallow_pullback_near_fib():
    n = 150
    low, high = 5000.0, 6000.0
    closes = list(np.linspace(low, high, 100))
    fib_382 = high - 0.382 * (high - low)
    closes += list(np.linspace(high, fib_382 * 0.998, 30))
    closes += [fib_382 * 0.998] * (n - len(closes))
    bars = _bars_from_closes(closes[:n])
    sma50 = np.full(len(bars), np.nan)
    for i in range(49, len(bars)):
        sma50[i] = float(np.mean([b.close for b in bars[i - 49 : i + 1]]))
    result = compute_structure(bars, sma50=sma50, pct_above_200dma=3.0)
    assert result.fib_382 > 0
    assert result.downside_target_rule == "fib_500"
    assert result.downside_target == result.fib_500
