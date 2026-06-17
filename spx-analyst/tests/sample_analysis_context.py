"""Sample analysis context for prompt/engine tests."""

from __future__ import annotations

from src.schemas import (
    AnalysisContext,
    MarketDataContext,
    MonteCarloContext,
    StructureContext,
    ThresholdEvaluationRow,
    ValuationContext,
)


def sample_analysis_context(date: str = "2026-06-12") -> AnalysisContext:
    market = MarketDataContext(
        spx_close=7450.25,
        vix=18.4,
        us10y=4.5,
        as_of_date=date,
        pct_above_200dma=8.0,
        realized_vol_20d=0.16,
        sma_50=7400.0,
        sma_200=7200.0,
    )
    valuation = ValuationContext(
        forward_pe=21.0,
        trailing_pe=33.9,
        forward_earnings_yield=0.0476,
        erp=0.0026,
        erp_trend="stable",
        erp_reentry_floor_at_0_5pct=7100.0,
    )
    structure = StructureContext(
        active_swing_high_date="2026-06-01",
        active_swing_high_price=7500.0,
        swing_high_confirmation="pullback_3pct",
        active_swing_low_date="2026-04-01",
        active_swing_low_price=6800.0,
        swing_low_confirmation="rally_5pct",
        fib_236=7334.8,
        fib_382=7232.6,
        fib_500=7150.0,
        fib_618=7067.4,
        liquidation_caution=7275.0,
        liquidation_nervous=7125.0,
        liquidation_margin_call=6750.0,
        liquidation_cascade=6375.0,
        upside_target=7500.0,
        upside_target_rule="active_swing_high",
        downside_target=7232.6,
        downside_target_rule="fib_382",
    )
    mc = MonteCarloContext(
        sigma=0.16,
        mu=0.07,
        rally_exhaustion_score="Moderate",
        exhaustion_discount=0.05,
        upside_target=7500.0,
        downside_target=7232.6,
        upside_target_rule="active_swing_high",
        downside_target_rule="fib_382",
        prob_up_first_raw=0.58,
        prob_down_first_raw=0.42,
        prob_up_first_adjusted=0.53,
        prob_down_first_adjusted=0.47,
        cascades="If 7233 breaks, P(7150)=76%",
        median_days="upside 25d / downside 18d",
        drift_path="5d=7455; 10d=7460",
        cash_drag_prob=0.35,
        threshold_evaluation={
            "65": ThresholdEvaluationRow(adjusted_prob_up_first=0.53, actionable=False),
            "70": ThresholdEvaluationRow(adjusted_prob_up_first=0.53, actionable=False),
            "75": ThresholdEvaluationRow(adjusted_prob_up_first=0.53, actionable=False),
        },
    )
    return AnalysisContext(
        date=date,
        market_data=market,
        valuation=valuation,
        structure=structure,
        monte_carlo=mc,
    )
