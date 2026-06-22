"""Unit tests for posture snapshot memory rollup (PR-3)."""

from __future__ import annotations

import copy
import re

from src.memory import (
    _bucket_fear_greed,
    _bucket_vix,
    _build_unresolved_watchlist,
    _format_day,
    _normalize_action,
    _regime_arc,
    _signal_labels,
    build_recent_summary,
    load_recent_states,
    load_recent_states_with_stats,
    rebuild_rolling_summary,
)
from src.schemas import DailyState, SignalSet

from tests.conftest import SAMPLE_STATE, write_state


def _state(**overrides) -> DailyState:
    data = copy.deepcopy(SAMPLE_STATE)
    data.update(overrides)
    return DailyState.model_validate(data)


def test_load_recent_states_orders_newest_first(settings):
    for date in ["2026-06-09", "2026-06-10", "2026-06-11"]:
        write_state(settings, date)
    states = load_recent_states(limit=5, settings=settings)
    assert [s.date for s in states] == ["2026-06-11", "2026-06-10", "2026-06-09"]


def test_load_recent_states_respects_limit_and_before(settings):
    for date in ["2026-06-09", "2026-06-10", "2026-06-11", "2026-06-12"]:
        write_state(settings, date)
    states = load_recent_states(limit=2, before_date="2026-06-12", settings=settings)
    assert [s.date for s in states] == ["2026-06-11", "2026-06-10"]


def test_load_recent_states_skips_malformed(settings):
    write_state(settings, "2026-06-10")
    bad = settings.daily_states_dir / "2026-06-11-state.json"
    bad.write_text("{broken", encoding="utf-8")
    states = load_recent_states(limit=5, settings=settings)
    assert [s.date for s in states] == ["2026-06-10"]


def test_load_recent_states_with_stats_counts(settings):
    for date in ["2026-06-09", "2026-06-10"]:
        write_state(settings, date)
    write_state(settings, "2026-06-12")
    bad = settings.daily_states_dir / "2026-06-11-state.json"
    bad.write_text("{broken", encoding="utf-8")
    states, stats = load_recent_states_with_stats(
        limit=2, before_date="2026-06-12", settings=settings
    )
    assert isinstance(states, list)
    assert [s.date for s in states] == ["2026-06-10", "2026-06-09"]
    assert stats.requested == 2
    assert stats.loaded == 2
    assert stats.skipped_before_date == 1
    assert stats.skipped_invalid == 1


def test_load_recent_states_delegates_to_stats(settings):
    write_state(settings, "2026-06-10")
    states = load_recent_states(limit=5, settings=settings)
    _, stats = load_recent_states_with_stats(limit=5, settings=settings)
    assert len(states) == stats.loaded


def test_build_recent_summary_empty():
    assert "No prior sessions" in build_recent_summary([])


def test_format_day_structure(sample_state):
    block = _format_day(sample_state)
    assert block.startswith("### 2026-06-11")
    assert "Mid Bull | mixed | action:" in block
    assert block.startswith("###")
    assert "signals:" in block
    assert "changed:" in block
    assert "tension:" in block


def test_signal_labels_categorical_only():
    s = _state(
        signals={
            "fear_greed": 60,
            "fear_greed_zone": "greed",
            "vix_regime": "elevated",
            "rsi14": 64.0,
            "high_yield_spread": 1.45,
            "pct_vs_50dma": -2.0,
        }
    )
    line = _signal_labels(s)
    assert "signals:" in line
    assert not re.search(r"\d+\.\d+", line)
    assert "F&G greed" in line
    assert "VIX elevated" in line
    assert "RSI neutral" in line
    assert "credit wide" in line
    assert "vs50d below" in line
    assert "_" not in line.split("signals:")[1]


def test_format_day_omits_spx_close():
    s = _state(spx_close=7440.0)
    block = _format_day(s)
    assert "close " not in block.lower()
    assert "7440" not in block


