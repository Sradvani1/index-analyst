"""Tests for web viewer report markdown parsing."""

from __future__ import annotations

from src.web.report_parse import extract_posture_lead, first_paragraph, strip_inline_markdown

SAMPLE_REPORT = """\
# SPX Daily Analysis — 2026-06-29

**Close:** 7,440.43

## Today's Posture

The posture for the next session is **Defensive — trim bias**. Today's sharp snap-back is a tradeable bounce.

Price reclaimed the flattening 50-day SMA on a strong close.

## Market Regime

Regime body here.
"""


def test_extract_posture_lead_returns_first_paragraph() -> None:
    lead = extract_posture_lead(SAMPLE_REPORT)
    assert lead.startswith("The posture for the next session is Defensive")
    assert "**" not in lead
    assert "50-day SMA" not in lead


def test_extract_posture_lead_missing_section() -> None:
    assert extract_posture_lead("## Market Regime\n\nNo posture.") == ""


def test_strip_inline_markdown() -> None:
    assert strip_inline_markdown("**Bold** and *italic*") == "Bold and italic"


def test_first_paragraph_skips_leading_blank_lines() -> None:
    body = "\n\nFirst block.\n\nSecond block."
    assert first_paragraph(body) == "First block."
