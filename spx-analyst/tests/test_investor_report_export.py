"""Tests for investor report PDF export."""

from __future__ import annotations

from pathlib import Path

from src.investor_report_export import (
    export_investor_report,
    parse_report_meta,
    render_investor_report_html,
    render_investor_report_pdf,
    tone_for,
)

SAMPLE = """\
# SPX Daily Analysis — 2026-06-29

**Framework version:** daily-2026-06
**Close:** 7,440.43 | **Structural Bias:** Late Bull / Topping | **Posture:** Defensive — trim bias

## Today's Posture

The posture for the next session is **Defensive — trim bias**. First paragraph lead.

Second paragraph with more detail.

## Updated Decision Matrix

| Signal Layer | Current Reading | Signal |
|---|---|---|
| Recommended Action | Trim into strength | Defensive — trim bias |
"""


def test_parse_report_meta_extracts_header_fields() -> None:
    meta = parse_report_meta(SAMPLE)
    assert meta.date == "2026-06-29"
    assert meta.close == "7,440.43"
    assert meta.structural_bias == "Late Bull / Topping"
    assert meta.posture == "Defensive — trim bias"
    assert meta.framework_version == "daily-2026-06"


def test_tone_for_trim_is_bearish() -> None:
    assert tone_for("Defensive — trim bias") == "bear"


def test_render_includes_header_and_sections() -> None:
    html_doc = render_investor_report_html(SAMPLE)
    assert 'class="report-header"' in html_doc
    header = html_doc.split("</header>")[0]
    assert "2026-06-29" in header
    assert "7,440.43" in header
    assert "header-title" not in header
    assert "7,440.43" in html_doc
    assert "chip" not in html_doc.split("</header>")[0]
    assert "First paragraph lead." in html_doc
    assert "Second paragraph with more detail." in html_doc
    assert "matrix-action" in html_doc
    assert "Contents" not in html_doc
    assert "SPX Daily Tactical Analysis" not in html_doc


def test_render_pdf_produces_valid_pdf() -> None:
    pdf_bytes = render_investor_report_pdf(SAMPLE, fallback_date="2026-06-29")
    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 1000


def test_export_writes_pdf_file(tmp_path: Path) -> None:
    source = tmp_path / "2026-06-29-analysis.md"
    source.write_text(SAMPLE, encoding="utf-8")
    pdf_dir = tmp_path / "daily_pdfs"
    dest = export_investor_report(source, pdf_dir=pdf_dir)
    assert dest.exists()
    assert dest == pdf_dir / "2026-06-29-investor-report.pdf"
    assert dest.read_bytes().startswith(b"%PDF")
