"""Tests for valuation precompute."""

from __future__ import annotations

from src.schemas import MarketDataContext, ResolvedEps
from src.valuation import compute_valuation_context, erp_reentry_floor_price


def test_erp_reentry_floor():
    floor = erp_reentry_floor_price(354.0, 4.5, target_erp=0.005)
    assert floor is not None
    assert floor > 0


def test_compute_valuation_context():
    market = MarketDataContext(
        spx_close=6000.0,
        vix=18.0,
        us10y=4.5,
        as_of_date="2026-06-12",
        pct_above_200dma=8.0,
        realized_vol_20d=0.15,
        sma_50=5900.0,
        sma_200=5700.0,
    )
    external = ResolvedEps(forward_eps=354.0, trailing_eps=220.0, effective_from="2026-06-12")
    tnx = [4.3, 4.35, 4.4, 4.42, 4.45, 4.5]
    val = compute_valuation_context(market, external, tnx)
    assert val.forward_pe == round(6000 / 354, 2)
    assert val.trailing_pe == round(6000 / 220, 2)
    assert val.erp is not None
    assert val.erp_trend in ("expanding", "stable", "contracting")
