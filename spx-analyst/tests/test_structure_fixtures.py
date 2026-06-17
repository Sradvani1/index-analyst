"""Tests for frozen DL-3 structure fixtures."""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pytest

from src.structure import PriceBar, compute_structure

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "structure"


def _bars_from_closes(closes: list[float], start: date | None = None) -> list[PriceBar]:
    start = start or date(2025, 1, 2)
    bars: list[PriceBar] = []
    for i, c in enumerate(closes):
        d = start + timedelta(days=i)
        bars.append(PriceBar(session_date=d, open=c, high=c + 5, low=c - 5, close=c))
    return bars


def _sma50(bars: list[PriceBar]) -> np.ndarray:
    sma50 = np.full(len(bars), np.nan)
    for i in range(49, len(bars)):
        sma50[i] = float(np.mean([b.close for b in bars[i - 49 : i + 1]]))
    return sma50


@pytest.mark.parametrize(
    "fixture_name",
    ["leg_uptrend", "leg_extended", "leg_shallow_pullback"],
)
def test_structure_fixture(fixture_name: str) -> None:
    path = FIXTURES_DIR / f"{fixture_name}.json"
    spec = json.loads(path.read_text(encoding="utf-8"))
    bars = _bars_from_closes(spec["closes"])
    result = compute_structure(
        bars,
        sma50=_sma50(bars),
        pct_above_200dma=spec["pct_above_200dma"],
    )
    expect = spec["expect"]

    if "downside_target_rules" in expect:
        assert result.downside_target_rule in expect["downside_target_rules"]
    if expect.get("active_swing_high_above_low"):
        assert result.active_swing_high_price > result.active_swing_low_price
    if "upside_target_rules" in expect:
        assert result.upside_target_rule in expect["upside_target_rules"]
    if expect.get("upside_above_close"):
        assert result.upside_target > bars[-1].close
    if "downside_target_rule" in expect:
        assert result.downside_target_rule == expect["downside_target_rule"]
