import copy

from src.schemas import DailyState
from src.validation import parse_daily_state, validate_report

from tests.conftest import SAMPLE_STATE
from tests.fixtures.investor_report import PASS2_PROSE, assembled_report_for_state

GOOD_REPORT = assembled_report_for_state(DailyState.model_validate(SAMPLE_STATE), date="2026-06-12")


def test_parse_daily_state_valid():
    state, report = parse_daily_state(SAMPLE_STATE, "2026-06-11")
    assert state is not None
    assert report.passed


def test_parse_daily_state_invalid():
    bad = dict(SAMPLE_STATE)
    del bad["spx_close"]
    state, report = parse_daily_state(bad, "2026-06-11")
    assert state is None
    assert not report.passed
    assert report.errors


def test_parse_daily_state_date_mismatch_warns():
    state, report = parse_daily_state(SAMPLE_STATE, "2026-06-12")
    assert state is not None
    assert report.passed
    assert any(i.code == "date_mismatch" for i in report.warnings)


def test_validate_report_good():
    report = validate_report(GOOD_REPORT, "2026-06-12", max_chars=24000)
    assert report.passed


def test_validate_report_good_with_mixed_state():
    state = DailyState.model_validate(SAMPLE_STATE)
    report = validate_report(GOOD_REPORT, "2026-06-12", max_chars=24000, daily_state=state)
    assert report.passed


def test_validate_report_matrix_echo_unescapes_pipe_cells():
    state = DailyState.model_validate(SAMPLE_STATE)
    rows = list(state.decision_matrix.rows)
    rows[0] = rows[0].model_copy(update={"current_reading": "A | B"})
    decision_matrix = state.decision_matrix.model_copy(update={"rows": rows})
    state = state.model_copy(update={"decision_matrix": decision_matrix})
    md = assembled_report_for_state(state, date="2026-06-12")

    report = validate_report(md, "2026-06-12", max_chars=24000, daily_state=state)

    assert report.passed


def test_validate_report_matrix_echo_normalizes_published_dash_style():
    state = DailyState.model_validate(SAMPLE_STATE)
    rows = list(state.decision_matrix.rows)
    rows[0] = rows[0].model_copy(update={"signal": "Trim bias — patience"})
    decision_matrix = state.decision_matrix.model_copy(update={"rows": rows})
    state = state.model_copy(update={"decision_matrix": decision_matrix})
    md = assembled_report_for_state(state, date="2026-06-12")

    report = validate_report(md, "2026-06-12", max_chars=24000, daily_state=state)

    assert report.passed


def test_validate_report_missing_matrix():
    md = GOOD_REPORT.split("## Updated Decision Matrix")[0]
    report = validate_report(md, "2026-06-12", max_chars=24000)
    assert not report.passed
    assert any(i.code == "missing_section" for i in report.errors)


def test_validate_report_missing_section():
    md = GOOD_REPORT.replace("## Risk and Monte Carlo", "## Risk Summary")
    report = validate_report(md, "2026-06-12", max_chars=24000)
    assert not report.passed
    assert any(i.code in {"missing_section", "extra_section", "section_order"} for i in report.errors)


def test_validate_report_extra_section():
    md = GOOD_REPORT.replace(
        "## Evidence and Tensions",
        "## Evidence and Tensions\n\nBody.\n\n## Extra Section",
        1,
    )
    report = validate_report(md, "2026-06-12", max_chars=24000)
    assert not report.passed
    assert any(i.code == "extra_section" for i in report.errors)


def test_validate_report_section_order():
    md = GOOD_REPORT.replace("## Market Regime", "## MARKET REGIME PLACEHOLDER")
    parts = md.split("## MARKET REGIME PLACEHOLDER", 1)
    md = parts[0] + "## Price and Trend" + parts[1].replace("## Price and Trend", "## Market Regime", 1)
    report = validate_report(md, "2026-06-12", max_chars=24000)
    assert not report.passed
    assert any(i.code == "section_order" for i in report.errors)


def test_validate_report_empty():
    report = validate_report("   ", "2026-06-12", max_chars=24000)
    assert not report.passed


def test_validate_report_missing_evidence_and_tensions():
    state = DailyState.model_validate(SAMPLE_STATE)
    md = GOOD_REPORT.replace("## Evidence and Tensions", "## Conflict Summary")
    report = validate_report(md, "2026-06-12", max_chars=24000, daily_state=state)
    assert not report.passed
    assert any(i.code == "missing_evidence_and_tensions" for i in report.errors)


TENSIONS_SECTION = """## Evidence and Tensions

Primary tension: Bullish trend extension versus cautious valuation bucket.

**Extension vs valuation** (high)
- Bullish read: Price trend remains bullish with momentum intact (see SPX charts).
- Bearish read: Forward P/E in cautious bucket limits add aggression.
- Framework rule: Forward PE calibration - cautious bucket.
- Blocks action: Neither trim nor buy reaches confluence; hold and monitor.
"""


def test_validate_report_missing_primary_tension():
    state = DailyState.model_validate({**SAMPLE_STATE, "conflicting_evidence": []})
    unrelated = (
        "## Evidence and Tensions\n"
        "We focus only on liquidity plumbing today.\n\n"
        "**repo_market_note**\n"
        "- Overnight funding eased; no equity signal implications.\n"
    )
    md = GOOD_REPORT.replace(TENSIONS_SECTION, unrelated)
    report = validate_report(md, "2026-06-12", max_chars=24000, daily_state=state)
    assert not report.passed
    assert any(i.code == "missing_primary_tension" for i in report.errors)


