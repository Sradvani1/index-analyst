"""Tests for PR-24 StructureAnchorState resolver (anchor authority)."""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np

from src.structure import (
    PriceBar,
    StructureAnchorState,
    compute_structure,
    resolve_structure_anchors,
)


def _bars_from_rows(rows: list[tuple[float, float, float]], start: date | None = None) -> list[PriceBar]:
    """Build bars from (high, low, close) rows with sequential dates."""
    start = start or date(2026, 1, 1)
    return [
        PriceBar(session_date=start + timedelta(days=i), open=close, high=high, low=low, close=close)
        for i, (high, low, close) in enumerate(rows)
    ]


def _flat_rows(level: float, n: int) -> list[tuple[float, float, float]]:
    return [(level, level, level) for _ in range(n)]


def _sma50(bars: list[PriceBar]) -> np.ndarray:
    closes = np.array([b.close for b in bars], dtype=float)
    sma50 = np.full(len(closes), np.nan)
    for i in range(49, len(closes)):
        sma50[i] = float(np.mean(closes[i - 49 : i + 1]))
    return sma50


BASE = _bars_from_rows(_flat_rows(5000.0, 60))


def _observation() -> object:
    """Legacy observation computed over the base bars only (no session bar)."""
    return compute_structure(BASE, sma50=_sma50(BASE), pct_above_200dma=5.0)


def _session_bars(close: float, high: float) -> list[PriceBar]:
    """Base bars plus one current-session bar (passed to the resolver)."""
    return BASE + [
        PriceBar(
            session_date=date(2026, 3, 15),
            open=close,
            high=high,
            low=min(close, high) - 10.0,
            close=close,
        )
    ]


def _resolve(anchor, close: float, high: float, obs=None):
    bars = _session_bars(close, high)
    return resolve_structure_anchors(
        obs or _observation(),
        bars,
        anchor,
        _sma50(bars),
        pct_above_200dma=5.0,
    )

# --- State machine transitions -------------------------------------------------


def _anchor(
    *,
    high=5000.0,
    high_date="2026-02-10",
    low=4900.0,
    low_date="2026-01-15",
    low_source="prior_active_fallback",
    status="none",
    candidate_high=None,
    candidate_date=None,
    closes=0,
    version=1,
    confirmation="pullback_3pct",
):
    return StructureAnchorState(
        active_swing_high_price=high,
        active_swing_high_date=high_date,
        active_swing_low_price=low,
        active_swing_low_date=low_date,
        active_swing_low_source=low_source,
        swing_high_confirmation=confirmation,
        swing_low_confirmation="above_50dma",
        status=status,
        candidate_high=candidate_high,
        candidate_date=candidate_date,
        closes_above_reference=closes,
        anchor_version=version,
    )


def test_noop_below_reference():
    anchor = _anchor(high=5000.0, low=4900.0, version=3)
    result, new_state, warnings = _resolve(anchor, close=4900.0, high=4905.0)
    assert new_state.status == "none"
    assert new_state.anchor_version == 3
    assert warnings == []
    # Geometry emitted from the authoritative state, not the observation.
    assert result.active_swing_high_price == 5000.0
    assert result.anchor_version == 3


def test_first_close_above_sets_unconfirmed():
    anchor = _anchor(high=5000.0, low=4900.0, version=1)
    result, new_state, warnings = _resolve(anchor, close=5020.0, high=5030.0)
    assert new_state.status == "unconfirmed_new_high"
    assert new_state.candidate_high == 5030.0
    assert new_state.closes_above_reference == 1
    assert new_state.anchor_version == 1
    assert result.active_swing_high_price == 5000.0
    assert any("unconfirmed" in w for w in warnings)


def test_second_qualifying_close_confirms_and_reanchors():
    anchor = _anchor(
        high=5000.0,
        low=4900.0,
        status="unconfirmed_new_high",
        candidate_high=5030.0,
        candidate_date="2026-03-10",
        closes=1,
        version=1,
    )
    result, new_state, warnings = _resolve(anchor, close=5040.0, high=5050.0)
    assert new_state.status == "confirmed_new_high"
    assert new_state.anchor_version == 2
    # Highest candidate in the window ratchets over 5030.
    assert new_state.active_swing_high_price == 5050.0
    assert result.active_swing_high_price == 5050.0
    assert result.anchor_version == 2
    assert result.prior_swing_high_price == 5000.0
    assert any("breakout confirmed" in w for w in warnings)


