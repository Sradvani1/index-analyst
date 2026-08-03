"""Transient retry behavior for the Anthropic client (529 OverloadedError fix)."""

from __future__ import annotations

from unittest.mock import MagicMock

import anthropic
import httpx
import pytest

from src.anthropic_client import AnthropicClient, _TRANSIENT_ERRORS


def _make_overloaded_error() -> anthropic.OverloadedError:
    req = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    resp = httpx.Response(529, request=req)
    return anthropic.OverloadedError("overloaded", response=resp, body=None)


def test_overloaded_error_in_transient_set():
    assert anthropic.OverloadedError in _TRANSIENT_ERRORS


def _client_with_error_sequence(errors: list[Exception], success):
    client = AnthropicClient.__new__(AnthropicClient)
    client._client = MagicMock()
    client._client.messages.create.side_effect = [*errors, success]
    return client


def test_overloaded_error_retries_then_succeeds():
    client = _client_with_error_sequence(
        [_make_overloaded_error()], MagicMock()
    )
    client._create(model="test", max_tokens=100)
    assert client._client.messages.create.call_count == 2


def test_overloaded_error_exhausts_after_three_attempts():
    client = AnthropicClient.__new__(AnthropicClient)
    client._client = MagicMock()

    def raise_overloaded(**kwargs):
        raise _make_overloaded_error()

    client._client.messages.create.side_effect = raise_overloaded
    with pytest.raises(anthropic.OverloadedError):
        client._create(model="test", max_tokens=100)
    assert client._client.messages.create.call_count == 3
