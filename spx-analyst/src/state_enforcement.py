"""Enforce precomputed numeric fields on DailyState after Pass 1."""

from __future__ import annotations

import logging

from .prompts import STRUCTURAL_BIAS_THRESHOLDS
from .schemas import (
    AnalysisContext,
    DailyState,
    DecisionMatrix,
    DecisionMatrixRow,
    MonteCarloDetail,
)

logger = logging.getLogger(__name__)

DEFAULT_THRESHOLD = 65

# Decision-matrix rows owned by precompute (not chart LLM reads).
def _find_row_index(rows: list[DecisionMatrixRow], layer: str) -> int | None:
    target = layer.strip().lower()
    for i, row in enumerate(rows):
        if row.signal_layer.strip().lower() == target:
            return i
    return None


def _mc_edge_signal(meets_threshold: bool) -> str:
    return "actionable" if meets_threshold else "monitor below threshold"


def _erp_signal(erp_trend: str | None) -> str:
    # Per framework: expanding ERP = structural support improving (bullish),
    # contracting = support weakening (bearish).
    if erp_trend == "expanding":
        return "attractive"
    if erp_trend == "contracting":
        return "caution"
    if erp_trend == "stable":
        return "neutral"
    return "unknown"


def sync_matrix_precomputed_rows(
    state: DailyState,
    analysis_context: AnalysisContext,
    *,
    effective_threshold: int,
    meets_threshold: bool,
) -> tuple[DailyState, bool]:
    """Overwrite precompute-owned decision matrix rows from analysis_context."""
    mc = analysis_context.monte_carlo
    val = analysis_context.valuation
    pct_edge = round(mc.prob_up_first_adjusted * 100)

    erp_reading = "n/a"
    if val.erp is not None and val.erp_trend:
        erp_reading = f"ERP {val.erp:.2%} / {val.erp_trend}"
    elif val.forward_pe is not None:
        erp_reading = f"Forward P/E {val.forward_pe:.1f}"

    updates: dict[str, tuple[str, str]] = {
        "Structural Bias": (state.structural_bias, state.structural_bias),
        "Monte Carlo Threshold": (f"{effective_threshold}%", f"{effective_threshold}%"),
        "Volatility Input": (f"{mc.sigma:.4f}", f"σ={mc.sigma:.4f}"),
        "Drift Input": (f"{mc.mu:.4f}", f"μ={mc.mu:.4f}"),
        "Rally Exhaustion Score": (mc.rally_exhaustion_score, mc.rally_exhaustion_score),
        "Monte Carlo Edge": (f"{pct_edge}%", _mc_edge_signal(meets_threshold)),
        "ERP State and Trend": (erp_reading, _erp_signal(val.erp_trend)),
    }

    rows = list(state.decision_matrix.rows)
    changed = False
    for layer, (reading, signal) in updates.items():
        idx = _find_row_index(rows, layer)
        if idx is None:
            continue
        prev = rows[idx]
        if prev.current_reading == reading and prev.signal == signal:
            continue
        rows[idx] = DecisionMatrixRow(
            signal_layer=prev.signal_layer,
            current_reading=reading,
            signal=signal,
        )
        changed = True

    if not changed:
        return state, False
    return state.model_copy(update={"decision_matrix": DecisionMatrix(rows=rows)}), True


def apply_precomputed_fields(
    state: DailyState,
    analysis_context: AnalysisContext,
) -> tuple[DailyState, list[str]]:
    """Overwrite spx_close, monte_carlo, and precompute-owned matrix rows.

    structural_bias remains LLM-assigned; effective_threshold is derived from it.
    """
    warnings: list[str] = []
    threshold = STRUCTURAL_BIAS_THRESHOLDS.get(state.structural_bias)
    if threshold is None:
        threshold = DEFAULT_THRESHOLD
        warnings.append(
            f"unknown structural_bias {state.structural_bias!r}; "
            f"defaulting effective_threshold to {DEFAULT_THRESHOLD}"
        )

    mc = analysis_context.monte_carlo
    row_key = str(threshold)
    row = mc.threshold_evaluation.get(row_key)
    if row is None:
        row = mc.threshold_evaluation[str(DEFAULT_THRESHOLD)]
        warnings.append(f"missing threshold_evaluation[{row_key}]; using 65% row")

    enforced_mc = MonteCarloDetail(
        effective_threshold=threshold,
        meets_threshold=row.actionable,
        prob_up_first_raw=mc.prob_up_first_raw,
        prob_down_first_raw=mc.prob_down_first_raw,
        prob_up_first_adjusted=mc.prob_up_first_adjusted,
        prob_down_first_adjusted=mc.prob_down_first_adjusted,
        sigma=mc.sigma,
        mu=mc.mu,
        upside_target=mc.upside_target,
        downside_target=mc.downside_target,
        rally_exhaustion_score=mc.rally_exhaustion_score,
        conditional_cascade=mc.cascades,
        median_days=mc.median_days,
        drift_path=mc.drift_path,
        cash_drag_prob=mc.cash_drag_prob,
    )

    spx_close = analysis_context.market_data.spx_close
    if state.spx_close != spx_close:
        logger.info(
            "overwriting spx_close %.2f -> %.2f from analysis_context",
            state.spx_close,
            spx_close,
        )
    if state.monte_carlo.model_dump() != enforced_mc.model_dump():
        logger.info("overwriting monte_carlo from analysis_context (threshold=%s)", threshold)

    state = state.model_copy(update={"spx_close": spx_close, "monte_carlo": enforced_mc})
    state, matrix_changed = sync_matrix_precomputed_rows(
        state,
        analysis_context,
        effective_threshold=threshold,
        meets_threshold=row.actionable,
    )
    if matrix_changed:
        warnings.append("synced precomputed values into decision_matrix rows")

    return state, warnings


def audit_enforcement_issues(warnings: list[str]) -> list[dict[str, str]]:
    """Serialize enforcement audit entries for validation_report.json."""
    issues = [
        {
            "severity": "warning",
            "code": "precompute_enforcement",
            "message": (
                "Applied precomputed spx_close, monte_carlo, and matrix rows "
                "from analysis_context"
            ),
        }
    ]
    for warning in warnings:
        issues.append(
            {
                "severity": "warning",
                "code": "precompute_enforcement",
                "message": warning,
            }
        )
    return issues
