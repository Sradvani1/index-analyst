"""Provider resolution tests — factory, injection contract, run_log fields."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from src.analysis_engine import (
    RunError,
    _pipeline_model,
    _resolve_pipeline_client,
    run_daily_analysis,
)
from src.anthropic_client import AnthropicClient
from src.pipeline_client import CallResult, PassTelemetry, PipelineLLMClient

from tests.conftest import SAMPLE_STATE, build_run_dir, make_settings
from tests.fixtures.investor_report import PASS2_PROSE


def test_default_resolves_google(tmp_path):
    from src.google_pipeline_client import GooglePipelineClient

    settings = make_settings(tmp_path)
    with patch.object(GooglePipelineClient, "_build_client", return_value=object()):
        client = _resolve_pipeline_client(settings)
    assert isinstance(client, GooglePipelineClient)


@pytest.mark.parametrize("value", ["anthropic", "ANTHROPIC", "Anthropic"])
def test_case_insensitive_resolution(tmp_path, value):
    settings = make_settings(tmp_path)
    settings.llm_provider = value
    client = _resolve_pipeline_client(settings)
    assert isinstance(client, AnthropicClient)


def test_resolves_openai(tmp_path):
    from src.openai_pipeline_client import OpenAIPipelineClient

    settings = make_settings(tmp_path)
    settings.openai_api_key = "test"
    settings.llm_provider = "openai"
    client = _resolve_pipeline_client(settings)
    assert isinstance(client, OpenAIPipelineClient)


def test_resolves_google(tmp_path):
    from src.google_pipeline_client import GooglePipelineClient

    settings = make_settings(tmp_path)
    settings.google_api_key = "test"
    settings.llm_provider = "google"
    with patch.object(GooglePipelineClient, "_build_client", return_value=object()):
        client = _resolve_pipeline_client(settings)
    assert isinstance(client, GooglePipelineClient)


@pytest.mark.parametrize("value", ["google", "GOOGLE", "Google"])
def test_case_insensitive_google_resolution(tmp_path, value):
    from src.google_pipeline_client import GooglePipelineClient

    settings = make_settings(tmp_path)
    settings.google_api_key = "test"
    settings.llm_provider = value
    with patch.object(GooglePipelineClient, "_build_client", return_value=object()):
        client = _resolve_pipeline_client(settings)
    assert isinstance(client, GooglePipelineClient)


@pytest.mark.parametrize(
    ("provider", "configured", "expected"),
    [
        ("anthropic", "claude-test", "claude-test"),
        ("openai", "gpt-test", "gpt-test"),
        ("openai", "", "gpt-5.6-sol"),
        ("google", "gemini-test", "gemini-test"),
        ("google", "", "gemini-3.7-flash"),
    ],
)
def test_pipeline_model_matches_selected_provider(tmp_path, provider, configured, expected):
    settings = make_settings(tmp_path)
    settings.llm_provider = provider
    if provider == "anthropic":
        settings.model = configured
    elif provider == "openai":
        settings.openai_pipeline_model = configured
    else:
        settings.google_pipeline_model = configured
    assert _pipeline_model(settings) == expected


@pytest.mark.parametrize("value", ["openai", "OPENAI", "OpenAI"])
def test_case_insensitive_openai_resolution(tmp_path, value):
    from src.openai_pipeline_client import OpenAIPipelineClient

    settings = make_settings(tmp_path)
    settings.openai_api_key = "test"
    settings.llm_provider = value
    client = _resolve_pipeline_client(settings)
    assert isinstance(client, OpenAIPipelineClient)


def test_unknown_provider_raises_actionable_error(tmp_path):
    settings = make_settings(tmp_path)
    settings.llm_provider = "grok"
    with pytest.raises(RunError, match="Unknown LLM provider"):
        _resolve_pipeline_client(settings)


class _FakePipelineClient:
    """Minimal fake matching PipelineLLMClient Protocol."""

    def run_structured_state(self, bundle, image_paths) -> CallResult:
        return CallResult(text=None, tool_input={}, raw_response={}, request_snapshot={})

    def repair_structured_state(self, invalid, errors) -> CallResult:
        return CallResult(text=None, tool_input={}, raw_response={}, request_snapshot={})

    def run_markdown_report(self, bundle, image_paths, *, pass2_audit=None) -> CallResult:
        return CallResult(text="prose", tool_input=None, raw_response={}, request_snapshot={})

    def run_substack_article(self, daily_state, report_markdown):
        raise AssertionError("injected test client should not generate Substack")


def test_fake_client_conforms_to_protocol():
    """Verify the PipelineLLMClient Protocol accepts structural subtyping."""
    client: PipelineLLMClient = _FakePipelineClient()
    assert client is not None


def test_pass_telemetry_shape():
    t = PassTelemetry(provider="anthropic", model="claude-4", pass_name="state")
    assert t.provider == "anthropic"
    assert t.model == "claude-4"
    assert t.pass_name == "state"
    assert t.input_tokens is None
    assert t.attempt_count == 1
    assert t.image_count == 0


@patch("src.analysis_engine.run_precompute")
def test_run_log_records_providers(mock_precompute, tmp_path, settings):
    """Verify configured_provider and resolved_provider appear in run_log."""
    from tests.sample_analysis_context import sample_analysis_context

    date = "2026-07-09"
    run_dir = build_run_dir(tmp_path, date=date, n=1)
    mock_precompute.return_value = sample_analysis_context(date)
    state = dict(SAMPLE_STATE)
    state["date"] = date

    class _StateFake(_FakePipelineClient):
        def run_structured_state(self, bundle, image_paths) -> CallResult:
            return CallResult(text=None, tool_input=state, raw_response={}, request_snapshot={})

        def run_markdown_report(self, bundle, image_paths, *, pass2_audit=None) -> CallResult:
            return CallResult(text=PASS2_PROSE, tool_input=None, raw_response={}, request_snapshot={})

    result = run_daily_analysis(date, str(run_dir), settings=settings, client=_StateFake())
    run_log = json.loads((result.output_dir / "run_log.json").read_text(encoding="utf-8"))
    assert run_log["configured_provider"] == "google"
    assert run_log["resolved_provider"] == "injected"
