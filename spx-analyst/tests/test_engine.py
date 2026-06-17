"""End-to-end engine test with mocked Anthropic client and precompute."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.analysis_engine import run_daily_analysis
from src.anthropic_client import CallResult

from tests.conftest import SAMPLE_STATE, build_run_dir, write_state
from tests.sample_analysis_context import sample_analysis_context
from tests.test_validation import GOOD_REPORT


class FakeClient:
    def __init__(self, state: dict):
        self._state = state
        self.state_bodies: list[str] = []
        self.report_bodies: list[str] = []

    def run_structured_state(self, bundle, image_paths) -> CallResult:
        self.state_bodies.append(bundle.body)
        return CallResult(
            text=None,
            tool_input=self._state,
            raw_response={"ok": True},
            request_snapshot={
                "analysis_context_included": "Precomputed analysis context" in bundle.body,
                "body_chars": len(bundle.body),
            },
        )

    def repair_structured_state(self, invalid, errors) -> CallResult:  # pragma: no cover
        return CallResult(text=None, tool_input=self._state, raw_response={}, request_snapshot={})

    def run_markdown_report(self, bundle, image_paths) -> CallResult:
        self.report_bodies.append(bundle.body)
        return CallResult(
            text=GOOD_REPORT,
            tool_input=None,
            raw_response={"ok": True},
            request_snapshot={
                "analysis_context_included": "Precomputed analysis context" in bundle.body,
                "body_chars": len(bundle.body),
            },
        )


@patch("src.analysis_engine.run_precompute")
def test_full_run_writes_artifacts(mock_precompute, tmp_path, settings):
    date = "2026-06-12"
    run_dir = build_run_dir(tmp_path, date=date, n=3)
    ac = sample_analysis_context(date)
    mock_precompute.return_value = ac

    settings.include_memory = True
    write_state(settings, "2026-06-11")

    state = dict(SAMPLE_STATE)
    state["date"] = date
    state["spx_close"] = 1.0
    state["monte_carlo"] = {
        **state["monte_carlo"],
        "prob_up_first_raw": 0.99,
        "prob_up_first_adjusted": 0.99,
    }

    client = FakeClient(state)
    result = run_daily_analysis(
        date, str(run_dir), settings=settings, client=client
    )

    assert result.state_validation.passed
    assert result.report_validation.passed
    assert (result.output_dir / f"{date}-analysis.md").exists()
    assert (result.output_dir / f"{date}-state.json").exists()
    assert (result.output_dir / "analysis_context.json").exists()
    assert (settings.daily_states_dir / f"{date}-state.json").exists()
    assert (settings.rolling_dir / "recent_summary.md").exists()
    mock_precompute.assert_called_once()

    assert result.daily_state.spx_close == ac.market_data.spx_close
    assert result.daily_state.monte_carlo.prob_up_first_raw == ac.monte_carlo.prob_up_first_raw

    assert client.state_bodies
    assert "Precomputed analysis context" in client.state_bodies[0]
    assert "Do not recalculate" in client.state_bodies[0]
    assert client.report_bodies
    assert "do not recompute" in client.report_bodies[0].lower()


@patch("src.analysis_engine.run_precompute")
def test_prompt_snapshots_flag_analysis_context(mock_precompute, tmp_path, settings):
    date = "2026-06-12"
    run_dir = build_run_dir(tmp_path, date=date, n=1)
    mock_precompute.return_value = sample_analysis_context(date)
    state = dict(SAMPLE_STATE)
    state["date"] = date
    client = FakeClient(state)
    run_daily_analysis(date, str(run_dir), settings=settings, client=client)
    # FakeClient snapshots mirror anthropic_client._snapshot flag
    assert client.state_bodies[0]


class BadStateClient(FakeClient):
    def run_structured_state(self, bundle, image_paths) -> CallResult:
        return CallResult(text=None, tool_input={"date": "x"}, raw_response={}, request_snapshot={})

    def repair_structured_state(self, invalid, errors) -> CallResult:
        return CallResult(text=None, tool_input={"date": "x"}, raw_response={}, request_snapshot={})


@patch("src.analysis_engine.run_precompute")
def test_failed_run_does_not_pollute_memory(mock_precompute, tmp_path, settings):
    from src.analysis_engine import RunError

    date = "2026-06-12"
    run_dir = build_run_dir(tmp_path, date=date, n=2)
    mock_precompute.return_value = sample_analysis_context(date)

    with pytest.raises(RunError):
        run_daily_analysis(date, str(run_dir), settings=settings, client=BadStateClient({}))

    assert (settings.output_dir / date / "validation_report.json").exists()
    assert not (settings.daily_states_dir / f"{date}-state.json").exists()
