"""Tests for decision matrix validation."""

from src.validation import parse_daily_state

from tests.conftest import SAMPLE_STATE


def test_parse_daily_state_warns_on_wrong_row_count():
    state = dict(SAMPLE_STATE)
    rows = state["decision_matrix"]["rows"]
    state["decision_matrix"] = {"rows": rows[:10] + rows[11:]}
    parsed, report = parse_daily_state(state, "2026-06-11")
    assert parsed is not None
    assert report.passed
    assert any(i.code == "decision_matrix_row_count" for i in report.issues)


def test_parse_daily_state_errors_on_empty_matrix():
    state = dict(SAMPLE_STATE)
    state["decision_matrix"] = {"rows": []}
    parsed, report = parse_daily_state(state, "2026-06-11")
    assert parsed is not None
    assert not report.passed
    assert any(i.code == "empty_decision_matrix" for i in report.issues)
