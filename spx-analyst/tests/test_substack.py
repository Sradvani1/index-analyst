import pytest

from src.schemas import DailyState, SUBSTACK_SECTIONS, SubstackArticle
from src.substack import (
    parse_substack_response,
    render_substack_markdown,
    sanitize_substack_sources,
)
from tests.conftest import SAMPLE_STATE


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


def test_substack_sources_remove_internal_monte_carlo_material() -> None:
    state = DailyState.model_validate(SAMPLE_STATE)
    report = (
        "# Report\n\n"
        "## Market Regime\n\nThe trend is constructive.\n\n"
        "## Risk and Monte Carlo\n\nThe probability edge is balanced.\n\n"
        "## Evidence and Tensions\n\nBreadth remains mixed.\n\n"
        "The probability output is internal.\n"
    )

    state_json, visible_report = sanitize_substack_sources(state, report)

    assert "monte_carlo" not in state_json
    assert "Monte Carlo" not in visible_report
    assert "probability" not in visible_report.lower()
    assert "The trend is constructive." in visible_report
    assert "Breadth remains mixed." in visible_report
