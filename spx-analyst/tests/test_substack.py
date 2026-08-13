import pytest

from src.schemas import SUBSTACK_SECTIONS, SubstackArticle
from src.substack import parse_substack_response, render_substack_markdown


def _payload() -> dict[str, object]:
    return {
        "title": "A Clear Market Read",
        "subtitle": "The daily setup in plain English.",
        "sections": {heading: f"Content for {heading}." for heading in SUBSTACK_SECTIONS},
    }


def test_substack_article_renders_consistent_markdown() -> None:
    article = SubstackArticle.model_validate(_payload())
    markdown = render_substack_markdown(article)
    assert "# A Clear Market Read" in markdown
    assert [line[3:] for line in markdown.splitlines() if line.startswith("## ")] == SUBSTACK_SECTIONS


def test_substack_response_rejects_missing_section() -> None:
    payload = _payload()
    sections = payload["sections"]
    assert isinstance(sections, dict)
    sections.pop("The Risk Case")

    with pytest.raises(ValueError):
        parse_substack_response(__import__("json").dumps(payload))
