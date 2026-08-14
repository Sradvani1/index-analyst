"""Generation and rendering of the short daily Substack article."""

from __future__ import annotations

import json
import html
import re
from typing import Any

from .schemas import DailyState, SubstackArticle, SUBSTACK_SECTIONS

SUBSTACK_INSTRUCTIONS = """You are the writer for a daily stock market publication.

Task:
Rewrite the supplied technical SPX market report into a concise daily article for retail investors who want a clear three-to-five-minute read.

Source authority:
- The validated daily state is authoritative.
- Explain the supplied analysis. Do not independently reanalyze the market.
- Preserve the meaning of the supplied structural bias, market conclusion, and posture.
- Preserve key levels, confirmation conditions, and invalidation conditions.
- Translate internal labels and classifications into plain, reader-facing language.
- Use only facts from the supplied daily state and technical report.

Audience and style:
- Use calm, analytical, plain English.
- Preserve useful technical detail. Briefly explain specialized terms when helpful.
- Do not mention Monte Carlo or its outputs.
- Keep paragraphs short and prioritize what changed, why it matters, confirmation conditions,
  invalidation conditions, and the bottom line.
- Do not repeat a level, posture, or conclusion unless the later reference adds a materially different implication.
- Avoid unexplained jargon and oversimplification.
- Avoid stock phrases and repetitive transitions.
- Do not use em dashes, colons, or semicolons anywhere in the article. Use periods or commas instead.
- Do not use sensational, promotional, or alarmist language.
- Do not make guarantees, provide personalized investment advice, or recommend position sizes or allocations.

Required output:
- Return only the JSON object defined by the response schema.
- Return a useful title and subtitle, followed by exactly these sections in this order:
  The Takeaway
  What Happened Today
  Why It Matters
  Levels and Signals to Watch
  The Bull Case
  The Risk Case
  Bottom Line
- Every section must contain substantive prose. Target 600-900 words overall.
- Do not return Markdown fences, commentary, or any extra fields.

State conclusions directly for the reader. Do not mention internal framework terminology, source documents, model mechanics, or the generation process.
"""

_INTERNAL_ANALYSIS_RE = re.compile(
    r"monte\s+carlo|probabilit(?:y|ies)|up-first|down-first|drift\s+path|"
    r"cash-drag|rally exhaustion|conditional cascade|\bσ\b|\bμ\b",
    re.IGNORECASE,
)


def sanitize_substack_sources(daily_state: DailyState, report_markdown: str) -> tuple[str, str]:
    """Remove internal Monte Carlo material before editorial generation."""
    state = daily_state.model_dump(mode="json", exclude={"monte_carlo"})
    sections = re.split(r"(?=^##\s+)", report_markdown, flags=re.MULTILINE)
    visible_sections: list[str] = []
    for section in sections:
        heading = re.match(r"^##\s+(.+?)\s*$", section, re.MULTILINE)
        if heading and "monte carlo" in heading.group(1).lower():
            continue
        blocks = re.split(r"\n\s*\n", section)
        visible_sections.append(
            "\n\n".join(block for block in blocks if not _INTERNAL_ANALYSIS_RE.search(block))
        )
    return json.dumps(state, indent=2), "\n\n".join(visible_sections).strip()


def build_substack_prompt(daily_state: DailyState, report_markdown: str) -> str:
    state, report = sanitize_substack_sources(daily_state, report_markdown)
    return (
        "SOURCE CONTEXT: VALIDATED DAILY STATE\n"
        "```json\n"
        f"{state}\n"
        "```\n\n"
        "SOURCE CONTEXT: TECHNICAL REPORT\n"
        "```markdown\n"
        f"{report}\n"
        "```"
    )


def render_substack_markdown(article: SubstackArticle) -> str:
    lines = [
        f"# {html.escape(article.title, quote=False)}",
        "",
        f"*{html.escape(article.subtitle, quote=False)}*",
        "",
    ]
    for heading in SUBSTACK_SECTIONS:
        lines.extend(
            [
                f"## {heading}",
                "",
                html.escape(article.sections.ordered_values()[heading].strip(), quote=False),
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def render_substack_html(article: SubstackArticle) -> str:
    from markdown import markdown

    return markdown(
        render_substack_markdown(article),
        extensions=["tables", "sane_lists", "nl2br"],
    )


def validate_substack_markdown(markdown_text: str) -> None:
    headings = re.findall(r"^##\s+(.+?)\s*$", markdown_text, re.MULTILINE)
    if headings != SUBSTACK_SECTIONS:
        raise ValueError("Substack article is missing required sections or has incorrect order")
    for heading in SUBSTACK_SECTIONS:
        match = re.search(
            rf"^##\s+{re.escape(heading)}\s*$([\s\S]*?)(?=^##\s+|\Z)",
            markdown_text,
            re.MULTILINE,
        )
        if not match or not match.group(1).strip():
            raise ValueError(f"Substack section is empty: {heading}")


def parse_substack_response(raw_text: str) -> SubstackArticle:
    try:
        payload: Any = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ValueError("Substack model returned invalid JSON") from exc
    article = SubstackArticle.model_validate(payload)
    validate_substack_markdown(render_substack_markdown(article))
    return article