def test_close_below_before_confirmation_fails():
    anchor = _anchor(
        high=5000.0,
        low=4900.0,
        status="unconfirmed_new_high",
        candidate_high=5030.0,
        candidate_date="2026-03-10",
        closes=1,
        version=1,
    )
    result, new_state, warnings = _resolve(anchor, close=4990.0, high=5035.0)
    assert new_state.status == "failed_breakout"
    # Candidate not updated by the failed day's intraday high.
    assert new_state.candidate_high == 5030.0
    assert any("failed" in w for w in warnings)


def test_failed_then_reattempt_sets_unconfirmed():
    anchor = _anchor(
        high=5000.0,
        low=4900.0,
        status="failed_breakout",
        candidate_high=5030.0,
        candidate_date="2026-03-10",
        closes=1,
        version=1,
    )
    result, new_state, warnings = _resolve(anchor, close=5040.0, high=5045.0)
    assert new_state.status == "unconfirmed_new_high"
    assert new_state.closes_above_reference == 1
    assert new_state.candidate_high == 5045.0
    assert any("breakout attempt" in w for w in warnings)


def test_exact_reference_retest_is_pending():
    anchor = _anchor(
        high=5000.0,
        low=4900.0,
        status="unconfirmed_new_high",
        candidate_high=5030.0,
        candidate_date="2026-03-10",
        closes=1,
        version=1,
    )
    result, new_state, warnings = _resolve(anchor, close=5000.0, high=5005.0)
    assert new_state.status == "unconfirmed_new_high"
    assert new_state.closes_above_reference == 1
    assert warnings == []


# --- Ratchet behavior ----------------------------------------------------------


def test_post_confirmation_ratchet_no_version_increment():
    anchor = _anchor(
        high=5050.0,
        low=4900.0,
        status="confirmed_new_high",
        version=2,
    )
    result, new_state, warnings = _resolve(anchor, close=5070.0, high=5080.0)
    assert new_state.active_swing_high_price == 5080.0
    assert new_state.anchor_version == 2
    assert result.active_swing_high_price == 5080.0
    assert result.anchor_version == 2
    assert any("ratcheted" in w for w in warnings)


def test_no_downgrade_on_lower_session_high():
    anchor = _anchor(
        high=5080.0,
        low=4900.0,
        status="confirmed_new_high",
        version=2,
    )
    result, new_state, warnings = _resolve(anchor, close=5070.0, high=5070.0)
    assert new_state.active_swing_high_price == 5080.0
    assert new_state.anchor_version == 2
    assert warnings == []


# --- Persistence over legacy staleness ------------------------------------------


def test_persistence_over_legacy_staleness():
    # Published breakout at 7600; legacy observation still reports 7526.
    anchor = _anchor(
        high=7600.0,
        low=7316.0,
        status="confirmed_new_high",
        version=2,
    )
    obs = _observation()
    from dataclasses import replace as dc_replace

    stale_obs = dc_replace(
        obs,
        active_swing_high_price=7526.0,
        active_swing_high_date="2026-07-22",
    )
    result, new_state, warnings = _resolve(anchor, close=7610.0, high=7620.0, obs=stale_obs)
    # Reference stays the published 7600, not the stale 7526.
    assert new_state.active_swing_high_price == 7620.0  # ratchet from 7600
    assert new_state.anchor_version == 2
    assert result.active_swing_high_price == 7620.0


def test_noop_after_breakout_keeps_published_anchor():
    # Legacy still reports 7526; close below published 7600 (no-op day).
    anchor = _anchor(
        high=7600.0,
        low=7316.0,
        status="confirmed_new_high",
        version=2,
    )
    obs = _observation()
    from dataclasses import replace as dc_replace

    stale_obs = dc_replace(
        obs,
        active_swing_high_price=7526.0,
        active_swing_high_date="2026-07-22",
    )
    result, new_state, warnings = _resolve(anchor, close=7550.0, high=7560.0, obs=stale_obs)
    # Must NOT regress to the stale 7526 observation.
    assert new_state.active_swing_high_price == 7600.0
    assert result.active_swing_high_price == 7600.0
    assert new_state.anchor_version == 2


