"""Tests for build_arc_brief (PR-15 compressed continuity layer)."""

from __future__ import annotations

import copy

from src.memory import _build_still_open_bullets, _regime_arc, build_arc_brief
from src.chat_preload import render_arc_brief
from src.schemas import ArcBriefCaps, DailyState

from tests.conftest import SAMPLE_STATE, write_state


def _state(**overrides) -> DailyState:
    data = copy.deepcopy(SAMPLE_STATE)
    data.update(overrides)
    return DailyState.model_validate(data)


def test_build_arc_brief_deterministic_from_states():
    states = [
        _state(
            date="2026-06-10",
            structural_bias="Mid Bull",
            what_changed_today=["Recovery extended on 6/10."],
            primary_tension="First tension sentence. More detail.",
        ),
        _state(
            date="2026-06-11",
            structural_bias="Mid Bull",
            what_changed_today=["Rollover rejected at resistance."],
            primary_tension="Second tension. Extra.",
        ),
        _state(
            date="2026-06-12",
            structural_bias="Late Bull / Topping",
            what_changed_today=["Downleg reasserted onto fib."],
            primary_tension="Third tension here.",
        ),
    ]
    states = list(reversed(states))

    arc = build_arc_brief(states)

    assert arc.regime_arc == _regime_arc(states)
    assert arc.still_open_bullets == _build_still_open_bullets(states)
    assert len(arc.session_snapshots) == 3
    assert [s.date for s in arc.session_snapshots] == ["2026-06-10", "2026-06-11", "2026-06-12"]
    assert arc.session_snapshots[-1].bias == "Late Bull / Topping"
    assert arc.session_snapshots[0].tension_fragment.startswith("Recovery extended")
    assert len(arc.session_snapshots[0].tension_fragment) <= ArcBriefCaps.MAX_TENSION_FRAGMENT_CHARS


def test_arc_session_fragment_prefers_what_changed_today():
    state = _state(
        what_changed_today=["Marginal change headline for the day."],
        primary_tension="Stable skeleton tension that should not appear.",
    )
    arc = build_arc_brief([state])
    assert arc.session_snapshots[0].tension_fragment.startswith("Marginal change headline")


def test_arc_session_fragment_falls_back_to_tension_when_no_changes():
    state = _state(
        what_changed_today=[],
        primary_tension="Fallback tension sentence. Extra detail.",
    )
    arc = build_arc_brief([state])
    assert arc.session_snapshots[0].tension_fragment == "Fallback tension sentence."


def test_build_arc_brief_respects_max_sessions(settings):
    dates = [f"2026-06-{day:02d}" for day in range(10, 17)]
    for date in dates:
        write_state(settings, date)
    from src.memory import load_recent_states

    states = load_recent_states(settings=settings)
    arc = build_arc_brief(states)

    assert len(arc.session_snapshots) <= ArcBriefCaps.MAX_SESSIONS
    assert arc.session_snapshots[-1].date == states[0].date


def test_build_arc_brief_tension_fragment_capped():
    long_tension = "A" * 200 + ". Tail sentence."
    states = [_state(date="2026-06-12", what_changed_today=[], primary_tension=long_tension)]
    arc = build_arc_brief(states)
    assert len(arc.session_snapshots[0].tension_fragment) <= ArcBriefCaps.MAX_TENSION_FRAGMENT_CHARS


def test_build_arc_brief_includes_latest_session():
    states = [
        _state(date="2026-06-11"),
        _state(date="2026-06-12"),
    ]
    states = list(reversed(states))
    arc = build_arc_brief(states)
    assert any(s.date == "2026-06-12" for s in arc.session_snapshots)


def test_arc_session_fragment_title_cases_all_caps_headline():
    state = _state(
        what_changed_today=[
            "RECOVERY FAILED / ROLLOVER: After reclaiming the 23.6% fib (~7,553) on 6/15, pr"
        ],
    )
    arc = build_arc_brief([state])
    fragment = arc.session_snapshots[0].tension_fragment
    assert fragment.startswith("Recovery Failed / Rollover:")
    assert "7,553" in fragment
    assert "RECOVERY FAILED" not in fragment


def test_render_arc_brief_uses_still_open_label():
    states = [
        _state(
            date="2026-06-12",
            what_changed_today=["DOWNLEG RE-ASSERTED: close 7,365.46 retraced the advance."],
        ),
    ]
    rendered = render_arc_brief(build_arc_brief(states))
    assert "## Recent arc" in rendered
    assert "Still open:" in rendered
    assert "Unresolved watchlist:" not in rendered
    assert "Inflection points:" in rendered
    assert "Downleg Re-Asserted:" in rendered
