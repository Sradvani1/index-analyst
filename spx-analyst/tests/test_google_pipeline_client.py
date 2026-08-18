"""Unit tests for GooglePipelineClient with a mocked Gemini SDK client."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from PIL import Image
import pytest

from src.google_pipeline_client import (
    GooglePipelineClient,
    GooglePipelineError,
    _is_transient_error,
)
from src.prompts import PromptBundle
from src.schemas import DailyState, SUBSTACK_SECTIONS


class _FakePart:
    @classmethod
    def from_bytes(cls, *, data: bytes, mime_type: str):
        return {"inline_data": {"data": data, "mime_type": mime_type}}

    @classmethod
    def from_text(cls, *, text: str):
        return {"text": text}


class _FakeTypes:
    Part = _FakePart

    class ThinkingConfig:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class Content:
        def __init__(self, *, role: str, parts: list[object]):
            self.role = role
            self.parts = parts

    class GenerateContentConfig:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)


class _StatusError(Exception):
    def __init__(self, status_code: int):
        super().__init__(str(status_code))
        self.status_code = status_code


class _UnavailableResponse:
    usage_metadata = None
    candidates: list[object] = []

    @property
    def text(self):
        raise ValueError("blocked")


def _settings(tmp_path):
    from src.config import Settings

    return Settings(
        google_api_key="test",
        google_pipeline_model="gemini-3.7-flash",
        framework_path_raw=str(tmp_path),
        role_path_raw=str(tmp_path),
        data_dir_raw=str(tmp_path / "data"),
        memory_dir_raw=str(tmp_path / "memory"),
        output_dir_raw=str(tmp_path / "output"),
        eps_history_path_raw=str(tmp_path / "data" / "master" / "eps_history.json"),
    )


def _bundle() -> PromptBundle:
    return PromptBundle(
        system_role="# Role\nBe an analyst.",
        framework="# Framework\nDo analysis.",
        body="Analyze today's charts.",
    )


def _response(text: str, *, cached: int | None = None):
    response = SimpleNamespace(
        text=text,
        usage_metadata=SimpleNamespace(
            prompt_token_count=100,
            candidates_token_count=50,
            thoughts_token_count=10,
            cached_content_token_count=cached,
        ),
    )
    response.model_dump = lambda mode="json": {
        "text": text,
        "usage_metadata": {"prompt_token_count": 100},
    }
    return response


def _client(tmp_path, response):
    sdk_client = Mock()
    sdk_client.models.generate_content.return_value = response
    return GooglePipelineClient(
        _settings(tmp_path), client=sdk_client, types_module=_FakeTypes
    ), sdk_client


def test_structured_state_uses_gemini_json_schema(tmp_path):
    client, sdk_client = _client(tmp_path, _response('{"date":"2026-08-13"}'))

    result = client.run_structured_state(_bundle(), [])

    assert result.tool_input == {"date": "2026-08-13"}
    assert result.request_snapshot["telemetry"]["provider"] == "google"
    assert result.request_snapshot["telemetry"]["output_tokens"] == 60
    request = sdk_client.models.generate_content.call_args.kwargs
    assert request["model"] == "gemini-3.7-flash"
    assert request["config"].max_output_tokens == 16000
    assert request["config"].response_mime_type == "application/json"
    assert (
        request["config"].response_json_schema["properties"]["mc_effective_threshold"]
        ["enum"]
        == [65, 70, 75]
    )


def test_thinking_level_is_applied_to_structured_and_report_calls(tmp_path):
    settings = _settings(tmp_path)
    settings.google_thinking_level = "high"
    sdk_client = Mock()
    sdk_client.models.generate_content.side_effect = [
        _response('{"date":"2026-08-13"}'),
        _response("report"),
    ]
    client = GooglePipelineClient(
        settings, client=sdk_client, types_module=_FakeTypes
    )

    result = client.run_structured_state(_bundle(), [])
    client.run_markdown_report(_bundle(), [])

    for call in sdk_client.models.generate_content.call_args_list:
        thinking = call.kwargs["config"].thinking_config
        assert thinking.thinking_level == "HIGH"

    assert result.request_snapshot["thinking_level"] == "HIGH"
    assert result.request_snapshot["max_output_tokens"] == 16000


def test_phase_thinking_levels_override_shared_level(tmp_path):
    settings = _settings(tmp_path)
    settings.google_thinking_level = "low"
    settings.google_state_thinking_level = "high"
    settings.google_report_thinking_level = ""
    sdk_client = Mock()
    sdk_client.models.generate_content.side_effect = [
        _response('{"date":"2026-08-13"}'),
        _response("report"),
    ]
    client = GooglePipelineClient(
        settings, client=sdk_client, types_module=_FakeTypes
    )

    state = client.run_structured_state(_bundle(), [])
    client.run_markdown_report(_bundle(), [])

    assert state.request_snapshot["thinking_level"] == "HIGH"
    assert (
        sdk_client.models.generate_content.call_args_list[1]
        .kwargs["config"].thinking_config
        .thinking_level
        == "LOW"
    )


def test_invalid_thinking_level_raises_before_request(tmp_path):
    settings = _settings(tmp_path)
    settings.google_thinking_level = "extreme"
    sdk_client = Mock()
    client = GooglePipelineClient(
        settings, client=sdk_client, types_module=_FakeTypes
    )

    with pytest.raises(GooglePipelineError, match="must be MINIMAL"):
        client.run_markdown_report(_bundle(), [])
    sdk_client.models.generate_content.assert_not_called()


def test_repair_uses_daily_state_schema(tmp_path):
    client, sdk_client = _client(tmp_path, _response('{"date":"2026-08-13"}'))

    client.repair_structured_state({"date": "bad"}, "date is invalid")

    config = sdk_client.models.generate_content.call_args.kwargs["config"]
    assert "monte_carlo" in config.response_json_schema["properties"]


def test_image_parts_are_sent_as_inline_bytes(tmp_path):
    image = Path(tmp_path) / "chart.png"
    Image.new("RGB", (4, 4), color=(128, 128, 128)).save(image)
    client, sdk_client = _client(tmp_path, _response("report"))

    client.run_markdown_report(_bundle(), [image])

    content = sdk_client.models.generate_content.call_args.kwargs["contents"][0]
    assert len(content.parts) == 2
    assert content.parts[0]["inline_data"]["mime_type"] == "image/png"
    assert isinstance(content.parts[0]["inline_data"]["data"], bytes)


def test_markdown_report_omits_json_schema_and_maps_cache_usage(tmp_path):
    client, sdk_client = _client(tmp_path, _response("## The Takeaway", cached=42))

    result = client.run_markdown_report(_bundle(), [], pass2_audit={"test": True})

    assert result.text == "## The Takeaway"
    assert result.request_snapshot["test"] is True
    telemetry = result.request_snapshot["telemetry"]
    assert telemetry["cache_read_tokens"] == 42
    config = sdk_client.models.generate_content.call_args.kwargs["config"]
    assert not hasattr(config, "response_mime_type")


def test_substack_uses_gemini_default_thinking_and_schema(tmp_path):
    from tests.conftest import SAMPLE_STATE

    payload = {
        "title": "Daily SPX",
        "subtitle": "A disciplined market read",
        "sections": {section: "Useful market commentary." for section in SUBSTACK_SECTIONS},
    }
    settings = _settings(tmp_path)
    client, sdk_client = _client(tmp_path, _response(json.dumps(payload)))

    state = dict(SAMPLE_STATE)
    state["date"] = "2026-08-13"
    client.run_substack_article(DailyState.model_validate(state), "# Report")

    config = sdk_client.models.generate_content.call_args.kwargs["config"]
    assert config.max_output_tokens == 8000
    assert not hasattr(config, "thinking_config")
    assert config.response_mime_type == "application/json"


def test_invalid_structured_output_raises(tmp_path):
    client, _ = _client(tmp_path, _response(json.dumps(["not", "an", "object"])))

    with pytest.raises(GooglePipelineError, match="JSON object"):
        client.run_structured_state(_bundle(), [])


def test_podcast_script_uses_gemini_default_thinking_and_schema(tmp_path):
    payload = {"title": "Daily SPX Brief", "script": " ".join(["market"] * 450)}
    client, sdk_client = _client(tmp_path, _response(json.dumps(payload)))

    script, audit = client.run_podcast_script("# Article\n\nBody.")

    assert script.title == "Daily SPX Brief"
    assert len(script.script.split()) == 450
    assert audit["mode"] == "podcast_script"
    assert audit["telemetry"]["provider"] == "google"
    config = sdk_client.models.generate_content.call_args.kwargs["config"]
    assert config.max_output_tokens == 4000
    assert not hasattr(config, "thinking_config")
    assert config.response_mime_type == "application/json"
    assert config.response_json_schema["properties"]["script"]["type"] == "string"


def test_transient_retry_filter_does_not_retry_permanent_api_error():
    assert _is_transient_error(_StatusError(400)) is False
    assert _is_transient_error(_StatusError(429)) is True


def test_unavailable_response_text_is_wrapped(tmp_path):
    client, _ = _client(tmp_path, _UnavailableResponse())

    with pytest.raises(GooglePipelineError, match="text was unavailable"):
        client.run_markdown_report(_bundle(), [])