# --- Conventional-swing path -----------------------------------------------------


def test_conventional_confirmation_publishes_immediately():
    anchor = _anchor(high=5000.0, low=4900.0, version=1)
    obs = _observation()
    from dataclasses import replace as dc_replace

    conv_obs = dc_replace(
        obs,
        active_swing_high_price=5100.0,
        active_swing_high_date="2026-03-15",
        swing_high_confirmation="pullback_3pct",
    )
    result, new_state, warnings = _resolve(anchor, close=5100.0, high=5110.0, obs=conv_obs)
    assert new_state.status == "none"
    assert new_state.active_swing_high_price == 5100.0
    assert new_state.anchor_version == 2
    assert result.anchor_version == 2
    assert any("conventional swing confirmed" in w for w in warnings)


def test_conventional_not_strictly_above_is_noop():
    anchor = _anchor(high=5000.0, low=4900.0, version=1)
    obs = _observation()
    from dataclasses import replace as dc_replace

    conv_obs = dc_replace(obs, active_swing_high_price=5000.0)
    result, new_state, warnings = _resolve(anchor, close=4950.0, high=4960.0, obs=conv_obs)
    assert new_state is anchor
    assert warnings == []


# --- Fib-low fallback tiers -------------------------------------------------------


def test_fib_low_intermediate_confirmed():
    rows = _flat_rows(6000.0, 55)
    dip = [(5900.0, 5890.0, 5900.0), (5850.0, 5840.0, 5850.0), (5810.0, 5800.0, 5800.0)]
    rows += dip
    rows += _flat_rows(6000.0, 3)  # so the dip is a confirmed low
    rows += [(6210.0, 6190.0, 6200.0)]  # current session
    bars = _bars_from_rows(rows)
    sma50 = _sma50(bars)
    obs = compute_structure(bars[:-1], sma50=sma50[:-1], pct_above_200dma=5.0)
    prior_high_date = bars[54].session_date.isoformat()
    candidate_date = bars[-1].session_date.isoformat()
    anchor = _anchor(
        high=6000.0,
        high_date=prior_high_date,
        low=5600.0,
        low_date="2026-01-01",
        status="unconfirmed_new_high",
        candidate_high=6200.0,
        candidate_date=candidate_date,
        closes=1,
        version=1,
    )
    result, new_state, warnings = resolve_structure_anchors(
        obs, bars, anchor, sma50, pct_above_200dma=5.0
    )
    assert new_state.active_swing_low_source == "intermediate_confirmed"
    assert new_state.active_swing_low_price == 5800.0
    assert result.active_swing_low_source == "intermediate_confirmed"


def test_fib_low_prior_active_fallback():
    anchor = _anchor(
        high=5000.0,
        low=4700.0,
        status="unconfirmed_new_high",
        candidate_high=5050.0,
        candidate_date="2026-03-10",
        closes=1,
        version=1,
    )
    result, new_state, warnings = _resolve(anchor, close=5040.0, high=5050.0)
    assert new_state.status == "confirmed_new_high"
    assert new_state.active_swing_low_source == "prior_active_fallback"
    assert new_state.active_swing_low_price == 4700.0
    assert "unavailable" not in " ".join(warnings)


def test_fib_low_unavailable_suppresses_ladder():
    anchor = _anchor(
        high=5000.0,
        high_date="2026-02-10",
        low=None,
        low_date=None,
        low_source=None,
        status="unconfirmed_new_high",
        candidate_high=5050.0,
        candidate_date="2026-03-10",
        closes=1,
        version=1,
    )
    result, new_state, warnings = _resolve(anchor, close=5040.0, high=5050.0)
    assert new_state.active_swing_low_source == "unavailable"
    assert result.active_swing_low_source == "unavailable"
    assert any("unavailable" in w for w in warnings)


# --- Simultaneous confirmation -----------------------------------------------------