def test_red_line_omissions():
    s = _state(
        spx_close=7151.25,
        narrative_summary="Monte Carlo prob_up 0.72 with Fibonacci 7,151 target and ERP 4.2% risk premium.",
        base_case="bullish_but_extended",
        trend_regime="late_cycle_melt_up",
        monte_carlo={
            **SAMPLE_STATE["monte_carlo"],
            "prob_up_first_raw": 0.72,
            "upside_target": 7500.0,
            "downside_target": 7151.0,
        },
    )
    summary = build_recent_summary([s])
    blocklist = [
        "7151",
        "7,151",
        "prob_up",
        "0.72",
        "4.2%",
        "Monte Carlo prob_up",
        "Fibonacci",
        "late_cycle_melt_up",
        "bullish_but_extended",
        "Trend bullish but extended",
    ]
    for token in blocklist:
        assert token not in summary


def test_bucket_vix_elevated_before_high():
    assert _bucket_vix(SignalSet(vix_regime="highly elevated")) == "elevated"
    assert _bucket_vix(SignalSet(vix_regime="elevated")) == "elevated"
    assert _bucket_vix(SignalSet(vix_regime="high")) == "high"


def test_bucket_fear_greed_extreme_zones():
    assert _bucket_fear_greed(SignalSet(fear_greed_zone="extreme_greed")) == "extreme_greed"
    assert _bucket_fear_greed(SignalSet(fear_greed_zone="Extreme Greed")) == "extreme_greed"
    assert _bucket_fear_greed(SignalSet(fear_greed_zone="extreme_fear")) == "extreme_fear"
    assert _bucket_fear_greed(SignalSet(fear_greed_zone="Extreme Fear")) == "extreme_fear"
    assert _bucket_fear_greed(SignalSet(fear_greed_zone="greed")) == "greed"


def test_signal_labels_extreme_greed_zone():
    s = _state(signals={"fear_greed_zone": "extreme_greed", "fear_greed": 80})
    line = _signal_labels(s)
    assert "F&G extreme greed" in line
    assert "extreme_greed" not in line
    assert "F&G greed" not in line


def test_action_normalization_table():
    assert _normalize_action("hold_schk_monitor") == "hold and monitor"
    assert _normalize_action("deploy tranche on dip") == "deploy"
    assert _normalize_action("partial 25% add") == "light deploy"
    assert _normalize_action("partial trim") == "trim bias"
    assert _normalize_action("light deploy") == "light deploy"
    assert _normalize_action("add tranche") == "deploy"
    assert _normalize_action("wave 1 trim") == "trim bias"
    assert _normalize_action("defensive patience") == "defensive patience"
    assert _normalize_action("unknown gibberish") == "hold and monitor"


def test_changed_tension_conflict_selection_full_text():
    long_item = "x" * 100
    long_tension = "t" * 200
    long_rule = "r" * 200
    s = _state(
        what_changed_today=[long_item, long_item, long_item, "fourth dropped"],
        primary_tension=long_tension,
        conflicting_evidence=[
            {
                "id": "DIV-1",
                "layers": ["technical", "structural"],
                "bullish_read": "b",
                "bearish_read": "s",
                "framework_rule": long_rule,
                "weight": "high",
                "chart_refs": [],
            },
            {
                "id": "DIV-2",
                "layers": ["sentiment"],
                "bullish_read": "b",
                "bearish_read": "s",
                "framework_rule": "second conflict",
                "weight": "medium",
                "chart_refs": [],
            },
            {
                "id": "DIV-3",
                "layers": ["valuation"],
                "bullish_read": "b",
                "bearish_read": "s",
                "framework_rule": "third dropped",
                "weight": "low",
                "chart_refs": [],
            },
        ],
    )
    block = _format_day(s)
    changed_line = [ln for ln in block.splitlines() if ln.startswith("changed:")][0]
    parts = changed_line.replace("changed: ", "").split("; ")
    assert len(parts) == 3
    assert all(len(p) == 100 for p in parts)
    assert "fourth dropped" not in changed_line
    tension_line = [ln for ln in block.splitlines() if ln.startswith("tension:")][0]
    assert tension_line == f"tension: {long_tension}"
    conflict_line = [ln for ln in block.splitlines() if ln.startswith("conflicts:")][0]
    assert "DIV-1" in conflict_line
    assert long_rule in conflict_line
    assert "DIV-2" in conflict_line
    assert "DIV-3" not in conflict_line
    assert "…" not in block


