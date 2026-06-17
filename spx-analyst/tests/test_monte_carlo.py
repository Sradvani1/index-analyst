"""Tests for deterministic Monte Carlo."""

from __future__ import annotations

from datetime import date

from src.monte_carlo import RNG_SEED, run_monte_carlo, select_mu, select_sigma
from src.structure import PriceBar, compute_structure
import numpy as np
import pytest


def _flat_bars(close: float, n: int = 100) -> list[PriceBar]:
    return [
        PriceBar(session_date=date(2025, 1, 1), open=close, high=close + 1, low=close - 1, close=close)
        for _ in range(n)
    ]


def test_monte_carlo_reproducible():
    bars = _flat_bars(6000.0, 120)
    for i, b in enumerate(bars):
        bars[i] = PriceBar(
            session_date=date(2025, 1, 1),
            open=6000 + i,
            high=6050 + i,
            low=5950,
            close=6000 + i * 0.5,
        )
    sma50 = np.full(len(bars), 5900.0)
    structure = compute_structure(bars, sma50=sma50, pct_above_200dma=5.0)
    mu = select_mu(5.0)
    sigma = select_sigma(0.18, 20.0)
    mc1 = run_monte_carlo(
        s0=6000.0,
        mu=mu,
        sigma=sigma,
        structure=structure,
        exhaustion_score="Low",
        exhaustion_discount=0.0,
        bars=bars,
    )
    mc2 = run_monte_carlo(
        s0=6000.0,
        mu=mu,
        sigma=sigma,
        structure=structure,
        exhaustion_score="Low",
        exhaustion_discount=0.0,
        bars=bars,
    )
    assert mc1.prob_up_first_raw == mc2.prob_up_first_raw
    assert "65" in mc1.threshold_evaluation
    assert mc1.threshold_evaluation["65"].actionable == (
        mc1.prob_up_first_adjusted >= 0.65
    )


def test_select_mu_sigma():
    assert select_mu(20) < select_mu(2)
    assert select_sigma(0.2, 18) == 0.2
    assert select_sigma(0, 22) == 0.22


def test_adjusted_probs_complement_after_discount():
    bars = _flat_bars(6000.0, 120)
    for i, b in enumerate(bars):
        bars[i] = PriceBar(
            session_date=date(2025, 1, 1),
            open=6000 + i,
            high=6050 + i,
            low=5950,
            close=6000 + i * 0.5,
        )
    sma50 = np.full(len(bars), 5900.0)
    structure = compute_structure(bars, sma50=sma50, pct_above_200dma=5.0)
    mc = run_monte_carlo(
        s0=6000.0,
        mu=select_mu(5.0),
        sigma=select_sigma(0.18, 20.0),
        structure=structure,
        exhaustion_score="Moderate",
        exhaustion_discount=0.05,
        bars=bars,
    )
    assert mc.prob_up_first_adjusted == pytest.approx(
        max(0.0, mc.prob_up_first_raw - 0.05), abs=1e-4
    )
    assert mc.prob_down_first_adjusted == pytest.approx(1.0 - mc.prob_up_first_adjusted, abs=1e-4)
