"""End-to-end engine test with a mocked Anthropic client (no network)."""

from __future__ import annotations

import json

from src.analysis_engine import run_daily_analysis
from src.anthropic_client import CallResult

from tests.conftest import SAMPLE_STATE, build_run_dir, write_state
from tests.test_validation import GOOD_REPORT


class FakeClient:
    def __init__(self, state: dict):
        self._state = state

    def run_structured_state(self, bundle, image_paths) -> CallResult:
        return CallResult(text=None, tool_input=self._state, raw_response={"ok": True}, request_snapshot={})

    def repair_structured_state(self, invalid, errors) -> CallResult:  # pragma: no cover
        return CallResult(text=None, tool_input=self._state, raw_response={}, request_snapshot={})

    def run_markdown_report(self, bundle, image_paths) -> CallResult:
        return CallResult(text=GOOD_REPORT, tool_input=None, raw_response={"ok": True}, request_snapshot={})


def test_full_run_writes_artifacts(tmp_path, settings):
    date = "2026-06-12"
    run_dir = build_run_dir(tmp_path, date=date, n=3)
    # User-supplied external context.
    (run_dir / "external_context.json").write_text(
        json.dumps({"date": date, "forward_eps": 300.0}), encoding="utf-8"
    )
    write_state(settings, "2026-06-11")  # prior memory

    state = dict(SAMPLE_STATE)
    state["date"] = date

    result = run_daily_analysis(
        date, str(run_dir), settings=settings, client=FakeClient(state)
    )

    assert result.state_validation.passed
    assert result.report_validation.passed
    assert (result.output_dir / f"{date}-analysis.md").exists()
    assert (result.output_dir / f"{date}-state.json").exists()
    assert (result.output_dir / "request_snapshot.json").exists()
    assert (result.output_dir / "validation_report.json").exists()
    # Canonical artifacts mirrored into memory.
    assert (settings.daily_states_dir / f"{date}-state.json").exists()
    assert (settings.daily_reports_dir / f"{date}-analysis.md").exists()
    # Rolling summary refreshed.
    assert (settings.rolling_dir / "recent_summary.md").exists()


class BadStateClient(FakeClient):
    """Always returns a schema-invalid state, even on repair."""

    def run_structured_state(self, bundle, image_paths) -> CallResult:
        return CallResult(text=None, tool_input={"date": "x"}, raw_response={}, request_snapshot={})

    def repair_structured_state(self, invalid, errors) -> CallResult:
        return CallResult(text=None, tool_input={"date": "x"}, raw_response={}, request_snapshot={})


def test_failed_run_does_not_pollute_memory(tmp_path, settings):
    import pytest

    from src.analysis_engine import RunError

    date = "2026-06-12"
    run_dir = build_run_dir(tmp_path, date=date, n=2)
    (run_dir / "external_context.json").write_text(
        json.dumps({"date": date}), encoding="utf-8"
    )

    with pytest.raises(RunError):
        run_daily_analysis(date, str(run_dir), settings=settings, client=BadStateClient({}))

    # Failure artifacts are written to output but NOT mirrored into memory.
    assert (settings.output_dir / date / "validation_report.json").exists()
    assert not (settings.daily_states_dir / f"{date}-state.json").exists()
    assert not (settings.daily_reports_dir / f"{date}-analysis.md").exists()
