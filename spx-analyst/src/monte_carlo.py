"""Deterministic GBM Monte Carlo simulation (20k paths, 60-day horizon).

Probability semantics:
- ``prob_*_first_raw``: share of paths where upside/downside is hit first among
  paths that hit at least one target within the horizon (ties excluded).
- ``prob_up_first_adjusted``: raw upside-first minus rally-exhaustion discount.
- ``prob_down_first_adjusted``: complement of adjusted upside (not a separate
  downside discount).
- ``threshold_evaluation`` rows use adjusted upside-first vs 65/70/75% gates.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .schemas import MonteCarloContext, RallyExhaustionScore, ThresholdEvaluationRow
from .structure import PriceBar, StructureResult, next_resistance_above

RNG_SEED = 42
PATHS = 20_000
HORIZON_DAYS = 60
TRADING_DAYS_PER_YEAR = 252
MODERATE_DISCOUNT = 0.05
HIGH_DISCOUNT = 0.08
THRESHOLDS = (65, 70, 75)


@dataclass(frozen=True)
class ExhaustionInputs:
    move_magnitude_pct: float
    move_velocity_pct_per_week: float
    vol_compression_ratio: float


def select_mu(pct_above_200dma: float) -> float:
    if pct_above_200dma < 0:
        return 0.10
    if pct_above_200dma < 5:
        return 0.09
    if pct_above_200dma < 10:
        return 0.07
    if pct_above_200dma < 15:
        return 0.045
    return 0.025


def select_sigma(realized_vol_20d: float, vix: float) -> float:
    if realized_vol_20d > 0:
        return realized_vol_20d
    return vix / 100.0


def compute_exhaustion_score(inputs: ExhaustionInputs) -> tuple[RallyExhaustionScore, float]:
    elevated = 0
    if inputs.move_magnitude_pct >= 15:
        elevated += 1
    if inputs.move_magnitude_pct >= 20:
        elevated += 1
    if inputs.move_velocity_pct_per_week >= 1.5:
        elevated += 1
    if inputs.move_velocity_pct_per_week >= 2.5:
        elevated += 1
    if inputs.vol_compression_ratio < 0.85:
        elevated += 1

    # Map elevated count to score per DL-3
    if elevated >= 3:
        return "High", HIGH_DISCOUNT
    if elevated >= 2:
        return "Moderate", MODERATE_DISCOUNT
    return "Low", 0.0


def exhaustion_inputs_from_bars(
    bars: list[PriceBar],
    swing_low_price: float,
    swing_low_date_str: str,
    realized_vol_20d: float,
    realized_vol_60d: float,
) -> ExhaustionInputs:
    from datetime import date

    close = bars[-1].close
    magnitude = (close / swing_low_price - 1.0) * 100.0 if swing_low_price > 0 else 0.0
    low_date = date.fromisoformat(swing_low_date_str)
    weeks = max((bars[-1].session_date - low_date).days / 7.0, 1.0)
    velocity = magnitude / weeks
    ratio = realized_vol_20d / realized_vol_60d if realized_vol_60d > 0 else 1.0
    return ExhaustionInputs(
        move_magnitude_pct=magnitude,
        move_velocity_pct_per_week=velocity,
        vol_compression_ratio=ratio,
    )


def _simulate_paths(
    s0: float,
    mu: float,
    sigma: float,
    rng: np.random.Generator,
) -> np.ndarray:
    dt = 1.0 / TRADING_DAYS_PER_YEAR
    drift = (mu - 0.5 * sigma**2) * dt
    vol = sigma * np.sqrt(dt)
    shocks = rng.standard_normal((PATHS, HORIZON_DAYS))
    log_returns = drift + vol * shocks
    paths = s0 * np.exp(np.cumsum(log_returns, axis=1))
    return np.column_stack([np.full(PATHS, s0), paths])


def _first_hit_up_down(
    paths: np.ndarray,
    upside: float,
    downside: float,
) -> tuple[float, float]:
    up_first = 0
    down_first = 0
    for path in paths:
        hit_up = np.where(path >= upside)[0]
        hit_down = np.where(path <= downside)[0]
        t_up = hit_up[0] if len(hit_up) else HORIZON_DAYS + 1
        t_down = hit_down[0] if len(hit_down) else HORIZON_DAYS + 1
        if t_up < t_down:
            up_first += 1
        elif t_down < t_up:
            down_first += 1
    total = up_first + down_first
    if total == 0:
        return 0.5, 0.5
    return up_first / total, down_first / total


def _conditional_hit(paths: np.ndarray, level_a: float, level_b: float, direction: str) -> float:
    hits = 0
    count = 0
    for path in paths:
        if direction == "down":
            idx_a = np.where(path <= level_a)[0]
            if len(idx_a) == 0:
                continue
            count += 1
            start = idx_a[0]
            if np.any(path[start:] <= level_b):
                hits += 1
        else:
            idx_a = np.where(path >= level_a)[0]
            if len(idx_a) == 0:
                continue
            count += 1
            start = idx_a[0]
            if np.any(path[start:] >= level_b):
                hits += 1
    return hits / count if count else 0.0


def _median_days_to_level(paths: np.ndarray, level: float, direction: str) -> int:
    days: list[int] = []
    for path in paths:
        if direction == "up":
            idx = np.where(path >= level)[0]
        else:
            idx = np.where(path <= level)[0]
        if len(idx):
            days.append(int(idx[0]))
    if not days:
        return HORIZON_DAYS
    return int(np.median(days))


def _drift_path(s0: float, mu: float, sigma: float) -> str:
    dt = 1.0 / TRADING_DAYS_PER_YEAR
    points = [5, 10, 20, 30, 60]
    parts = []
    for t in points:
        expected = s0 * np.exp((mu - 0.5 * sigma**2) * (t / TRADING_DAYS_PER_YEAR))
        parts.append(f"{t}d={expected:.2f}")
    return "; ".join(parts)


def run_monte_carlo(
    *,
    s0: float,
    mu: float,
    sigma: float,
    structure: StructureResult,
    exhaustion_score: RallyExhaustionScore,
    exhaustion_discount: float,
    bars: list[PriceBar],
) -> MonteCarloContext:
    rng = np.random.default_rng(RNG_SEED)
    paths = _simulate_paths(s0, mu, sigma, rng)

    upside = structure.upside_target
    downside = structure.downside_target

    prob_up_raw, prob_down_raw = _first_hit_up_down(paths, upside, downside)
    prob_up_adj = max(0.0, min(1.0, prob_up_raw - exhaustion_discount))
    prob_down_adj = 1.0 - prob_up_adj

    # Cascades
    if structure.downside_target_rule == "fib_382":
        down_next = structure.fib_500
    elif structure.downside_target_rule == "fib_500":
        down_next = structure.fib_618
    else:
        lower_levels = [
            z
            for z in (
                structure.liquidation_caution,
                structure.liquidation_nervous,
                structure.liquidation_margin_call,
                structure.liquidation_cascade,
            )
            if z < downside
        ]
        down_next = max(lower_levels) if lower_levels else downside * (1.0 - 0.0125)
    p_down_cascade = _conditional_hit(paths, downside, down_next, "down")
    up_next = next_resistance_above(upside, bars)
    p_up_cascade = _conditional_hit(paths, upside, up_next, "up")
    cascades = (
        f"If {downside:.0f} breaks, P({down_next:.0f})={p_down_cascade:.0%}; "
        f"If {upside:.0f} breaks, P({up_next:.0f})={p_up_cascade:.0%}"
    )

    med_up = _median_days_to_level(paths, upside, "up")
    med_down = _median_days_to_level(paths, downside, "down")
    median_days = f"upside {med_up}d / downside {med_down}d"

    cash_drag = float(np.mean([not np.any(p <= downside) for p in paths]))

    threshold_eval = {}
    for th in THRESHOLDS:
        threshold = th / 100.0
        threshold_eval[str(th)] = ThresholdEvaluationRow(
            adjusted_prob_up_first=round(prob_up_adj, 4),
            actionable=prob_up_adj >= threshold,
        )

    return MonteCarloContext(
        sigma=round(sigma, 6),
        mu=round(mu, 6),
        rally_exhaustion_score=exhaustion_score,
        exhaustion_discount=exhaustion_discount,
        upside_target=upside,
        downside_target=downside,
        upside_target_rule=structure.upside_target_rule,
        downside_target_rule=structure.downside_target_rule,
        prob_up_first_raw=round(prob_up_raw, 4),
        prob_down_first_raw=round(prob_down_raw, 4),
        prob_up_first_adjusted=round(prob_up_adj, 4),
        prob_down_first_adjusted=round(prob_down_adj, 4),
        cascades=cascades,
        median_days=median_days,
        drift_path=_drift_path(s0, mu, sigma),
        cash_drag_prob=round(cash_drag, 4),
        threshold_evaluation=threshold_eval,
    )
