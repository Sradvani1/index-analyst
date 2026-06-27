"""Tests for compact chat preload (PR-15 authority + budget guards)."""

from __future__ import annotations

import copy

import pytest

from src.formatting import format_price
from src.chat_preload import (
    answer_posture_from_preload,
    build_additional_instructions,
    build_current_brief,
    find_latest_run_date,
    load_instructions,
    load_latest_daily_state,
    render_arc_brief,
    render_current_brief,
    validate_report_matrix_section,
)
from src.config import get_settings
from src.files import InputError
from src.memory import build_arc_brief, build_recent_summary, load_recent_states
from src.schemas import (
    ArcBriefCaps,
    ChatPreloadBudget,
    ConstitutionCaps,
    CurrentBrief,
    CurrentBriefCaps,
    CurrentBriefRow,
    DailyState,
)

from tests.conftest import SAMPLE_STATE, make_settings, write_state
from tests.fixtures.investor_report import assembled_report_for_state


@pytest.fixture
def preload_settings(tmp_path):
    settings = make_settings(tmp_path)
    instructions = tmp_path / "framework" / "chat-assistant-instructions.md"
    instructions.write_text("# Assistant\n\nUse preload for current posture.\n", encoding="utf-8")
    settings = settings.model_copy(
        update={"chat_assistant_instructions_path_raw": str(instructions)}
    )
    return settings


def _count_tokens(text: str) -> int | None:
    try:
        import tiktoken
    except ImportError:
        return None
    enc = tiktoken.get_encoding("o200k_base")
    return len(enc.encode(text))


def _live_settings_or_skip():
    settings = get_settings()
    states_dir = settings.daily_states_dir
    if not states_dir.is_dir() or not list(states_dir.glob("*-state.json")):
        pytest.skip("live memory/daily_states not present")
    return settings


def test_find_latest_run_date_uses_newest_state(preload_settings):
    write_state(preload_settings, "2026-06-10")
    write_state(preload_settings, "2026-06-12")
    assert find_latest_run_date(preload_settings) == "2026-06-12"


def test_build_current_brief_from_daily_state(sample_state, preload_settings):
    write_state(preload_settings, "2026-06-12")
    daily_state = load_latest_daily_state(preload_settings)
    brief = build_current_brief(daily_state)

    assert brief.latest_run_date == "2026-06-12"
    assert brief.spx_close == daily_state.spx_close
    assert brief.structural_bias == daily_state.structural_bias
    assert len(brief.authoritative_rows) == CurrentBriefCaps.MAX_MATRIX_ROWS
    assert brief.authoritative_rows[0].signal_layer == "Structural Bias"
    assert brief.authoritative_rows[4].signal_layer == "Leverage Risk State"
    assert brief.authoritative_rows[5].signal_layer == "Monte Carlo Edge"
    assert len(brief.key_risks_or_tensions) <= CurrentBriefCaps.MAX_RISK_BULLETS


def test_render_current_brief_has_table_not_json(sample_state, preload_settings):
    write_state(preload_settings, "2026-06-12")
    brief = build_current_brief(load_latest_daily_state(preload_settings))
    rendered = render_current_brief(brief)

    assert "As of 2026-06-12" in rendered
    assert "(SPX close" in rendered
    assert "## Current house view" in rendered
    assert "What shifted:" in rendered
    assert "Setup / tension:" in rendered
    assert "Triggers to watch:" in rendered
    assert "What changes the view:" in rendered
    assert "| Signal Layer | Signal |" in rendered
    assert "decision_matrix.rows (JSON)" not in rendered
    assert "what_changed_today:" not in rendered
    assert len(rendered) <= CurrentBriefCaps.MAX_RENDERED_CHARS


def test_build_additional_instructions_three_layer_stack(preload_settings, sample_state):
    write_state(preload_settings, "2026-06-12")
    write_state(preload_settings, "2026-06-11")
    write_state(preload_settings, "2026-06-10")

    context = build_additional_instructions(preload_settings)

    assert "Use preload for current posture." in context.instructions
    assert context.current_brief.latest_run_date == "2026-06-12"
    assert context.arc_brief.regime_arc
    assert "## Current house view" in context.additional_instructions
    assert "## Recent arc" in context.additional_instructions
    assert "Latest-run state (authoritative for current posture)" not in context.additional_instructions
    assert "Rolling summary (multi-day arc)" not in context.additional_instructions
    assert "decision_matrix.rows (JSON)" not in context.additional_instructions
    assert "changed:" not in context.additional_instructions
    assert "signals: F&G" not in context.additional_instructions


def test_validate_report_matrix_section_warns_when_report_missing(preload_settings, sample_state):
    write_state(preload_settings, "2026-06-12")
    daily_state = load_latest_daily_state(preload_settings)
    warnings = validate_report_matrix_section("2026-06-12", daily_state, preload_settings)
    assert any("same-date report missing" in w for w in warnings)


