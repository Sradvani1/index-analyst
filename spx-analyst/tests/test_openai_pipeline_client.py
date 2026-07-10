"""Unit tests for OpenAIPipelineClient with mocked Responses API SDK."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image

import pytest

from src.openai_pipeline_client import OpenAIPipelineClient, OpenAIPipelineError
from src.pipeline_client import CallResult
from src.prompts import PromptBundle


def _make_settings(tmp_path):
    from src.config import Settings

    return Settings(
        anthropic_api_key="test",
        openai_api_key="test",
        openai_pipeline_model="",
        framework_path_raw=str(tmp_path),
        role_path_raw=str(tmp_path),
        data_dir_raw=str(tmp_path / "data"),
        memory_dir_raw=str(tmp_path / "memory"),
        output_dir_raw=str(tmp_path / "output"),
        eps_history_path_raw=str(tmp_path / "data" / "master" / "eps_history.json"),
    )


def _make_image(tmp_path: Path, name: str = "x.png", size: tuple[int, int] = (32, 32)) -> Path:
    p = tmp_path / name
    Image.new("RGB", size, color=(128, 128, 128)).save(p)
    return p


def _fake_state_json() -> str:
    return (
        '{"date":"x","framework_version":"v","spx_close":100.0,'
        '"structural_bias":"Mid Bull","base_case":"b","trend_regime":"b",'
        '"valuation_bucket":"c","what_changed_today":["a"],'
        '"narrative_summary":"n","open_questions":[],'
        '"confirming_evidence":[],"primary_tension":"t",'
        '"conflicting_evidence":[],"signals_pct_vs_50dma":0,'
        '"mc_effective_threshold":65,"mc_meets_threshold":false,'
        '"mc_prob_up_first_raw":0.5,"mc_prob_down_first_raw":0.4,'
        '"mc_prob_up_first_adjusted":0.5,"mc_prob_down_first_adjusted":0.4,'
        '"mc_sigma":0.1,"mc_mu":0,"mc_upside_target":0,"mc_downside_target":0,'
        '"mc_rally_exhaustion_score":"Low","mc_conditional_cascade":"",'
        '"mc_median_days":"","mc_drift_path":"","mc_cash_drag_prob":0,'
        '"decision_matrix_rows":[],"trim_signals_met":0,"buy_signals_met":0,'
        '"overall":"neutral"}'
    )


def _fake_repair_json() -> str:
    return (
        '{"date":"x","framework_version":"v","spx_close":100.0,'
        '"structural_bias":"Mid Bull","base_case":"b","trend_regime":"b",'
        '"valuation_bucket":"c","signals":{},'
        '"what_changed_today":["a"],"narrative_summary":"n","open_questions":[],'
        '"decision_matrix":{"rows":[]},'
        '"signal_alignment":{"trim_signals_met":0,"buy_signals_met":0,'
        '"overall":"neutral"},"confirming_evidence":[],'
        '"conflicting_evidence":[],"primary_tension":"t",'
        '"monte_carlo":{"effective_threshold":65,"meets_threshold":false,'
        '"prob_up_first_raw":0.5,"prob_down_first_raw":0.5,'
        '"prob_up_first_adjusted":0.5,"prob_down_first_adjusted":0.5,'
        '"sigma":0.1,"mu":0,"upside_target":0,"downside_target":0,'
        '"rally_exhaustion_score":"Low","conditional_cascade":"",'
        '"median_days":"","drift_path":"","cash_drag_prob":0}}'
    )


def _fake_response(
    output_text: str,
    model: str = "gpt-5.6-sol",
    *,
    has_refusal: bool = False,
    cached_tokens: int | None = None,
) -> SimpleNamespace:
    usage_details = SimpleNamespace(cached_tokens=cached_tokens)
    usage = SimpleNamespace(
        input_tokens=100,
        output_tokens=50,
        input_tokens_details=usage_details,
    )
    if has_refusal:
        output_item = SimpleNamespace(type="refusal", refusal="content filtered")
    else:
        output_item = SimpleNamespace(type="message", content=output_text)
    resp = SimpleNamespace(
        output=[output_item],
        output_text=output_text if not has_refusal else "",
        model=model,
        usage=usage,
    )
    resp.model_dump = lambda mode="json": {
        "model": model,
        "output_text": resp.output_text,
        "usage": vars(usage),
    }
    return resp


def _bundle(body: str = "body") -> PromptBundle:
    return PromptBundle(
        system_role="# Role\nBe an analyst.",
        framework="# Framework\nDo analysis.",
        body=body,
    )


# ── Model resolution ─────────────────────────────────────────────────────────


class TestResolveModel:
    def test_uses_env_var_when_set(self, tmp_path):
        settings = _make_settings(tmp_path)
        settings.openai_pipeline_model = "gpt-5.6-terra"
        client = OpenAIPipelineClient(settings)
        assert client._model == "gpt-5.6-terra"

    def test_defaults_when_env_var_unset(self, tmp_path):
        settings = _make_settings(tmp_path)
        client = OpenAIPipelineClient(settings)
        assert client._model == "gpt-5.6-sol"


# ── Pass 1: structured state ─────────────────────────────────────────────────


class TestRunStructuredState:
    def test_returns_call_result_with_parsed_json(self, tmp_path):
        settings = _make_settings(tmp_path)
        client = OpenAIPipelineClient(settings)
        bundle = _bundle()
        img = _make_image(tmp_path)
        state_json = (
            '{"date":"2026-07-09","framework_version":"daily-2026-06",'
            '"spx_close":5500.0,"structural_bias":"Mid Bull",'
            '"base_case":"bullish","trend_regime":"bullish",'
            '"valuation_bucket":"cautious",'
            '"what_changed_today":["Up on volume"],'
            '"narrative_summary":"Bullish.","open_questions":[],'
            '"confirming_evidence":["Trend up"],'
            '"primary_tension":"Valuation","conflicting_evidence":[],'
            '"signals_pct_vs_50dma":1.5,"signals_rsi14":60,'
            '"mc_effective_threshold":65,"mc_meets_threshold":false,'
            '"mc_prob_up_first_raw":0.6,"mc_prob_down_first_raw":0.4,'
            '"mc_prob_up_first_adjusted":0.55,'
            '"mc_prob_down_first_adjusted":0.45,'
            '"mc_sigma":0.18,"mc_mu":0.07,"mc_upside_target":5600,'
            '"mc_downside_target":5400,'
            '"mc_rally_exhaustion_score":"Low",'
            '"mc_conditional_cascade":"none","mc_median_days":"15",'
            '"mc_drift_path":"up","mc_cash_drag_prob":0.3,'
            '"decision_matrix_rows":['
            '{"signal_layer":"Structural Bias","current_reading":"Mid Bull",'
            '"signal":"bullish"},'
            '{"signal_layer":"Recommended Action","current_reading":"hold",'
            '"signal":"hold"}],"trim_signals_met":1,"buy_signals_met":0,'
            '"overall":"mixed"}'
        )

        with patch.object(client, "_create", return_value=_fake_response(state_json)):
            result = client.run_structured_state(bundle, [img])

        assert isinstance(result, CallResult)
        assert result.text is None
        assert result.tool_input["date"] == "2026-07-09"
        assert result.tool_input["structural_bias"] == "Mid Bull"
        assert result.raw_response["model"] == "gpt-5.6-sol"
        assert result.request_snapshot["mode"] == "state"
        assert result.request_snapshot["telemetry"]["provider"] == "openai"
        assert result.request_snapshot["telemetry"]["pass_name"] == "state"
        assert result.request_snapshot["telemetry"]["image_count"] == 1
        assert result.request_snapshot["telemetry"]["cache_read_tokens"] is None

    def test_telemetry_includes_cached_tokens(self, tmp_path):
        settings = _make_settings(tmp_path)
        client = OpenAIPipelineClient(settings)
        resp = _fake_response(_fake_state_json(), cached_tokens=42)

        with patch.object(client, "_create", return_value=resp):
            result = client.run_structured_state(_bundle(), [])

        assert result.request_snapshot["telemetry"]["cache_read_tokens"] == 42

    def test_raises_on_invalid_json(self, tmp_path):
        settings = _make_settings(tmp_path)
        client = OpenAIPipelineClient(settings)

        with patch.object(client, "_create", return_value=_fake_response("not json")):
            with pytest.raises(OpenAIPipelineError, match="no valid JSON"):
                client.run_structured_state(_bundle(), [])

    def test_handles_trailing_text_after_json(self, tmp_path):
        settings = _make_settings(tmp_path)
        client = OpenAIPipelineClient(settings)

        with patch.object(
            client, "_create",
            return_value=_fake_response(_fake_state_json() + "\n\nSome trailing text"),
        ):
            result = client.run_structured_state(_bundle(), [])

        assert result.tool_input["date"] == "x"

    def test_raises_on_empty_output_text(self, tmp_path):
        settings = _make_settings(tmp_path)
        client = OpenAIPipelineClient(settings)

        with patch.object(client, "_create", return_value=_fake_response("")):
            with pytest.raises(OpenAIPipelineError, match="output_text is empty"):
                client.run_structured_state(_bundle(), [])

    def test_raises_on_refusal(self, tmp_path):
        settings = _make_settings(tmp_path)
        client = OpenAIPipelineClient(settings)

        with patch.object(
            client, "_create", return_value=_fake_response("", has_refusal=True)
        ):
            with pytest.raises(OpenAIPipelineError, match="refusal"):
                client.run_structured_state(_bundle(), [])

    def test_raises_on_no_output(self, tmp_path):
        settings = _make_settings(tmp_path)
        client = OpenAIPipelineClient(settings)
        bad = _fake_response("test")
        bad.output = []

        with patch.object(client, "_create", return_value=bad):
            with pytest.raises(OpenAIPipelineError, match="no output items"):
                client.run_structured_state(_bundle(), [])

    def test_text_only_path_works(self, tmp_path):
        settings = _make_settings(tmp_path)
        client = OpenAIPipelineClient(settings)

        with patch.object(client, "_create", return_value=_fake_response(_fake_state_json())):
            result = client.run_structured_state(_bundle(), [])

        assert result.tool_input["date"] == "x"
        assert result.request_snapshot["telemetry"]["image_count"] == 0


# ── Repair pass ───────────────────────────────────────────────────────────────


class TestRepairStructuredState:
    def test_returns_fixed_state(self, tmp_path):
        settings = _make_settings(tmp_path)
        client = OpenAIPipelineClient(settings)

        with patch.object(client, "_create", return_value=_fake_response(_fake_repair_json())):
            result = client.repair_structured_state({"date": "x"}, "field required")

        assert result.tool_input["date"] == "x"
        assert result.request_snapshot["telemetry"]["pass_name"] == "repair"
        assert result.request_snapshot["telemetry"]["image_count"] == 0


# ── Pass 2: markdown report ──────────────────────────────────────────────────


class TestRunMarkdownReport:
    def test_returns_prose(self, tmp_path):
        settings = _make_settings(tmp_path)
        client = OpenAIPipelineClient(settings)
        img = _make_image(tmp_path)
        prose = "## Today's Posture\nHold."

        with patch.object(client, "_create", return_value=_fake_response(prose)):
            result = client.run_markdown_report(_bundle(), [img])

        assert result.text == prose
        assert result.tool_input is None
        assert result.request_snapshot["telemetry"]["pass_name"] == "report"

    def test_empty_image_list(self, tmp_path):
        settings = _make_settings(tmp_path)
        client = OpenAIPipelineClient(settings)

        with patch.object(
            client, "_create", return_value=_fake_response("## Today's Posture\nHold.")
        ):
            result = client.run_markdown_report(_bundle(), [])

        assert result.request_snapshot["telemetry"]["image_count"] == 0

    def test_passes_pass2_audit(self, tmp_path):
        settings = _make_settings(tmp_path)
        client = OpenAIPipelineClient(settings)

        with patch.object(
            client, "_create", return_value=_fake_response("## Today's Posture\nHold.")
        ):
            result = client.run_markdown_report(
                _bundle(), [], pass2_audit={"custom_key": "val"}
            )

        assert result.request_snapshot["custom_key"] == "val"
        assert "pass2_image_max_dimension_used" in result.request_snapshot

    def test_raises_on_refusal(self, tmp_path):
        settings = _make_settings(tmp_path)
        client = OpenAIPipelineClient(settings)

        with patch.object(
            client, "_create", return_value=_fake_response("", has_refusal=True)
        ):
            with pytest.raises(OpenAIPipelineError, match="refusal"):
                client.run_markdown_report(_bundle(), [])

    def test_raises_on_blank_output(self, tmp_path):
        settings = _make_settings(tmp_path)
        client = OpenAIPipelineClient(settings)

        with patch.object(client, "_create", return_value=_fake_response("")):
            with pytest.raises(OpenAIPipelineError, match="output_text is empty"):
                client.run_markdown_report(_bundle(), [])


# ── Retry behavior ───────────────────────────────────────────────────────────


def _make_openai_rate_limit():
    import httpx, openai
    req = httpx.Request("POST", "https://api.openai.com/v1/responses")
    resp = httpx.Response(429, request=req)
    return openai.RateLimitError("rate limited", response=resp, body=None)


def _make_openai_apiconnection_error():
    import httpx, openai
    req = httpx.Request("POST", "https://api.openai.com/v1/responses")
    return openai.APIConnectionError(message="connection failed", request=req)


def _make_openai_internal_server_error():
    import httpx, openai
    req = httpx.Request("POST", "https://api.openai.com/v1/responses")
    resp = httpx.Response(500, request=req)
    return openai.InternalServerError("internal error", response=resp, body=None)


class TestRetryBehavior:

    def _assert_retry_count(self, tmp_path, error_maker, expected_attempts):
        settings = _make_settings(tmp_path)
        client = OpenAIPipelineClient(settings)

        call_count = 0

        def side_effect(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < expected_attempts:
                raise error_maker()
            return _fake_response(_fake_state_json())

        with patch.object(client._client.responses, "create", side_effect=side_effect):
            client.run_structured_state(_bundle(), [])
        return call_count

    def test_rate_limit_retries(self, tmp_path):
        count = self._assert_retry_count(tmp_path, _make_openai_rate_limit, 2)
        assert count == 2

    def test_apiconnection_error_retries(self, tmp_path):
        count = self._assert_retry_count(tmp_path, _make_openai_apiconnection_error, 2)
        assert count == 2

    def test_internal_server_error_does_not_retry(self, tmp_path):
        import openai
        with pytest.raises(openai.InternalServerError):
            self._assert_retry_count(tmp_path, _make_openai_internal_server_error, 2)


# ── store=False contract ─────────────────────────────────────────────────────


class TestStoreFalse:

    def _assert_store_false(self, tmp_path, method_call, **kwargs):
        settings = _make_settings(tmp_path)
        client = OpenAIPipelineClient(settings)

        captured: dict | None = None

        def capture(**kw):
            nonlocal captured
            captured = kw
            return _fake_response(_fake_state_json())

        with patch.object(client._client.responses, "create", side_effect=capture):
            method_call(client, **kwargs)

        assert captured is not None
        assert captured.get("store") is False

    def test_run_structured_state_passes_store_false(self, tmp_path):
        def call(client):
            client.run_structured_state(_bundle(), [])
        self._assert_store_false(tmp_path, call)

    def test_repair_passes_store_false(self, tmp_path):
        def call(client):
            client.repair_structured_state({}, "test error")
        self._assert_store_false(tmp_path, call)

    def test_run_markdown_report_passes_store_false(self, tmp_path):
        def call(client):
            client.run_markdown_report(_bundle(), [])
        self._assert_store_false(tmp_path, call)


# ── Constructor validation ───────────────────────────────────────────────────


class TestMissingApiKey:
    def test_raises_on_empty_key(self, tmp_path):
        settings = _make_settings(tmp_path)
        settings.openai_api_key = ""
        with pytest.raises(OpenAIPipelineError, match="OPENAI_API_KEY"):
            OpenAIPipelineClient(settings)
