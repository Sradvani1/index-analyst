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

SwingConfirmation = Literal[
    "pullback_3pct",
    "five_sessions",
    "rally_5pct",
    "above_50dma",
    "unconfirmed_new_high",
]
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
    prior_swing_high_price: float | None = None
    prior_swing_high_date: str | None = None
    active_swing_low_source: str | None = None
    anchor_version: int = 1


@dataclass(frozen=True)
class StructureAnchorState:
    """Persistent authoritative anchor identity + breakout-sequence tracking.

    This is the sole source of the published active anchor geometry. The
    legacy local-extrema detector in ``compute_structure`` emits observations
    only; ``resolve_structure_anchors`` decides the published anchors.
    """

    # Persisted authoritative anchor identity.
    active_swing_high_price: float | None = None
    active_swing_high_date: str | None = None
    active_swing_low_price: float | None = None
    active_swing_low_date: str | None = None
    active_swing_low_source: str | None = None
    swing_high_confirmation: str | None = None
    swing_low_confirmation: str | None = None
    # The anchor superseded by the current active high (now reclaimed support).
    # Persisted so every precompute call in a session emits the same context.
    prior_swing_high_price: float | None = None
    prior_swing_high_date: str | None = None

    # Breakout-sequence tracking.
    status: str = "none"  # none | unconfirmed_new_high | confirmed_new_high | failed_breakout
    candidate_high: float | None = None
    candidate_date: str | None = None
    closes_above_reference: int = 0

    # Idempotency: the session date the state was last advanced on. A single
    # trading day's precompute may run more than once (prepare + run), so the
    # machine must not count the same session twice.
    last_processed_date: str | None = None

    anchor_version: int = 1


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


def _bar_index_by_date(bars: Sequence[PriceBar], date_str: str) -> int:
    for i, b in enumerate(bars):
        if b.session_date.isoformat() == date_str:
            return i
    return -1


def _find_intermediate_swing_low(
    bars: Sequence[PriceBar],
    sma50: np.ndarray,
    prior_high_date: str,
    candidate_date: str,
) -> ConfirmedSwing | None:
    """Lowest confirmed local minimum strictly between two dated bars.

    Scans the bar range (prior_high_date, candidate_date) exclusive on both
    ends; never looks beyond the candidate bar. Returns None when no confirmed
    swing low exists in that window.
    """
    start = _bar_index_by_date(bars, prior_high_date)
    end = _bar_index_by_date(bars, candidate_date)
    if start < 0 or end < 0 or end - start < 2:
        return None
    lows = [c for c in _confirmed_lows(bars, sma50) if start < c.index < end]
    if not lows:
        return None
    return min(lows, key=lambda c: c.price)


def _low_source_and_value(
    bars: Sequence[PriceBar],
    sma50: np.ndarray,
    prior_high_date: str,
    candidate_date: str,
    anchor_state: StructureAnchorState,
) -> tuple[float | None, str | None, str]:
    """Three-tier fib-low selection for a confirmed re-anchor."""
    inter = _find_intermediate_swing_low(bars, sma50, prior_high_date, candidate_date)
    if inter is not None:
        return inter.price, inter.session_date.isoformat(), "intermediate_confirmed"
    if anchor_state.active_swing_low_price is not None:
        return (
            anchor_state.active_swing_low_price,
            anchor_state.active_swing_low_date,
            "prior_active_fallback",
        )
    return None, None, "unavailable"