def test_validate_report_matrix_section_ok_with_assembled_report(preload_settings, sample_state):
    write_state(preload_settings, "2026-06-12")
    daily_state = load_latest_daily_state(preload_settings)
    report = assembled_report_for_state(daily_state, date="2026-06-12")
    report_path = preload_settings.daily_reports_dir / "2026-06-12-analysis.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")

    warnings = validate_report_matrix_section("2026-06-12", daily_state, preload_settings)
    assert warnings == []


def test_posture_canary_answerable_without_retrieval(preload_settings, sample_state):
    """Exit gate: 'what is posture now?' from current_brief only — no vector retrieval."""
    write_state(preload_settings, "2026-06-12")
    context = build_additional_instructions(preload_settings)

    answer = answer_posture_from_preload(context)

    assert context.current_brief.latest_run_date in answer
    assert context.current_brief.recommended_action.replace("_", " ") in answer.replace("_", " ")
    assert format_price(context.current_brief.spx_close) in answer
    assert "decision_matrix.rows" not in answer


def test_no_daily_states_raises(preload_settings):
    with pytest.raises(InputError, match="no daily states"):
        find_latest_run_date(preload_settings)


def test_arc_brief_shorter_than_recent_summary(preload_settings, sample_state):
    for date in ["2026-06-10", "2026-06-11", "2026-06-12"]:
        write_state(preload_settings, date)
    states = load_recent_states(settings=preload_settings)
    arc = build_arc_brief(states)
    arc_rendered = render_arc_brief(arc)
    full_summary = build_recent_summary(states)
    assert len(arc_rendered) < len(full_summary) * 0.5


def test_live_memory_budget_caps():
    settings = _live_settings_or_skip()
    context = build_additional_instructions(settings)
    rendered_current = render_current_brief(context.current_brief)
    rendered_arc = render_arc_brief(context.arc_brief)

    assert len(context.instructions) <= ConstitutionCaps.MAX_RENDERED_CHARS
    assert len(rendered_current) <= CurrentBriefCaps.MAX_RENDERED_CHARS
    assert len(rendered_arc) <= ArcBriefCaps.MAX_RENDERED_CHARS
    assert len(context.additional_instructions) <= ChatPreloadBudget.MAX_ADDITIONAL_INSTRUCTIONS_CHARS

    tokens = _count_tokens(context.additional_instructions)
    # Per-layer token figures are approx targets (doc-table only); char caps are enforced.
    if tokens is not None:
        assert tokens <= ChatPreloadBudget.MAX_ADDITIONAL_INSTRUCTIONS_TOKENS

    assert "decision_matrix.rows (JSON)" not in context.additional_instructions
    assert "what_changed_today:" not in context.additional_instructions
    assert "changed:" not in context.additional_instructions
    assert "signals: F&G" not in context.additional_instructions
    assert "conflicts:" not in context.additional_instructions


def _state(**overrides) -> DailyState:
    data = copy.deepcopy(SAMPLE_STATE)
    data.update(overrides)
    return DailyState.model_validate(data)


def _matrix_with_row(layer: str, *, signal: str, current_reading: str = "n/a") -> list[dict]:
    rows = copy.deepcopy(SAMPLE_STATE["decision_matrix"]["rows"])
    for row in rows:
        if row["signal_layer"] == layer:
            row["signal"] = signal
            row["current_reading"] = current_reading
            return rows
    raise KeyError(layer)


def test_leverage_and_mc_edge_matrix_rows(sample_state):
    state = _state(
        decision_matrix={
            "rows": _matrix_with_row(
                "Leverage Risk State",
                signal="Caution zone active",
                current_reading="Price on liquidation zone",
            )
        }
    )
    rows = build_current_brief(state).authoritative_rows
    assert rows[4].signal_layer == "Leverage Risk State"
    assert rows[5].signal_layer == "Monte Carlo Edge"


def test_leverage_row_uses_signal_not_current_reading_for_display(sample_state):
    state = _state(
        decision_matrix={
            "rows": _matrix_with_row(
                "Leverage Risk State",
                signal="neutral",
                current_reading="Price on the caution liquidation zone",
            )
        }
    )
    leverage_row = build_current_brief(state).authoritative_rows[4]
    assert leverage_row.signal_layer == "Leverage Risk State"
    assert leverage_row.signal == "neutral"


def test_trend_regime_row_uses_state_field_not_matrix_signal(sample_state):
    state = _state(
        trend_regime="from-state-trend-regime-field",
        decision_matrix={
            "rows": _matrix_with_row(
                "Trend Regime",
                signal="from-matrix-signal",
                current_reading="from-matrix-reading",
            )
        },
    )
    trend_row = next(
        row
        for row in build_current_brief(state).authoritative_rows
        if row.signal_layer == "Trend Regime"
    )
    assert trend_row.signal == "from-state-trend-regime-field"
    assert trend_row.signal != "from-matrix-signal"


