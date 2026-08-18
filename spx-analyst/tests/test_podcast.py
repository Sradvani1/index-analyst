"""Tests for podcast script generation and validation."""

from __future__ import annotations

import json

import pytest

from src.podcast import (
    build_podcast_prompt,
    parse_podcast_response,
    render_podcast_script,
)
from src.schemas import PodcastScript


def _script(words: int = 450) -> dict[str, str]:
    return {"title": "A Calm Close", "script": " ".join(["market"] * words)}


def test_build_podcast_prompt_unescapes_html_entities() -> None:
    source = "# S&amp;P 500 Falls\n\nThe S&amp;P closed at 7,785.76."
    prompt = build_podcast_prompt(source)
    assert "S&P 500 Falls" in prompt
    assert "&amp;" not in prompt
    assert "SOURCE CONTEXT: DAILY SUBSTACK ARTICLE" in prompt


def test_parse_podcast_response_accepts_valid_script() -> None:
    script = parse_podcast_response(json.dumps(_script()))
    assert isinstance(script, PodcastScript)
    assert script.title == "A Calm Close"
    assert len(script.script.split()) == 450


def test_parse_podcast_response_rejects_invalid_json() -> None:
    with pytest.raises(ValueError, match="invalid JSON"):
        parse_podcast_response("not json")


def test_parse_podcast_response_rejects_non_object() -> None:
    with pytest.raises(ValueError):
        parse_podcast_response(json.dumps(["a", "list"]))


def test_parse_podcast_response_rejects_too_short_script() -> None:
    with pytest.raises(ValueError, match="word count"):
        parse_podcast_response(json.dumps(_script(words=10)))


def test_parse_podcast_response_rejects_too_long_script() -> None:
    with pytest.raises(ValueError, match="word count"):
        parse_podcast_response(json.dumps(_script(words=900)))


def test_parse_podcast_response_rejects_markdown_artifacts() -> None:
    payload = _script()
    payload["script"] = " ".join(["market"] * 450) + "\n\n## What Happened\n\nA strong day."
    with pytest.raises(ValueError, match="Markdown"):
        parse_podcast_response(json.dumps(payload))


def test_parse_podcast_response_rejects_extra_fields() -> None:
    payload = _script()
    payload["extra"] = "field"
    with pytest.raises(ValueError):
        parse_podcast_response(json.dumps(payload))


def test_parse_podcast_response_rejects_markdown_title() -> None:
    payload = _script()
    payload["title"] = "**Breaking** News"
    with pytest.raises(ValueError, match="title"):
        parse_podcast_response(json.dumps(payload))


def test_parse_podcast_response_rejects_title_with_newline() -> None:
    payload = _script()
    payload["title"] = "First line\nSecond line"
    with pytest.raises(ValueError, match="title"):
        parse_podcast_response(json.dumps(payload))


def test_render_podcast_script_prefixes_title() -> None:
    rendered = render_podcast_script(PodcastScript(**_script()))
    assert rendered.startswith("# A Calm Close\n")
    assert "market market" in rendered