"""End-to-end engine test with mocked Anthropic client and precompute."""

from __future__ import annotations

import json
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
        self.state_image_paths: list[list] = []
        self.report_image_paths: list[list] = []

    def run_structured_state(self, bundle, image_paths) -> CallResult:
        self.state_bodies.append(bundle.body)
        self.state_image_paths.append(list(image_paths))
        return CallResult(
            text=None,
            tool_input=self._state,
            raw_response={"ok": True},
            request_snapshot={
                "analysis_context_included": "Precomputed analysis context" in bundle.body,
                "body_chars": len(bundle.body),
                "image_count": len(image_paths),
            },
        )

    def repair_structured_state(self, invalid, errors) -> CallResult:  # pragma: no cover
        return CallResult(text=None, tool_input=self._state, raw_response={}, request_snapshot={})

    def run_markdown_report(self, bundle, image_paths, *, pass2_audit=None) -> CallResult:
        self.report_bodies.append(bundle.body)
        self.report_image_paths.append(list(image_paths))
        return CallResult(
            text=GOOD_REPORT,
            tool_input=None,
            raw_response={"ok": True},
            request_snapshot={
                "analysis_context_included": "Precomputed analysis context" in bundle.body,
                "body_chars": len(bundle.body),
                "image_count": len(image_paths),
                **(pass2_audit or {}),
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
    assert len(client.state_image_paths[0]) == 3
    assert client.report_bodies
    assert "do not recompute" in client.report_bodies[0].lower()
    assert len(client.report_image_paths[0]) < len(client.state_image_paths[0])
    assert "Pass 2 chart pack" in client.report_bodies[0]
    assert "Today's chart pack (images attached in this order)" not in client.report_bodies[0]

    run_log = json.loads((result.output_dir / "run_log.json").read_text(encoding="utf-8"))
    assert run_log["chart_count"] == run_log["pass1_chart_count"] == 3
    assert run_log["pass2_chart_count"] == len(client.report_image_paths[0])
    assert "pass2_selection_reasons" in run_log
    assert "pass2_charts_attached" in run_log
    omitted = set(run_log["pass2_charts_omitted"])
    attached_report = {p.name for p in client.report_image_paths[0]}
    assert omitted.isdisjoint(attached_report)
    assert set(run_log["pass2_selection_reasons"]) == attached_report


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


@patch("src.analysis_engine.run_precompute")
def test_memory_block_absent_when_include_memory_false(mock_precompute, tmp_path, settings):
    date = "2026-06-12"
    run_dir = build_run_dir(tmp_path, date=date, n=1)
    mock_precompute.return_value = sample_analysis_context(date)
    settings.include_memory = False
    state = dict(SAMPLE_STATE)
    state["date"] = date
    client = FakeClient(state)
    run_daily_analysis(date, str(run_dir), settings=settings, client=client)
    assert "Prior posture snapshot" not in client.state_bodies[0]
    assert "Prior posture snapshot" not in client.report_bodies[0]


@patch("src.analysis_engine.run_precompute")
def test_rolling_rebuilt_without_include_memory(mock_precompute, tmp_path, settings):
    date = "2026-06-12"
    run_dir = build_run_dir(tmp_path, date=date, n=1)
    mock_precompute.return_value = sample_analysis_context(date)
    settings.include_memory = False
    write_state(settings, "2026-06-11")
    state = dict(SAMPLE_STATE)
    state["date"] = date
    client = FakeClient(state)
    run_daily_analysis(date, str(run_dir), settings=settings, client=client)
    rolling = settings.rolling_dir / "recent_summary.md"
    assert rolling.exists()
    text = rolling.read_text(encoding="utf-8")
    assert "###" in text
    assert date in text or "2026-06-11" in text


@patch("src.analysis_engine.run_precompute")
def test_no_warning_young_archive_zero_invalid_skips(mock_precompute, tmp_path, settings):
    date = "2026-06-12"
    run_dir = build_run_dir(tmp_path, date=date, n=1)
    mock_precompute.return_value = sample_analysis_context(date)
    settings.include_memory = True
    state = dict(SAMPLE_STATE)
    state["date"] = date
    client = FakeClient(state)
    result = run_daily_analysis(date, str(run_dir), settings=settings, client=client)
    memory_warnings = [w for w in result.warnings if "memory load skipped" in w]
    assert memory_warnings == []
    run_log = json.loads((result.output_dir / "run_log.json").read_text(encoding="utf-8"))
    assert run_log["memory_load"]["skipped_invalid"] == 0


@patch("src.analysis_engine.run_precompute")
def test_warning_when_prior_file_unreadable(mock_precompute, tmp_path, settings):
    date = "2026-06-12"
    run_dir = build_run_dir(tmp_path, date=date, n=1)
    mock_precompute.return_value = sample_analysis_context(date)
    settings.include_memory = True
    bad = settings.daily_states_dir / "2026-06-11-state.json"
    bad.parent.mkdir(parents=True, exist_ok=True)
    bad.write_text("{broken", encoding="utf-8")
    state = dict(SAMPLE_STATE)
    state["date"] = date
    client = FakeClient(state)
    result = run_daily_analysis(date, str(run_dir), settings=settings, client=client)
    assert any("memory load skipped" in w for w in result.warnings)
    run_log = json.loads((result.output_dir / "run_log.json").read_text(encoding="utf-8"))
    assert run_log["memory_load"]["skipped_invalid"] >= 1


@patch("src.analysis_engine.run_precompute")
def test_pass2_engine_subset_on_full_manifest(mock_precompute, tmp_path, settings):
    from tests.test_pass2_images import _build_full_run_dir, _state_with

    date = "2026-06-10"
    run_dir = _build_full_run_dir(tmp_path)
    mock_precompute.return_value = sample_analysis_context(date)
    settings.pass2_image_optimization_enabled = True

    state = _state_with(
        date=date,
        conflicts=[
            {
                "id": "extension_vs_credit",
                "layers": ["valuation", "credit"],
                "bullish_read": "Trend holds",
                "bearish_read": "Credit stress",
                "framework_rule": "Credit warning",
                "weight": "high",
                "chart_refs": ["03_spx_1month.png", "15_junk_bond_spread.png"],
            },
        ],
        matrix_signals={
            "Trend Regime": "neutral",
            "Credit Condition": "widening",
            "VIX Regime": "elevated",
        },
    )
    client = FakeClient(state.model_dump(mode="json"))
    result = run_daily_analysis(date, str(run_dir), settings=settings, client=client)

    assert result.report_validation.passed
    assert len(client.state_image_paths[0]) == 15
    assert len(client.report_image_paths[0]) < 15
    assert "Pass 2 chart pack" in client.report_bodies[0]

    run_log = json.loads((result.output_dir / "run_log.json").read_text(encoding="utf-8"))
    attached_report = {p.name for p in client.report_image_paths[0]}
    assert set(run_log["pass2_charts_attached"]) == attached_report
    assert set(run_log["pass2_selection_reasons"]) == attached_report
    assert set(run_log["pass2_charts_omitted"]).isdisjoint(attached_report)


@patch("src.analysis_engine.run_precompute")
def test_pass2_engine_zero_charts_completes(mock_precompute, tmp_path, settings):
    from tests.test_pass2_images import _build_full_run_dir, _state_with

    date = "2026-06-10"
    run_dir = _build_full_run_dir(tmp_path)
    mock_precompute.return_value = sample_analysis_context(date)
    settings.pass2_image_optimization_enabled = True

    state = _state_with(
        date=date,
        conflicts=[],
        matrix_signals={
            "Trend Regime": "neutral",
            "Credit Condition": "monitor",
            "VIX Regime": "stable",
        },
    )
    client = FakeClient(state.model_dump(mode="json"))
    result = run_daily_analysis(date, str(run_dir), settings=settings, client=client)

    assert result.report_validation.passed
    assert client.report_image_paths[0] == []
    assert "no chart images are attached" in client.report_bodies[0]

    run_log = json.loads((result.output_dir / "run_log.json").read_text(encoding="utf-8"))
    assert run_log["pass2_chart_count"] == 0
    assert run_log["pass2_charts_attached"] == []
    assert run_log["pass2_selection_reasons"] == {}
