"""Tests for post-Pass-1 precomputed field enforcement."""

from __future__ import annotations

from src.schemas import DailyState, DecisionMatrix, DecisionMatrixRow
from src.state_enforcement import apply_precomputed_fields

from tests.conftest import SAMPLE_STATE
from tests.sample_analysis_context import sample_analysis_context


def test_apply_precomputed_fields_overwrites_close_and_monte_carlo():
    ctx = sample_analysis_context("2026-06-12")
    state = DailyState.model_validate({**SAMPLE_STATE, "date": "2026-06-12"})
    tampered = state.model_copy(
        update={
            "spx_close": 1.0,
            "monte_carlo": state.monte_carlo.model_copy(
                update={"prob_up_first_raw": 0.99, "prob_up_first_adjusted": 0.99}
            ),
        }
    )

    enforced, warnings = apply_precomputed_fields(tampered, ctx)

    assert enforced.spx_close == ctx.market_data.spx_close
    assert enforced.monte_carlo.prob_up_first_raw == ctx.monte_carlo.prob_up_first_raw
    assert enforced.monte_carlo.prob_up_first_adjusted == ctx.monte_carlo.prob_up_first_adjusted
    assert enforced.monte_carlo.effective_threshold == 65
    assert enforced.monte_carlo.meets_threshold == ctx.monte_carlo.threshold_evaluation["65"].actionable
    assert any("decision_matrix" in w for w in warnings)


def test_apply_precomputed_fields_maps_late_bull_threshold():
    ctx = sample_analysis_context("2026-06-12")
    state = DailyState.model_validate(
        {**SAMPLE_STATE, "date": "2026-06-12", "structural_bias": "Late Bull / Topping"}
    )
    enforced, _ = apply_precomputed_fields(state, ctx)
    assert enforced.monte_carlo.effective_threshold == 70


def _erp_row_signal(ctx_trend: str) -> str:
    ctx = sample_analysis_context("2026-06-12")
    ctx = ctx.model_copy(
        update={"valuation": ctx.valuation.model_copy(update={"erp_trend": ctx_trend})}
    )
    state = DailyState.model_validate({**SAMPLE_STATE, "date": "2026-06-12"})
    enforced, _ = apply_precomputed_fields(state, ctx)
    row = next(
        r for r in enforced.decision_matrix.rows if r.signal_layer == "ERP State and Trend"
    )
    return row.signal


def test_erp_signal_expanding_is_attractive():
    # Framework: expanding ERP = structural support improving (bullish).
    assert _erp_row_signal("expanding") == "attractive"


def test_erp_signal_contracting_is_caution():
    # Framework: contracting ERP = structural support weakening (bearish).
    assert _erp_row_signal("contracting") == "caution"


def test_apply_precomputed_fields_syncs_matrix_rows():
    ctx = sample_analysis_context("2026-06-12")
    state = DailyState.model_validate({**SAMPLE_STATE, "date": "2026-06-12"})
    rows = [
        DecisionMatrixRow(
            signal_layer=row["signal_layer"],
            current_reading="wrong",
            signal="wrong",
        )
        if row["signal_layer"] == "Monte Carlo Edge"
        else DecisionMatrixRow(**row)
        for row in SAMPLE_STATE["decision_matrix"]["rows"]
    ]
    tampered = state.model_copy(update={"decision_matrix": DecisionMatrix(rows=rows)})
    enforced, warnings = apply_precomputed_fields(tampered, ctx)
    edge = next(
        r for r in enforced.decision_matrix.rows if r.signal_layer == "Monte Carlo Edge"
    )
    assert edge.current_reading == f"{round(ctx.monte_carlo.prob_up_first_adjusted * 100)}%"
    assert edge.signal == "monitor below threshold"
    assert any("decision_matrix" in w for w in warnings)