def test_validate_report_paraphrased_long_tension_passes():
    long_tension = (
        "A fully restored record-setting technical skeleton (new all-time high at 7,600.50, "
        "upper-band walk, 50-day above a rising 200-day, VIX 15.86, junk spread tightening to "
        "1.28, Monte Carlo back to 56.23% up-first, Low exhaustion) is colliding with the most "
        "severe internal non-confirmation: McClellan breadth stuck at its 874.59 cycle-low shelf, "
        "ERP pinned at 0.31% inside the valuation-ceiling band on a 4.686% 10-year, and the "
        "Monte Carlo edge still failing the 70% threshold for an eighth consecutive session."
    )
    state = DailyState.model_validate({
        **SAMPLE_STATE,
        "primary_tension": long_tension,
        "conflicting_evidence": [],
    })
    paraphrased = (
        "## Evidence and Tensions\n"
        "Record price versus stale internals defines today's picture, and the validated posture "
        "respects the move without funding it. The S&P 500 printed a new all-time high at 7,600 "
        "riding the upper price band with credit spreads confirming, yet the McClellan volume "
        "summation measure sits on a cycle-low shelf while net fresh 52-week highs slip, and the "
        "ERP stays pinned inside the valuation ceiling band on a 4.7% ten-year. The Monte Carlo "
        "model's up-first probability once more fails the 70% threshold a late-bull regime asks "
        "for, an eighth consecutive session without a bullish edge; volatility reads docile but "
        "no capitulation washout confirms the recent swing low.\n"
    )
    md = GOOD_REPORT.replace(TENSIONS_SECTION, paraphrased)
    report = validate_report(md, "2026-06-12", max_chars=24000, daily_state=state)
    assert report.passed


def test_validate_report_contradicting_structural_bias():
    state = DailyState.model_validate(SAMPLE_STATE)  # Mid Bull
    md = GOOD_REPORT.replace("Mid Bull", "Bear Market")
    report = validate_report(md, "2026-06-12", max_chars=24000, daily_state=state)
    assert not report.passed
    assert any(i.code == "contradicting_structural_bias" for i in report.errors)


def test_validate_report_missing_structural_bias():
    state = DailyState.model_validate(SAMPLE_STATE)  # Mid Bull
    md = GOOD_REPORT.replace("Mid Bull", "the regime")
    report = validate_report(md, "2026-06-12", max_chars=24000, daily_state=state)
    assert not report.passed
    assert any(i.code == "missing_structural_bias" for i in report.errors)


def test_validate_report_unaddressed_high_weight_conflict_is_error():
    data = copy.deepcopy(SAMPLE_STATE)
    data["conflicting_evidence"] = [
        {
            "id": "zeta_signal",
            "layers": ["sentiment"],
            "bullish_read": "Quixotic zorblax indicators flipping upward",
            "bearish_read": "Wobblequark structure decaying without warning",
            "framework_rule": "Distinctive framework clause",
            "weight": "high",
            "chart_refs": ["01_chart.png"],
        }
    ]
    state = DailyState.model_validate(data)
    report = validate_report(GOOD_REPORT, "2026-06-12", max_chars=24000, daily_state=state)
    assert not report.passed
    assert any(
        i.code == "missing_high_weight_conflict" and i.severity == "error"
        for i in report.issues
    )


def test_validate_report_unaddressed_medium_weight_conflict_is_error():
    data = copy.deepcopy(SAMPLE_STATE)
    data["conflicting_evidence"] = [
        {
            "id": "zeta_signal",
            "layers": ["sentiment"],
            "bullish_read": "Quixotic zorblax indicators flipping upward",
            "bearish_read": "Wobblequark structure decaying without warning",
            "framework_rule": "Distinctive framework clause",
            "weight": "medium",
            "chart_refs": ["01_chart.png"],
        }
    ]
    state = DailyState.model_validate(data)
    report = validate_report(GOOD_REPORT, "2026-06-12", max_chars=24000, daily_state=state)
    assert not report.passed
    assert any(i.code == "missing_conflict" and i.severity == "error" for i in report.issues)


def test_validate_report_matrix_state_mismatch():
    state = DailyState.model_validate(SAMPLE_STATE)
    md = GOOD_REPORT.replace("| Recommended Action | hold_and_monitor | hold_and_monitor |", "| Recommended Action | buy | buy |")
    report = validate_report(md, "2026-06-12", max_chars=24000, daily_state=state)
    assert not report.passed
    assert any(i.code == "matrix_state_mismatch" for i in report.errors)


def test_validate_report_matrix_not_last():
    md = GOOD_REPORT + "\n## After Matrix\nTail content."
    report = validate_report(md, "2026-06-12", max_chars=24000)
    assert not report.passed
    assert any(i.code == "matrix_not_last" for i in report.errors)


def test_pass2_prose_has_eight_sections_only():
    import re

    headings = re.findall(r"^##\s+(.+?)\s*$", PASS2_PROSE, re.MULTILINE)
    assert len(headings) == 8
    assert "Updated Decision Matrix" not in headings