def _result_from_anchor_state(
    anchor_state: StructureAnchorState,
    bars: Sequence[PriceBar],
    pct_above_200dma: float,
) -> StructureResult:
    """Build the published StructureResult from the authoritative anchor state.

    This is the single place geometry is emitted. Every resolver path —
    including no-op days — emits from the state's anchors, never from the
    possibly-stale legacy observation.
    """
    close = float(bars[-1].close)
    new_high = anchor_state.active_swing_high_price
    new_low = anchor_state.active_swing_low_price
    new_low_date = anchor_state.active_swing_low_date
    low_source = anchor_state.active_swing_low_source or "unavailable"
    new_low_confirmation: SwingConfirmation = (
        anchor_state.swing_low_confirmation or "above_50dma"
    ) if anchor_state.swing_low_confirmation in (
        "pullback_3pct",
        "five_sessions",
        "rally_5pct",
        "above_50dma",
        "unconfirmed_new_high",
    ) else "above_50dma"
    new_high_confirmation: SwingConfirmation = (
        anchor_state.swing_high_confirmation or "five_sessions"
    ) if anchor_state.swing_high_confirmation in (
        "pullback_3pct",
        "five_sessions",
        "rally_5pct",
        "above_50dma",
        "unconfirmed_new_high",
    ) else "five_sessions"

    assert new_high is not None, "published anchor state must carry an active swing high"
    liq_caution, liq_nervous, liq_margin, liq_cascade = _liquidation_zones(new_high)

    if new_low is not None:
        fib_236, fib_382, fib_500, fib_618 = _fib_levels(new_high, new_low)
        downside, downside_rule = _downside_target(
            close,
            fib_382,
            fib_500,
            liq_margin,
            pct_above_200dma,
        )
    else:
        # No fib low (unavailable): suppress the ladder but keep a sane
        # downside target so Monte Carlo never degenerates to 0.
        fib_236 = fib_382 = fib_500 = fib_618 = 0.0
        downside = close * (1.0 - EXTENSION_FALLBACK_PCT)
        downside_rule = "reanchor_fallback_pct"

    active_high = ConfirmedSwing(
        index=_bar_index_by_date(bars, anchor_state.active_swing_high_date or ""),
        price=new_high,
        session_date=(
            bars[0].session_date
            if _bar_index_by_date(bars, anchor_state.active_swing_high_date or "") < 0
            else bars[_bar_index_by_date(bars, anchor_state.active_swing_high_date or "")].session_date
        ),
        confirmation=new_high_confirmation,
    )
    upside, upside_rule = _nearest_resistance_above(close, bars, active_high)

    return StructureResult(
        active_swing_high_date=anchor_state.active_swing_high_date or "",
        active_swing_high_price=new_high,
        swing_high_confirmation=new_high_confirmation,
        active_swing_low_date=new_low_date or "",
        active_swing_low_price=new_low if new_low is not None else 0.0,
        swing_low_confirmation=new_low_confirmation,
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
        prior_swing_high_price=anchor_state.prior_swing_high_price,
        prior_swing_high_date=anchor_state.prior_swing_high_date,
        active_swing_low_source=low_source,
        anchor_version=anchor_state.anchor_version,
    )


