"""Structural swing detection, Fibonacci levels, liquidation zones, and MC targets.

DL-3 implementation spec (frozen):

Detection window
  - 300 trading days of ^GSPC daily bars (close, high, low).
  - Select the most recent structurally governing leg, not absolute window extremes.

Active swing high (confirmed local maximum)
  - Candidate local maximum: high[t] exceeds k neighbors on each side (default k=2).
  - Confirmed when either:
      (a) 3% pullback: subsequent close <= peak * 0.97, or
      (b) 5 consecutive sessions without a higher high.
  - Active swing high = most recent confirmed local maximum governing the current leg.

Active swing low (meaningful local minimum)
  - Candidate local minimum: low[t] below k neighbors on each side.
  - Confirmed when it preceded the current advance and either:
      (a) 5% rally: subsequent close >= trough * 1.05, or
      (b) recovery back above the 50-day SMA.
  - Active swing low = most recent meaningful confirmed minimum before the advance
    into the active swing high leg.

Monte Carlo primary targets
  - Upside: active swing high if close < swing high; else nearest structural
    resistance above price (next confirmed local max above close, else close * 1.0125).
  - Downside: 38.2% Fib default; promote to 50% Fib or first liquidation zone per rules.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from datetime import date
from typing import Literal, Sequence

import numpy as np

SwingConfirmation = Literal["pullback_3pct", "five_sessions", "rally_5pct", "above_50dma"]
UpsideTargetRule = Literal["active_swing_high", "next_local_max", "pct_extension"]
DownsideTargetRule = Literal[
    "fib_382",
    "fib_500",
    "first_liquidation_zone",
    "reanchor_liquidation",
    "reanchor_erp_floor",
    "reanchor_sma200",
    "reanchor_margin_call",
    "reanchor_fallback_pct",
]

LOCAL_EXTREMA_K = 2
PULLBACK_CONFIRM_PCT = 0.03
RALLY_CONFIRM_PCT = 0.05
STALE_HIGH_SESSIONS = 5
EXTENSION_FALLBACK_PCT = 0.0125
NEAR_FIB_PCT = 0.01
ELEVATED_EXTENSION_PCT = 12.0


@dataclass(frozen=True)
class PriceBar:
    session_date: date
    open: float
    high: float
    low: float
    close: float


@dataclass(frozen=True)
class ConfirmedSwing:
    index: int
    price: float
    session_date: date
    confirmation: SwingConfirmation


@dataclass(frozen=True)
class StructureResult:
    active_swing_high_date: str
    active_swing_high_price: float
    swing_high_confirmation: SwingConfirmation
    active_swing_low_date: str
    active_swing_low_price: float
    swing_low_confirmation: SwingConfirmation
    fib_236: float
    fib_382: float
    fib_500: float
    fib_618: float
    liquidation_caution: float
    liquidation_nervous: float
    liquidation_margin_call: float
    liquidation_cascade: float
    upside_target: float
    upside_target_rule: UpsideTargetRule
    downside_target: float
    downside_target_rule: DownsideTargetRule


def _highs(bars: Sequence[PriceBar]) -> np.ndarray:
    return np.array([b.high for b in bars], dtype=float)


def _lows(bars: Sequence[PriceBar]) -> np.ndarray:
    return np.array([b.low for b in bars], dtype=float)


def _closes(bars: Sequence[PriceBar]) -> np.ndarray:
    return np.array([b.close for b in bars], dtype=float)


def _candidate_local_maxima(highs: np.ndarray, k: int = LOCAL_EXTREMA_K) -> list[int]:
    n = len(highs)
    indices: list[int] = []
    for i in range(k, n - k):
        window = highs[i - k : i + k + 1]
        if highs[i] >= window.max() and highs[i] > highs[i - 1] and highs[i] > highs[i + 1]:
            indices.append(i)
    return indices


def _candidate_local_minima(lows: np.ndarray, k: int = LOCAL_EXTREMA_K) -> list[int]:
    n = len(lows)
    indices: list[int] = []
    for i in range(k, n - k):
        window = lows[i - k : i + k + 1]
        if lows[i] <= window.min() and lows[i] < lows[i - 1] and lows[i] < lows[i + 1]:
            indices.append(i)
    return indices


def _confirm_swing_high(highs: np.ndarray, closes: np.ndarray, peak_idx: int) -> SwingConfirmation | None:
    peak = highs[peak_idx]
    threshold = peak * (1.0 - PULLBACK_CONFIRM_PCT)
    for j in range(peak_idx + 1, len(closes)):
        if closes[j] <= threshold:
            return "pullback_3pct"
    stale = 0
    max_high = peak
    for j in range(peak_idx + 1, len(highs)):
        if highs[j] > max_high:
            return None
        stale += 1
        if stale >= STALE_HIGH_SESSIONS:
            return "five_sessions"
    return None


def _confirm_swing_low(
    lows: np.ndarray,
    closes: np.ndarray,
    sma50: np.ndarray,
    trough_idx: int,
) -> SwingConfirmation | None:
    trough = lows[trough_idx]
    rally_level = trough * (1.0 + RALLY_CONFIRM_PCT)
    for j in range(trough_idx + 1, len(closes)):
        if closes[j] >= rally_level:
            return "rally_5pct"
        if not math.isnan(sma50[j]) and closes[j] > sma50[j]:
            return "above_50dma"
    return None


def _confirmed_highs(bars: Sequence[PriceBar]) -> list[ConfirmedSwing]:
    highs = _highs(bars)
    closes = _closes(bars)
    confirmed: list[ConfirmedSwing] = []
    for idx in _candidate_local_maxima(highs):
        method = _confirm_swing_high(highs, closes, idx)
        if method is not None:
            confirmed.append(
                ConfirmedSwing(
                    index=idx,
                    price=float(highs[idx]),
                    session_date=bars[idx].session_date,
                    confirmation=method,
                )
            )
    return confirmed


def _confirmed_lows(bars: Sequence[PriceBar], sma50: np.ndarray) -> list[ConfirmedSwing]:
    lows = _lows(bars)
    closes = _closes(bars)
    confirmed: list[ConfirmedSwing] = []
    for idx in _candidate_local_minima(lows):
        method = _confirm_swing_low(lows, closes, sma50, idx)
        if method is not None:
            confirmed.append(
                ConfirmedSwing(
                    index=idx,
                    price=float(lows[idx]),
                    session_date=bars[idx].session_date,
                    confirmation=method,
                )
            )
    return confirmed


def _active_swing_high(bars: Sequence[PriceBar]) -> ConfirmedSwing:
    confirmed = _confirmed_highs(bars)
    if confirmed:
        return confirmed[-1]
    # Degenerate: use highest high in window
    highs = _highs(bars)
    idx = int(np.argmax(highs))
    return ConfirmedSwing(
        index=idx,
        price=float(highs[idx]),
        session_date=bars[idx].session_date,
        confirmation="five_sessions",
    )


def _active_swing_low(
    bars: Sequence[PriceBar],
    sma50: np.ndarray,
    swing_high: ConfirmedSwing,
) -> ConfirmedSwing:
    confirmed = [c for c in _confirmed_lows(bars, sma50) if c.index < swing_high.index]
    if confirmed:
        return confirmed[-1]
    lows = _lows(bars)
    window = lows[: swing_high.index + 1]
    idx = int(np.argmin(window))
    return ConfirmedSwing(
        index=idx,
        price=float(lows[idx]),
        session_date=bars[idx].session_date,
        confirmation="rally_5pct",
    )


def _fib_levels(high: float, low: float) -> tuple[float, float, float, float]:
    r = high - low
    return (
        high - 0.236 * r,
        high - 0.382 * r,
        high - 0.500 * r,
        high - 0.618 * r,
    )


def _liquidation_zones(swing_high: float) -> tuple[float, float, float, float]:
    return (
        swing_high * 0.97,
        swing_high * 0.95,
        swing_high * 0.90,
        swing_high * 0.85,
    )


def next_resistance_above(price: float, bars: Sequence[PriceBar]) -> float:
    """Next structural resistance above ``price`` (for MC cascade reporting)."""
    active_high = _active_swing_high(bars)
    level, _ = _nearest_resistance_above(price, bars, active_high)
    return level


def _nearest_resistance_above(
    close: float,
    bars: Sequence[PriceBar],
    active_high: ConfirmedSwing,
) -> tuple[float, UpsideTargetRule]:
    if close < active_high.price:
        return active_high.price, "active_swing_high"
    highs = _confirmed_highs(bars)
    above = [h for h in highs if h.price > close and h.index > active_high.index]
    if above:
        nearest = min(above, key=lambda h: h.price)
        return nearest.price, "next_local_max"
    return close * (1.0 + EXTENSION_FALLBACK_PCT), "pct_extension"


def _downside_target(
    close: float,
    fib_382: float,
    fib_500: float,
    first_liquidation: float,
    pct_above_200dma: float,
) -> tuple[float, DownsideTargetRule]:
    """Promotion rules per DL-3.

    Note: rule 2 uses first_liquidation_zone (−10% from swing high). For typical
    H→L legs that zone sits below fib_382, so rule 2 rarely fires; near-fib cases
    without a breach use fib_382 (rule 4) unless rule 3 (elevated extension) applies.
    """
    if close <= fib_382:
        return fib_500, "fib_500"
    if (
        first_liquidation > fib_382
        and abs(close - fib_382) / close <= NEAR_FIB_PCT
    ):
        return first_liquidation, "first_liquidation_zone"
    if pct_above_200dma > ELEVATED_EXTENSION_PCT:
        return fib_500, "fib_500"
    return fib_382, "fib_382"


def compute_structure(
    bars: Sequence[PriceBar],
    *,
    sma50: np.ndarray,
    pct_above_200dma: float,
) -> StructureResult:
    """Derive swing anchors, Fib levels, liquidation zones, and MC targets."""
    if len(bars) < 10:
        raise ValueError("need at least 10 price bars for structure detection")

    swing_high = _active_swing_high(bars)
    swing_low = _active_swing_low(bars, sma50, swing_high)
    close = float(bars[-1].close)

    fib_236, fib_382, fib_500, fib_618 = _fib_levels(swing_high.price, swing_low.price)
    liq_caution, liq_nervous, liq_margin, liq_cascade = _liquidation_zones(swing_high.price)

    upside, upside_rule = _nearest_resistance_above(close, bars, swing_high)
    downside, downside_rule = _downside_target(
        close, fib_382, fib_500, liq_margin, pct_above_200dma
    )

    return StructureResult(
        active_swing_high_date=swing_high.session_date.isoformat(),
        active_swing_high_price=swing_high.price,
        swing_high_confirmation=swing_high.confirmation,
        active_swing_low_date=swing_low.session_date.isoformat(),
        active_swing_low_price=swing_low.price,
        swing_low_confirmation=swing_low.confirmation,
        fib_236=fib_236,
        fib_382=fib_382,
        fib_500=fib_500,
        fib_618=fib_618,
        liquidation_caution=liq_caution,
        liquidation_nervous=liq_nervous,
        liquidation_margin_call=liq_margin,
        liquidation_cascade=liq_cascade,
        upside_target=upside,
        upside_target_rule=upside_rule,
        downside_target=downside,
        downside_target_rule=downside_rule,
    )


def reanchor_downside_for_straddle(
    result: StructureResult,
    close: float,
    *,
    erp_reentry_floor: float | None,
    sma_200: float | None,
) -> tuple[StructureResult, list[str]]:
    """Option-A straddle guard: enforce ``downside_target < close < upside_target``.

    Once the current close sits at or below the resolved downside target, the prior
    active H->L leg has been fully retraced (and likely broken), so its Fibonacci
    ladder is no longer a valid downside map. Re-anchor the downside target to the
    nearest structurally valid level strictly below spot, in priority order:

      1. nearest liquidation level strictly below spot,
      2. ERP re-entry floor (if strictly below spot),
      3. 200-day SMA (if strictly below spot),
      4. margin-call zone.

    A deterministic percentage fallback is used only if no structural level lies
    below spot (a catastrophic >15% break), so the straddle invariant always holds.
    Returns the (possibly updated) result and any precompute warnings.
    """
    warnings: list[str] = []
    prior_downside = result.downside_target

    if prior_downside < close:
        return result, warnings

    candidates: list[tuple[float, DownsideTargetRule]] = []
    liq_below = [
        z
        for z in (
            result.liquidation_caution,
            result.liquidation_nervous,
            result.liquidation_margin_call,
            result.liquidation_cascade,
        )
        if z < close
    ]
    if liq_below:
        candidates.append((max(liq_below), "reanchor_liquidation"))
    if erp_reentry_floor is not None and erp_reentry_floor < close:
        candidates.append((erp_reentry_floor, "reanchor_erp_floor"))
    if sma_200 is not None and sma_200 < close:
        candidates.append((sma_200, "reanchor_sma200"))
    if result.liquidation_margin_call < close:
        candidates.append((result.liquidation_margin_call, "reanchor_margin_call"))

    if candidates:
        new_downside, new_rule = candidates[0]
    else:
        new_downside = close * (1.0 - EXTENSION_FALLBACK_PCT)
        new_rule = "reanchor_fallback_pct"

    warnings.append(
        f"active leg fully retraced: close {close:.2f} <= prior downside target "
        f"{prior_downside:.2f} ({result.downside_target_rule}); re-anchored downside to "
        f"{new_downside:.2f} ({new_rule}) for Monte Carlo straddle validity"
    )
    updated = replace(
        result,
        downside_target=new_downside,
        downside_target_rule=new_rule,
    )
    return updated, warnings
