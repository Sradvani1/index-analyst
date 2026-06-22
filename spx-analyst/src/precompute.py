"""Orchestrate Step 0 precompute: market data, structure, valuation, Monte Carlo."""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

from .config import Settings, get_settings
from .files import ANALYSIS_CONTEXT_FILENAME, InputError, write_json
from .market_data import (
    build_market_data_context,
    load_or_fetch_market_series,
    realized_vol_annualized,
)
from .monte_carlo import (
    compute_exhaustion_score,
    exhaustion_inputs_from_bars,
    run_monte_carlo,
    select_mu,
    select_sigma,
)
from .schemas import (
    AnalysisContext,
    DailyManifest,
    ResolvedEps,
    StructureContext,
)
from .structure import compute_structure, reanchor_downside_for_straddle

logger = logging.getLogger(__name__)


def _structure_to_schema(result) -> StructureContext:
    return StructureContext(
        active_swing_high_date=result.active_swing_high_date,
        active_swing_high_price=result.active_swing_high_price,
        swing_high_confirmation=result.swing_high_confirmation,
        active_swing_low_date=result.active_swing_low_date,
        active_swing_low_price=result.active_swing_low_price,
        swing_low_confirmation=result.swing_low_confirmation,
        fib_236=round(result.fib_236, 2),
        fib_382=round(result.fib_382, 2),
        fib_500=round(result.fib_500, 2),
        fib_618=round(result.fib_618, 2),
        liquidation_caution=round(result.liquidation_caution, 2),
        liquidation_nervous=round(result.liquidation_nervous, 2),
        liquidation_margin_call=round(result.liquidation_margin_call, 2),
        liquidation_cascade=round(result.liquidation_cascade, 2),
        upside_target=round(result.upside_target, 2),
        upside_target_rule=result.upside_target_rule,
        downside_target=round(result.downside_target, 2),
        downside_target_rule=result.downside_target_rule,
    )


def run_precompute(
    run_date: str,
    run_dir: Path,
    manifest: DailyManifest,
    eps: ResolvedEps,
    *,
    settings: Settings | None = None,
    force_fetch: bool = False,
) -> AnalysisContext:
    settings = settings or get_settings()
    try:
        series = load_or_fetch_market_series(
            run_date, run_dir, settings=settings, force_fetch=force_fetch
        )
    except ValueError as exc:
        raise InputError(
            f"market data fetch failed for {run_date}: {exc}. "
            "Ensure network access or a cached market_history.json exists in the run dir."
        ) from exc

    market = build_market_data_context(series, manifest)
    closes = np.array([b.close for b in series.bars], dtype=float)
    sma50 = np.full(len(closes), np.nan)
    for i in range(49, len(closes)):
        sma50[i] = float(np.mean(closes[i - 49 : i + 1]))

    structure_result = compute_structure(
        series.bars,
        sma50=sma50,
        pct_above_200dma=market.pct_above_200dma,
    )

    tnx_history = [float(v) for v in series.tnx.values]
    from .valuation import compute_valuation_context

    valuation = compute_valuation_context(market, eps, tnx_history)

    structure_result, reanchor_warnings = reanchor_downside_for_straddle(
        structure_result,
        market.spx_close,
        erp_reentry_floor=valuation.erp_reentry_floor_at_0_5pct,
        sma_200=market.sma_200,
    )
    if reanchor_warnings:
        market.precompute_warnings.extend(reanchor_warnings)
        for warning in reanchor_warnings:
            logger.warning("precompute straddle guard: %s", warning)

    structure = _structure_to_schema(structure_result)

    vol_60 = realized_vol_annualized(closes, min(60, len(closes) - 1))
    exh_inputs = exhaustion_inputs_from_bars(
        series.bars,
        structure_result.active_swing_low_price,
        structure_result.active_swing_low_date,
        market.realized_vol_20d,
        vol_60,
    )
    exhaustion_score, exhaustion_discount = compute_exhaustion_score(exh_inputs)

    mu = select_mu(market.pct_above_200dma)
    sigma = select_sigma(market.realized_vol_20d, market.vix)

    monte_carlo = run_monte_carlo(
        s0=market.spx_close,
        mu=mu,
        sigma=sigma,
        structure=structure_result,
        exhaustion_score=exhaustion_score,
        exhaustion_discount=exhaustion_discount,
        bars=series.bars,
    )

    ctx = AnalysisContext(
        date=run_date,
        market_data=market,
        valuation=valuation,
        structure=structure,
        monte_carlo=monte_carlo,
    )

    write_json(run_dir / ANALYSIS_CONTEXT_FILENAME, ctx)
    logger.info("wrote precompute context to %s", run_dir / ANALYSIS_CONTEXT_FILENAME)
    return ctx
