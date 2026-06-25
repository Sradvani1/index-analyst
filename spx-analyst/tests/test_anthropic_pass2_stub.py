"""Pass 2 stub detection and retry (claude-opus-4-8 follow-up)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.anthropic_client import AnthropicClient, AnthropicError, _is_pass2_stub_response
from src.prompts import PromptBundle


def test_stub_detects_opus_preamble():
    assert _is_pass2_stub_response(
        "I'll emit the structured daily state and then deliver the full markdown report."
    )


def test_stub_detects_short_text_without_headings():
    assert _is_pass2_stub_response("Short placeholder without markdown structure.")


def test_stub_rejects_full_report_opening():
    text = "# SPX Daily Analysis — 2026-06-10\n\n## 0. Structural Regime Classification\n"
    assert not _is_pass2_stub_response(text)


def test_stub_detects_short_spx_preamble_without_sections():
    text = "# SPX Daily Analysis — 2026-06-10\n\nI'll deliver the full report next."
    assert _is_pass2_stub_response(text)


def test_stub_rejects_investor_prose_opening():
    text = "## Today's Posture\n\nHold and monitor; no new deployment today.\n"
    assert not _is_pass2_stub_response(text)


def test_stub_rejects_long_body():
    text = "x" * 3500
    assert not _is_pass2_stub_response(text)


def _mock_response(text: str):
    block = MagicMock()
    block.type = "text"
    block.text = text
    resp = MagicMock()
    resp.content = [block]
    resp.model_dump.return_value = {"content": [{"type": "text", "text": text}]}
    return resp


@patch.object(AnthropicClient, "_create")
def test_run_markdown_report_retries_without_tools_on_stub(mock_create):
    stub = "I'll first emit the structured daily state, then provide the full markdown report."
    good = (
        "## Today's Posture\n\nHold and monitor.\n\n"
        "## Market Regime\n\nMid Bull structural bias.\n"
    )
    mock_create.side_effect = [_mock_response(stub), _mock_response(good)]

    client = AnthropicClient.__new__(AnthropicClient)
    client.settings = MagicMock()
    client.settings.model = "claude-opus-4-8"
    client.settings.max_output_tokens = 8000
    client.settings.prompt_cache_enabled = True
    client.settings.pass2_image_optimization_enabled = True
    client.settings.pass2_image_max_dimension = 1092
    client.settings.image_max_dimension = 1568

    bundle = PromptBundle(system_role="role", framework="framework", body="body")
    with patch("src.anthropic_client._user_content", return_value=[{"type": "text", "text": "body"}]):
        result = client.run_markdown_report(bundle, [Path("a.png")])

    assert result.text.strip() == good.strip()
    assert mock_create.call_count == 2
    assert "tools" not in mock_create.call_args_list[1].kwargs
    assert result.request_snapshot["pass2_stub_retry"] is True
    assert result.request_snapshot["pass2_tools_in_request"] is False


@patch.object(AnthropicClient, "_create")
def test_run_markdown_report_no_retry_when_valid(mock_create):
    good = "# SPX Daily Analysis — 2026-06-10\n\n## Updated Decision Matrix\n"
    mock_create.return_value = _mock_response(good)

    client = AnthropicClient.__new__(AnthropicClient)
    client.settings = MagicMock()
    client.settings.model = "claude-opus-4-8"
    client.settings.max_output_tokens = 8000
    client.settings.prompt_cache_enabled = True
    client.settings.pass2_image_optimization_enabled = True
    client.settings.pass2_image_max_dimension = 1092
    client.settings.image_max_dimension = 1568

    bundle = PromptBundle(system_role="role", framework="framework", body="body")
    with patch("src.anthropic_client._user_content", return_value=[{"type": "text", "text": "body"}]):
        result = client.run_markdown_report(bundle, [])

    assert mock_create.call_count == 1
    assert "tools" in mock_create.call_args.kwargs
    assert result.request_snapshot["pass2_stub_retry"] is False
    assert result.request_snapshot["pass2_tools_in_request"] is True


@patch.object(AnthropicClient, "_create")
def test_run_markdown_report_raises_when_stub_persists(mock_create):
    stub = "I'll emit the structured daily state first."
    mock_create.side_effect = [_mock_response(stub), _mock_response(stub)]

    client = AnthropicClient.__new__(AnthropicClient)
    client.settings = MagicMock()
    client.settings.model = "claude-opus-4-8"
    client.settings.max_output_tokens = 8000
    client.settings.prompt_cache_enabled = False
    client.settings.pass2_image_optimization_enabled = True
    client.settings.pass2_image_max_dimension = 1092
    client.settings.image_max_dimension = 1568

    bundle = PromptBundle(system_role="role", framework="framework", body="body")
    with patch("src.anthropic_client._user_content", return_value=[{"type": "text", "text": "body"}]):
        with pytest.raises(AnthropicError, match="stub markdown after retry"):
            client.run_markdown_report(bundle, [])
