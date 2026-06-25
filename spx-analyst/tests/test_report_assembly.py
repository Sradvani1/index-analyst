"""Tests for investor report assembly."""

from __future__ import annotations

import re

from src.prompts import INVESTOR_REPORT_SECTIONS, PASS2_PROSE_SECTIONS
from src.report_assembly import (
    assemble_investor_report,
    extract_prose_sections,
    render_decision_matrix_table,
    render_header_snapshot,
    render_monte_carlo_facts_block,
    render_tactical_levels_block,
    render_valuation_facts_block,
)
from src.schemas import DailyState

from tests.conftest import SAMPLE_STATE
from tests.fixtures.investor_report import PASS2_PROSE, assembled_report_for_state
from tests.sample_analysis_context import sample_analysis_context


def test_render_header_snapshot_includes_close_line(sample_state):
    ctx = sample_analysis_context(sample_state.date)
    header = render_header_snapshot(date=sample_state.date, daily_state=sample_state, analysis_context=ctx)
    assert header.startswith(f"# SPX Daily Analysis — {sample_state.date}")
    assert "Close:" in header
    assert sample_state.structural_bias in header
    assert "Framework version:" in header


def test_render_valuation_facts_block(sample_state):
    ctx = sample_analysis_context(sample_state.date)
    block = render_valuation_facts_block(daily_state=sample_state, analysis_context=ctx)
    assert "Forward P/E" in block
    assert "ERP:" in block
    assert sample_state.valuation_bucket in block


def test_render_monte_carlo_facts_block(sample_state):
    ctx = sample_analysis_context(sample_state.date)
    block = render_monte_carlo_facts_block(daily_state=sample_state, analysis_context=ctx)
    assert "Adjusted up-first" in block
    assert "Effective threshold" in block


def test_render_tactical_levels_block():
    ctx = sample_analysis_context()
    block = render_tactical_levels_block(analysis_context=ctx)
    assert "Fibonacci" in block
    assert "Liquidation zones" in block


def test_render_decision_matrix_table_matches_state(sample_state):
    table = render_decision_matrix_table(daily_state=sample_state)
    assert "## Updated Decision Matrix" in table
    for row in sample_state.decision_matrix.rows:
        assert row.signal_layer in table


def test_extract_prose_sections_strips_preamble_and_matrix():
    drifted = (
        "# SPX Daily Analysis — 2026-06-12\n\n"
        + PASS2_PROSE
        + "\n\n## Updated Decision Matrix\n| Signal Layer | Current Reading | Signal |\n"
    )
    sections = extract_prose_sections(drifted)
    assert set(sections) == set(PASS2_PROSE_SECTIONS)
    assert "Today's Posture" in sections


def test_assemble_investor_report_nine_visible_parts(sample_state):
    report = assembled_report_for_state(sample_state, date="2026-06-12")
    assert report.startswith("# SPX Daily Analysis — 2026-06-12")
    headings = re.findall(r"^##\s+(.+?)\s*$", report, re.MULTILINE)
    assert headings == INVESTOR_REPORT_SECTIONS
    assert "Key valuation levels" in report
    assert "Probability snapshot" in report
    assert "**Tactical levels:**" in report
    assert report.strip().endswith("|")


def test_assemble_investor_report_golden_snapshot(sample_state):
    state = DailyState.model_validate({**SAMPLE_STATE, "date": "2026-06-12"})
    report = assemble_investor_report(
        date="2026-06-12",
        daily_state=state,
        analysis_context=sample_analysis_context("2026-06-12"),
        prose_md=PASS2_PROSE,
    )
    assert "Primary tension: Bullish trend extension versus cautious valuation bucket." in report
    assert "**Extension vs valuation**" in report
    assert "**extension_vs_valuation**" not in report
    assert "Recommended Action" in report
