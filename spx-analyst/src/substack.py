"""Generation and rendering of the short daily Substack article."""

from __future__ import annotations

import json
import html
import re
from typing import Any

from .schemas import DailyState, SubstackArticle, SUBSTACK_SECTIONS


def build_substack_prompt(daily_state: DailyState, report_markdown: str) -> str:
    state = json.dumps(daily_state.model_dump(mode="json"), indent=2)
    headings = ", ".join(SUBSTACK_SECTIONS)
    return (
        "Create a concise daily market article from the supplied technical report.\n\n"
        "Audience: sophisticated retail investors and fund managers who want a clear "
        "three-to-five-minute read. Use calm, analytical, plain English. Explain useful "
        "technical terms briefly, keep paragraphs short, and do not give personalized advice.\n\n"
        "The validated daily state is authoritative. Rewrite and explain it, but do not "
        "change its posture, recommendation, or conclusions. Use only facts from the supplied "
        "state and report. Do not mention internal passes, prompts, filenames, or the framework.\n\n"
        f"Return JSON with exactly these section keys, in this order: {headings}. Also return "
        "title and subtitle. Target 600-900 words. Return no Markdown fences or extra text.\n\n"
        f"Validated daily state:\n```json\n{state}\n```\n\n"
        f"Technical report:\n```markdown\n{report_markdown}\n```"
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