def test_load_instructions_truncates_constitution(preload_settings):
    long_text = "x" * 2500
    path = preload_settings.chat_assistant_instructions_path
    path.write_text(long_text, encoding="utf-8")
    loaded = load_instructions(preload_settings)
    assert len(loaded) == ConstitutionCaps.MAX_RENDERED_CHARS
    assert loaded.endswith("…")


def test_render_current_brief_truncates_when_over_cap():
    long_signal = "S" * 500
    brief = CurrentBrief(
        latest_run_date="2026-06-12",
        spx_close=7440.0,
        structural_bias="Mid Bull",
        recommended_action="hold and monitor",
        overall_signal_balance="mixed",
        opening_house_view="As of 2026-06-12 (SPX close 7,440.00): Mid Bull — hold and monitor.",
        setup_tension="Setup tension sentence.",
        key_risks_or_tensions=[long_signal],
        key_trigger_levels=[long_signal],
        view_change_bullets=[long_signal],
        authoritative_rows=[
            CurrentBriefRow(signal_layer="Structural Bias", signal=long_signal),
            CurrentBriefRow(signal_layer="Overall Signal Balance", signal=long_signal),
            CurrentBriefRow(signal_layer="Trend Regime", signal=long_signal),
            CurrentBriefRow(signal_layer="Recommended Action", signal=long_signal),
            CurrentBriefRow(signal_layer="Monte Carlo Edge", signal=long_signal),
        ],
    )
    rendered = render_current_brief(brief)
    assert len(rendered) == CurrentBriefCaps.MAX_RENDERED_CHARS
    assert rendered.endswith("…")


def test_render_current_brief_formats_prices(preload_settings, sample_state):
    write_state(preload_settings, "2026-06-12")
    daily = load_latest_daily_state(preload_settings)
    brief = build_current_brief(daily)
    rendered = render_current_brief(brief)

    assert f"As of 2026-06-12 (SPX close {format_price(daily.spx_close)})" in rendered
    assert f"MC upside: {format_price(daily.monte_carlo.upside_target)}" in rendered
    assert f"MC downside: {format_price(daily.monte_carlo.downside_target)}" in rendered
    assert f"{daily.spx_close}" not in rendered


def test_risk_bullets_use_marginal_change_and_no_conflict_ids(sample_state):
    state = _state(
        what_changed_today=["Sentiment deteriorated to deeper fear."],
        conflicting_evidence=[
            {
                "id": "erp_ceiling_vs_forward_pe",
                "layers": ["valuation"],
                "bullish_read": "x",
                "bearish_read": "y",
                "framework_rule": "ERP 0.0-0.5% = valuation ceiling, trim bias.",
                "weight": "high",
                "chart_refs": [],
            }
        ],
    )
    brief = build_current_brief(state)
    assert brief.key_risks_or_tensions[0].startswith("Sentiment deteriorated")
    assert "erp_ceiling_vs_forward_pe:" not in " ".join(brief.key_risks_or_tensions)
    assert brief.key_risks_or_tensions[1] == "ERP 0.0-0.5% = valuation ceiling, trim bias."


def test_risk_bullets_title_case_all_caps_marginal_change(sample_state):
    state = _state(
        what_changed_today=[
            "DOWNSIDE TARGET TAGGED: close 7,357.49 fully retraced the active leg and breached the 50% fib (7,408)"
        ],
    )
    brief = build_current_brief(state)
    assert brief.key_risks_or_tensions[0].startswith("Downside Target Tagged:")
    assert "7,357.49" in brief.key_risks_or_tensions[0]
    assert "DOWNSIDE TARGET TAGGED" not in brief.key_risks_or_tensions[0]


def test_real_constitution_fits_cap_without_truncation():
    loaded = load_instructions(get_settings())
    assert len(loaded) <= ConstitutionCaps.MAX_RENDERED_CHARS
    assert not loaded.endswith("…")
    assert "Authority stack" in loaded
    assert "house analyst" in loaded.lower()


def test_format_event_headline_title_cases_all_caps_label():
    from src.formatting import format_event_headline

    original = (
        "DOWNSIDE TARGET TAGGED: close 7,357.49 fully retraced the active leg "
        "and breached the 50% fib (7,408)"
    )
    result = format_event_headline(original)
    assert result.startswith("Downside Target Tagged:")
    assert "7,357.49" in result
    assert "7,408" in result
    assert "DOWNSIDE TARGET TAGGED" not in result


def test_format_event_headline_passes_through_sentence_case():
    from src.formatting import format_event_headline

    text = "Sentiment deteriorated to deeper fear."
    assert format_event_headline(text) == text


def test_format_event_headline_preserves_body_acronyms_and_prices():
    from src.formatting import format_event_headline

    original = "RECOVERY FAILED / ROLLOVER: After reclaiming the 23.6% fib (~7,553) on 6/15, pr"
    result = format_event_headline(original)
    assert result.startswith("Recovery Failed / Rollover:")
    assert "7,553" in result
    assert "6/15" in result
