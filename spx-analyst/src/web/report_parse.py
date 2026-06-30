"""Markdown parsing helpers for the Phase 2 web viewer."""

from __future__ import annotations

import re

POSTURE_SECTION = re.compile(r"today's posture", re.IGNORECASE)
HEADING_PATTERN = re.compile(r"^##\s+(.+?)\s*$")


def split_sections(markdown: str) -> list[tuple[str, str]]:
    """Split report markdown on ``## `` headings into (title, body) pairs."""
    sections: list[tuple[str, str]] = []
    current_title: str | None = None
    current_lines: list[str] = []

    def flush() -> None:
        nonlocal current_title, current_lines
        if current_title is not None:
            sections.append((current_title, "\n".join(current_lines).strip()))
        current_title = None
        current_lines = []

    for line in markdown.splitlines():
        match = HEADING_PATTERN.match(line)
        if match:
            flush()
            current_title = match.group(1).strip()
            continue
        if current_title is not None:
            current_lines.append(line)
    flush()
    return sections


def strip_inline_markdown(text: str) -> str:
    """Remove common inline markdown for plain card display."""
    cleaned = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    cleaned = re.sub(r"\*(.+?)\*", r"\1", cleaned)
    cleaned = re.sub(r"__(.+?)__", r"\1", cleaned)
    cleaned = re.sub(r"_(.+?)_", r"\1", cleaned)
    return cleaned.strip()


def first_paragraph(body: str) -> str:
    """Return the first non-empty paragraph block in a section body."""
    for block in body.split("\n\n"):
        paragraph = block.strip()
        if paragraph:
            return strip_inline_markdown(paragraph)
    return ""


def extract_posture_lead(markdown: str) -> str:
    """First paragraph of the Today's Posture section, or empty string."""
    for title, body in split_sections(markdown):
        if POSTURE_SECTION.search(title):
            return first_paragraph(body)
    return ""
