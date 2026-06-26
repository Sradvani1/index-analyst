"""Tests for chat preload (Phase 1 authority + posture canary)."""

from __future__ import annotations

import pytest

from src.chat_preload import (
    answer_posture_from_preload,
    build_additional_instructions,
    build_latest_run_block,
    build_latest_run_state,
    find_latest_run_date,
    load_latest_daily_state,
    validate_report_matrix_section,
)
from src.files import InputError
from src.prompts import DECISION_MATRIX_ROWS

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


def test_latest_run_state_matrix_from_daily_state_only(sample_state, preload_settings):
    write_state(preload_settings, "2026-06-12")
    daily_state = load_latest_daily_state(preload_settings)
    latest = build_latest_run_state(daily_state)

    assert latest.latest_run_date == "2026-06-12"
    assert latest.decision_matrix.rows == daily_state.decision_matrix.rows
    assert latest.recommended_action == daily_state.decision_matrix.recommended_action
    assert latest.decision_matrix.rows[0].signal_layer == "Structural Bias"
    assert latest.decision_matrix.rows[-1].signal_layer == "Recommended Action"


def test_find_latest_run_date_uses_newest_state(preload_settings):
    write_state(preload_settings, "2026-06-10")
    write_state(preload_settings, "2026-06-12")
    assert find_latest_run_date(preload_settings) == "2026-06-12"


def test_build_latest_run_block_includes_matrix_rows(sample_state, preload_settings):
    write_state(preload_settings, "2026-06-12")
    latest = build_latest_run_state(load_latest_daily_state(preload_settings))
    block = build_latest_run_block(latest)

    assert "latest_run_date: 2026-06-12" in block
    assert "decision_matrix.rows (Updated Decision Matrix — authoritative):" in block
    for layer in DECISION_MATRIX_ROWS:
        assert layer in block
    assert "recommended_action:" in block


def test_build_additional_instructions_assembles_stack(preload_settings, sample_state):
    write_state(preload_settings, "2026-06-12")
    rolling = preload_settings.rolling_dir / "recent_summary.md"
    rolling.parent.mkdir(parents=True, exist_ok=True)
    rolling.write_text("### 2026-06-12\nMid Bull | mixed\n", encoding="utf-8")

    context = build_additional_instructions(preload_settings)

    assert "Use preload for current posture." in context.instructions
    assert context.latest_run.latest_run_date == "2026-06-12"
    assert context.rolling_summary.startswith("### 2026-06-12")
    assert "Latest-run state (authoritative for current posture)" in context.additional_instructions
    assert "Rolling summary (multi-day arc)" in context.additional_instructions


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
    """Exit gate: 'what is posture now?' from LatestRunState only — no vector retrieval."""
    write_state(preload_settings, "2026-06-12")
    context = build_additional_instructions(preload_settings)

    answer = answer_posture_from_preload(context)

    assert context.latest_run.latest_run_date in answer
    assert context.latest_run.recommended_action.replace("_", " ") in answer.replace("_", " ")
    assert str(context.latest_run.spx_close) in answer
    assert "decision_matrix.rows" not in answer  # natural-language answer, not raw dump


def test_no_daily_states_raises(preload_settings):
    with pytest.raises(InputError, match="no daily states"):
        find_latest_run_date(preload_settings)