def resolve_structure_anchors(
    result: StructureResult,
    bars: Sequence[PriceBar],
    anchor_state: StructureAnchorState,
    sma50: np.ndarray,
    *,
    pct_above_200dma: float,
) -> tuple[StructureResult, StructureAnchorState, list[str]]:
    """Sole publisher of active anchor geometry for a session.

    ``anchor_state.active_swing_high_price`` is the authoritative reference
    (not ``result.active_swing_high_price``, the legacy observation). Applies
    the conventional-swing path and the two-close breakout machine; publishes
    at most one anchor transition and one ``anchor_version`` increment. Every
    path emits geometry from the authoritative anchor state, never from the
    possibly-stale legacy observation.
    """
    warnings: list[str] = []
    close = float(bars[-1].close)
    session_high = float(bars[-1].high)
    session_date = bars[-1].session_date.isoformat()
    reference = anchor_state.active_swing_high_price

    # Idempotency: a single session may be precomputed more than once in one
    # pipeline (prepare + run both call run_precompute). Never re-advance the
    # state machine for a session that has already been resolved.
    if anchor_state.last_processed_date == session_date:
        return (
            _result_from_anchor_state(anchor_state, bars, pct_above_200dma),
            anchor_state,
            warnings,
        )

    def emit(
        state: StructureAnchorState,
    ) -> tuple[StructureResult, StructureAnchorState, list[str]]:
        stamped = replace(state, last_processed_date=session_date)
        return (
            _result_from_anchor_state(stamped, bars, pct_above_200dma),
            stamped,
            warnings,
        )

    # --- Conventional-swing path: legacy detector confirms a higher swing high ---
    if (
        reference is not None
        and result.active_swing_high_price is not None
        and result.active_swing_high_price > reference
    ):
        low_price, low_date, low_source = _low_source_and_value(
            bars,
            sma50,
            anchor_state.active_swing_high_date or "",
            result.active_swing_high_date,
            anchor_state,
        )
        if low_source == "unavailable":
            warnings.append("Fib ladder unavailable: no confirmed structural low")
        new_version = anchor_state.anchor_version + 1
        new_state = StructureAnchorState(
            active_swing_high_price=result.active_swing_high_price,
            active_swing_high_date=result.active_swing_high_date,
            active_swing_low_price=low_price,
            active_swing_low_date=low_date,
            active_swing_low_source=low_source,
            swing_high_confirmation=result.swing_high_confirmation,
            swing_low_confirmation=(
                "rally_5pct" if low_source == "intermediate_confirmed" else result.swing_low_confirmation
            ),
            prior_swing_high_price=reference,
            prior_swing_high_date=anchor_state.active_swing_high_date,
            status="none",
            anchor_version=new_version,
        )
        warnings.append(
            f"conventional swing confirmed: active swing high re-anchored "
            f"{reference:.2f} -> {result.active_swing_high_price:.2f} (anchor_version={new_version})"
        )
        return emit(new_state)

    # --- Breakout path ---
    if reference is None:
        warnings.append("no authoritative anchor reference; returning legacy observation")
        return result, anchor_state, warnings

    # Pending: close exactly at reference.
    if close == reference:
        return emit(anchor_state)

    # Failure: unconfirmed breakout closes back below the reference.
    if close < reference:
        if anchor_state.status == "unconfirmed_new_high":
            new_state = replace(anchor_state, status="failed_breakout")
            warnings.append(
                f"breakout above {reference:.2f} failed; prior anchors retained"
            )
            return emit(new_state)
        return emit(anchor_state)

    # close > reference
    if anchor_state.status == "none":
        new_state = replace(
            anchor_state,
            status="unconfirmed_new_high",
            candidate_high=session_high,
            candidate_date=session_date,
            closes_above_reference=1,
        )
        warnings.append(
            f"new high {session_high:.2f} above active swing high {reference:.2f}; "
            "unconfirmed — provisional"
        )
        return emit(new_state)

    if anchor_state.status == "unconfirmed_new_high":
        count = anchor_state.closes_above_reference + 1
        prior_cand = anchor_state.candidate_high
        prior_cand_date = anchor_state.candidate_date
        # Only ratchet (candidate_high/candidate_date) on a strictly higher session high.
        if prior_cand is None or session_high > prior_cand:
            cand = session_high
            cand_date = session_date
        else:
            cand = prior_cand
            cand_date = prior_cand_date if prior_cand_date is not None else session_date
        if count < 2:
            new_state = replace(
                anchor_state,
                status="unconfirmed_new_high",
                candidate_high=cand,
                candidate_date=cand_date,
                closes_above_reference=count,
            )
            return emit(new_state)
        # Confirm on second close.
        low_price, low_date, low_source = _low_source_and_value(
            bars,
            sma50,
            anchor_state.active_swing_high_date or "",
            cand_date,
            anchor_state,
        )
        if low_source == "unavailable":
            warnings.append("Fib ladder unavailable: no confirmed structural low")
        new_version = anchor_state.anchor_version + 1
        new_state = StructureAnchorState(
            active_swing_high_price=cand,
            active_swing_high_date=cand_date,
            active_swing_low_price=low_price,
            active_swing_low_date=low_date,
            active_swing_low_source=low_source,
            swing_high_confirmation="unconfirmed_new_high",
            swing_low_confirmation="above_50dma",
            prior_swing_high_price=reference,
            prior_swing_high_date=anchor_state.active_swing_high_date,
            status="confirmed_new_high",
            anchor_version=new_version,
        )
        warnings.append(
            f"breakout confirmed: active swing high re-anchored "
            f"{reference:.2f} -> {cand:.2f} (anchor_version={new_version})"
        )
        return emit(new_state)

    if anchor_state.status == "failed_breakout":
        new_state = replace(
            anchor_state,
            status="unconfirmed_new_high",
            candidate_high=session_high,
            candidate_date=session_date,
            closes_above_reference=1,
        )
        warnings.append(
            f"new breakout attempt above {reference:.2f}; unconfirmed — provisional"
        )
        return emit(new_state)

    # confirmed_new_high: ratchet the high without a version increment.
    if anchor_state.status == "confirmed_new_high":
        if session_high <= (anchor_state.active_swing_high_price or session_high):
            return emit(anchor_state)
        new_state = replace(
            anchor_state,
            active_swing_high_price=session_high,
            active_swing_high_date=session_date,
        )
        warnings.append(
            f"active swing high ratcheted to {session_high:.2f} "
            "(same leg; anchor_version unchanged)"
        )
        return emit(new_state)

    return emit(anchor_state)