def test_regime_arc_held():
    states = [
        _state(date="2026-06-10", structural_bias="Late Bull / Topping"),
        _state(date="2026-06-11", structural_bias="Late Bull / Topping"),
    ]
    assert "(held)" in _regime_arc(states)


def test_regime_arc_transition():
    states = [
        _state(date="2026-06-11", structural_bias="Late Bull / Topping"),
        _state(date="2026-06-10", structural_bias="Mid Bull"),
    ]
    arc = _regime_arc(states)
    assert "Mid Bull → Late Bull / Topping" in arc


def test_watchlist_recency_and_exact_wording():
    states = [
        _state(date="2026-06-12", open_questions=["Will junk spread widen?"]),
        _state(
            date="2026-06-11",
            open_questions=[
                "Will junk spread widen?",
                "Does VIX spike into the 25-30 capitulation zone and reverse?",
            ],
        ),
        _state(
            date="2026-06-10",
            open_questions=["Does VIX spike into the 25-30 capitulation zone and reverse?"],
        ),
    ]
    footer = _build_unresolved_watchlist(states)
    assert footer.index("Will junk spread widen?") < footer.index("Does VIX spike")


def test_watchlist_two_of_three_repeat():
    states = [
        _state(date="2026-06-12", open_questions=[]),
        _state(date="2026-06-11", open_questions=["Repeat question here?"]),
        _state(date="2026-06-10", open_questions=["Repeat question here?"]),
    ]
    footer = _build_unresolved_watchlist(states)
    assert "Repeat question here?" in footer


def test_watchlist_two_session_expiry():
    states = [
        _state(date="2026-06-12", open_questions=[]),
        _state(date="2026-06-11", open_questions=[]),
        _state(date="2026-06-10", open_questions=["Stale question only in old session?"]),
        _state(date="2026-06-09", open_questions=["Stale question only in old session?"]),
    ]
    footer = _build_unresolved_watchlist(states)
    assert "Stale question" not in footer


def test_watchlist_full_question_text():
    long_q = "Q" * 120
    states = [_state(date="2026-06-12", open_questions=[long_q, long_q + "2"])]
    footer = _build_unresolved_watchlist(states)
    assert long_q in footer
    assert "…" not in footer


def test_six_day_rollup_under_typical_ceiling():
    dates = ["2026-06-05", "2026-06-06", "2026-06-07", "2026-06-08", "2026-06-09", "2026-06-10"]
    states = [_state(date=d, open_questions=[f"Question {i}?"]) for i, d in enumerate(dates)]
    summary = build_recent_summary(states)
    # PR-3.2 Option B: no char truncation; typical 6-day synthetic rollup stays well below ~10k chars.
    assert len(summary) <= 10_000


def test_six_day_rollup_under_stress_ceiling():
    states = []
    for i, date in enumerate(["2026-06-05", "2026-06-06", "2026-06-07", "2026-06-08", "2026-06-09", "2026-06-10"]):
        states.append(
            _state(
                date=date,
                what_changed_today=[f"change {i} " + "x" * 50],
                primary_tension="tension " + "y" * 100,
                open_questions=[f"Question {i}?"],
            )
        )
    summary = build_recent_summary(states)
    assert len(summary) <= 12_000


def test_rebuild_rolling_summary_writes_files(settings):
    write_state(settings, "2026-06-11")
    summary, path = rebuild_rolling_summary(days=5, settings=settings)
    assert path.exists()
    assert "### 2026-06-11" in summary
    assert "signals:" in summary
    assert "Primary tension:" not in summary
    assert (settings.rolling_dir / "recent_memory.json").exists()
