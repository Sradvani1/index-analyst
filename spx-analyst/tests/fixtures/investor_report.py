"""Shared Pass 2 prose and assembled-report fixtures for investor template tests."""

from __future__ import annotations

from src.report_assembly import assemble_investor_report
from src.schemas import DailyState

from tests.sample_analysis_context import sample_analysis_context

PASS2_PROSE = """
## Today's Posture
Mid Bull regime with hold and monitor posture. Lead with patience: no new deployment until valuation and Monte Carlo align.

## Market Regime
Mid Bull structural bias assigned. Extension above the 200-day remains moderate while ERP sits thin but stable.

## Price and Trend
Close held above the 50-day with the Mid Bull bias intact. Trend remains constructive but extended.

## Technicals and Sentiment
RSI 64 and MFI 70 — neutral momentum with sentiment not yet confirming a chase.

## Valuation and ERP
Forward P/E sits in the cautious bucket; ERP offers little cushion for aggressive adds.

## Risk and Monte Carlo
Precomputed Monte Carlo edge is below the Mid Bull threshold — monitor only, not actionable for deployment.

## Tactical Levels and Next Session Plan
Respect Fibonacci re-entry bands and liquidation caution zones before adding exposure.

## Evidence and Tensions
Primary tension: Bullish trend extension versus cautious valuation bucket.

**extension_vs_valuation** (high)
- Bullish read: Price trend remains bullish with momentum intact (see SPX charts).
- Bearish read: Forward P/E in cautious bucket limits add aggression.
- Framework rule: Forward PE calibration — cautious bucket.
- Blocks action: Neither trim nor buy reaches confluence; hold and monitor.
""".strip()


def assembled_report_for_state(state: DailyState, date: str | None = None) -> str:
    run_date = date or state.date
    ctx = sample_analysis_context(run_date)
    return assemble_investor_report(
        date=run_date,
        daily_state=state,
        analysis_context=ctx,
        prose_md=PASS2_PROSE,
    )
