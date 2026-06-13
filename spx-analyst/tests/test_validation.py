from src.schemas import DailyState
from src.validation import parse_daily_state, validate_report

from tests.conftest import SAMPLE_STATE

GOOD_REPORT = """
# Daily Analysis 2026-06-12

## Step 1: Price Action & Trend Recentering
Close held above the 50-day.

## Step 2: Technical & Sentiment Pulse
RSI 64, MFI 70.

## Evidence Reconciliation
Primary tension: Bullish trend extension versus cautious valuation bucket.

**extension_vs_valuation**
- Bullish read: Price trend remains bullish with momentum intact (see SPX charts).
- Bearish read: Forward P/E in cautious bucket limits add aggression.
- Framework rule: Forward P/E calibration table — cautious bucket.
- Blocks action: Neither trim nor buy reaches 3-of-5; hold and monitor.

## Step 3: Fundamental Valuation & ERP
Forward P/E elevated.

## Step 4: Leverage & Margin Debt Monitor
VIX below 20.

## Step 5: Monte Carlo & Brownian Motion
Edge 58% — monitor only, below 65% threshold.

## Step 6: Tactical Matrix
Trim ladder mapped.

## Step 7: Narrative & Executive Summary
Given mixed evidence — bullish trend extension versus cautious valuation — the
3-of-5 rule is unmet and Monte Carlo edge is below threshold, resolving to hold
and monitor per the no-forced-signal rule.

## Updated Decision Matrix
| Signal Layer | Reading | Signal |
|---|---|---|
| Trend Regime | bullish | Bull |
| RSI / MFI | 64/70 | Neutral |
| Bollinger Band | upper half | Within |
| ERP | low | Caution |
| Leverage Risk | moderate | Moderate |
| Monte Carlo Edge | 58% | Monitor |
| Sentiment | greed | Greed (mixed) |
| RECOMMENDED ACTION | | Hold and monitor |
"""


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


def test_validate_report_missing_matrix():
    md = GOOD_REPORT.split("## Updated Decision Matrix")[0]
    report = validate_report(md, "2026-06-12", max_chars=24000)
    assert not report.passed
    assert any(i.code == "missing_decision_matrix" for i in report.errors)


def test_validate_report_missing_step():
    md = GOOD_REPORT.replace("## Step 5: Monte Carlo & Brownian Motion", "## Step 5: Something else")
    report = validate_report(md, "2026-06-12", max_chars=24000)
    assert not report.passed
    assert any(i.code == "missing_step" for i in report.errors)


def test_validate_report_empty():
    report = validate_report("   ", "2026-06-12", max_chars=24000)
    assert not report.passed


def test_validate_report_mixed_missing_reconciliation():
    state = DailyState.model_validate(SAMPLE_STATE)
    md = GOOD_REPORT.replace("## Evidence Reconciliation", "## Conflict Summary")
    report = validate_report(md, "2026-06-12", max_chars=24000, daily_state=state)
    assert not report.passed
    assert any(i.code == "missing_evidence_reconciliation" for i in report.errors)


RECON_SECTION = """## Evidence Reconciliation
Primary tension: Bullish trend extension versus cautious valuation bucket.

**extension_vs_valuation**
- Bullish read: Price trend remains bullish with momentum intact (see SPX charts).
- Bearish read: Forward P/E in cautious bucket limits add aggression.
- Framework rule: Forward P/E calibration table — cautious bucket.
- Blocks action: Neither trim nor buy reaches 3-of-5; hold and monitor.
"""


def test_validate_report_mixed_missing_primary_tension():
    state = DailyState.model_validate(SAMPLE_STATE)
    # Replace the whole reconciliation section with content that never touches
    # the primary tension's substance.
    unrelated = (
        "## Evidence Reconciliation\n"
        "We focus only on liquidity plumbing today.\n\n"
        "**repo_market_note**\n"
        "- Overnight funding eased; no equity signal implications.\n"
    )
    md = GOOD_REPORT.replace(RECON_SECTION, unrelated)
    assert unrelated in md  # guard: the replacement actually occurred
    report = validate_report(md, "2026-06-12", max_chars=24000, daily_state=state)
    assert not report.passed
    assert any(i.code == "missing_primary_tension" for i in report.errors)