def test_simultaneous_conventional_and_breakout_one_transition():
    anchor = _anchor(
        high=5000.0,
        low=4900.0,
        status="unconfirmed_new_high",
        candidate_high=5040.0,
        candidate_date="2026-03-10",
        closes=1,
        version=1,
    )
    obs = _observation()
    from dataclasses import replace as dc_replace

    conv_obs = dc_replace(
        obs,
        active_swing_high_price=5050.0,
        active_swing_high_date="2026-03-15",
        swing_high_confirmation="pullback_3pct",
    )
    result, new_state, warnings = _resolve(anchor, close=5050.0, high=5060.0, obs=conv_obs)
    # One transition, one version increment.
    assert new_state.anchor_version == 2
    assert new_state.active_swing_high_price == 5050.0
    assert result.anchor_version == 2
    assert any("conventional swing confirmed" in w for w in warnings)


# --- Initialization semantics ---------------------------------------------------------


def test_seeded_anchor_state_has_version_one():
    from src.precompute import _seed_anchor_state

    obs = _observation()
    seeded = _seed_anchor_state(obs, "intermediate_confirmed")
    assert seeded.anchor_version == 1
    assert seeded.status == "none"
    assert seeded.active_swing_high_price == obs.active_swing_high_price


# --- Regression fixes (PR-24 review pass) -----------------------------------------


def test_confirm_keeps_original_candidate_date_when_no_ratchet():
    # Candidate high set on day1 (2026-03-10); day2 session high EQUALS candidate.
    # Confirmation must publish 5030 with the day1 date, not today's date.
    anchor = _anchor(
        high=5000.0,
        low=4900.0,
        status="unconfirmed_new_high",
        candidate_high=5030.0,
        candidate_date="2026-03-10",
        closes=1,
        version=1,
    )
    result, new_state, _ = _resolve(anchor, close=5040.0, high=5030.0)
    assert new_state.status == "confirmed_new_high"
    assert new_state.active_swing_high_price == 5030.0
    assert new_state.active_swing_high_date == "2026-03-10"


def test_fib_low_unavailable_downside_target_not_zero():
    anchor = _anchor(
        high=5000.0,
        high_date="2026-02-10",
        low=None,
        low_date=None,
        low_source=None,
        status="unconfirmed_new_high",
        candidate_high=5050.0,
        candidate_date="2026-03-10",
        closes=1,
        version=1,
    )
    result, new_state, warnings = _resolve(anchor, close=5040.0, high=5050.0)
    assert new_state.active_swing_low_source == "unavailable"
    assert result.active_swing_low_source == "unavailable"
    assert any("unavailable" in w for w in warnings)
    # Downside must stay positive and below spot (straddle validity), not degenerate to 0.
    assert result.downside_target > 0
    assert result.downside_target < 5040.0
    assert result.downside_target_rule == "reanchor_fallback_pct"


def test_reference_none_returns_observation_without_crash():
    from src.structure import StructureAnchorState

    empty = StructureAnchorState()
    bars = _session_bars(4950.0, 4960.0)
    obs = _observation()
    result, new_state, warnings = resolve_structure_anchors(
        obs, bars, empty, _sma50(bars), pct_above_200dma=5.0
    )
    assert new_state is empty
    assert result is obs
    assert any("no authoritative anchor" in w for w in warnings)


def test_no_future_fib_leakage():
    from datetime import date, timedelta

    from src.structure import _find_intermediate_swing_low

    rows = []
    for i in range(70):
        c = 6000.0 - (i % 7)
        rows.append(
            PriceBar(session_date=date(2026, 1, 1) + timedelta(days=i), open=c, high=c + 5, low=c - 5, close=c)
        )

    def set_bar(idx, high, low, close):
        d = rows[idx].session_date
        rows[idx] = PriceBar(session_date=d, open=close, high=high, low=low, close=close)

    set_bar(50, 6100, 5950, 6000)  # prior high
    set_bar(60, 6200, 6000, 6190)  # candidate high (current session)
    set_bar(65, 6050, 5800, 5850)  # deep low AFTER candidate -> must not be selected
    sma = _sma50(rows)
    low = _find_intermediate_swing_low(
        rows, sma, rows[50].session_date.isoformat(), rows[60].session_date.isoformat()
    )
    assert low is None or low.index < 60
