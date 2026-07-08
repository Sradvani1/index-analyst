import copy

import pytest
from pydantic import ValidationError

from src.schemas import (
    DailyManifest,
    DailyState,
    EmitDailyStateInput,
    flat_to_nested,
)

_MATRIX_ROWS = [
    {"signal_layer": layer, "current_reading": "n/a", "signal": "n/a"}
    for layer in [
        "Structural Bias",
        "Monte Carlo Threshold",
        "Volatility Input",
        "Drift Input",
        "Rally Exhaustion Score",
        "Trend Regime",
        "Intraday Close Position",
        "RSI / MFI State",
        "20-Day SMA Status",
        "Bollinger Band State",
        "ERP State and Trend",
        "Credit Condition",
        "Breadth Condition",
        "VIX Regime",
        "Leverage Risk State",
        "Monte Carlo Edge",
        "Overall Signal Balance",
    ]
]
_MATRIX_ROWS.append(
    {
        "signal_layer": "Recommended Action",
        "current_reading": "hold_and_monitor",
        "signal": "hold_and_monitor",
    }
)

_FLAT_SAMPLE = {
    "date": "2026-06-11",
    "framework_version": "daily-2026-06",
    "spx_close": 7440.0,
    "structural_bias": "Mid Bull",
    "base_case": "bullish_but_extended",
    "trend_regime": "bullish",
    "valuation_bucket": "cautious",
    "signals_rsi14": 64.0,
    "signals_fear_greed": 60,
    "signals_fear_greed_zone": "greed",
    "signals_intraday_close_position": "middle third",
    "what_changed_today": ["Breadth improved"],
    "narrative_summary": "Trend bullish but extended; hold and monitor.",
    "open_questions": ["Will VIX stay below 20?"],
    "decision_matrix_rows": _MATRIX_ROWS,
    "trim_signals_met": 1,
    "buy_signals_met": 0,
    "overall": "mixed",
    "confirming_evidence": ["50-day SMA remains above 200-day SMA"],
    "conflicting_evidence": [
        {
            "id": "extension_vs_valuation",
            "layers": ["technicals", "valuation"],
            "bullish_read": "Price trend remains bullish with momentum intact",
            "bearish_read": "Forward P/E in cautious bucket limits add aggression",
            "framework_rule": "Forward PE calibration — cautious bucket",
            "weight": "high",
            "chart_refs": ["01_chart.png"],
        }
    ],
    "primary_tension": "Bullish trend extension versus cautious valuation bucket",
    "mc_effective_threshold": 65,
    "mc_meets_threshold": False,
    "mc_prob_up_first_raw": 0.58,
    "mc_prob_down_first_raw": 0.42,
    "mc_prob_up_first_adjusted": 0.53,
    "mc_prob_down_first_adjusted": 0.47,
    "mc_sigma": 0.18,
    "mc_mu": 0.07,
    "mc_upside_target": 7500.0,
    "mc_downside_target": 7200.0,
    "mc_rally_exhaustion_score": "Moderate",
    "mc_conditional_cascade": "If 7200 breaks, P(7100)=76%",
    "mc_median_days": "upside 25d / downside 18d",
    "mc_drift_path": "5d=7445; 10d=7450",
    "mc_cash_drag_prob": 0.35,
}

_NESTED_SAMPLE = {
    "date": "2026-06-11",
    "framework_version": "daily-2026-06",
    "spx_close": 7440.0,
    "structural_bias": "Mid Bull",
    "base_case": "bullish_but_extended",
    "trend_regime": "bullish",
    "valuation_bucket": "cautious",
    "what_changed_today": ["Breadth improved"],
    "narrative_summary": "Trend bullish but extended; hold and monitor.",
    "open_questions": ["Will VIX stay below 20?"],
    "confirming_evidence": ["50-day SMA remains above 200-day SMA"],
    "conflicting_evidence": [
        {
            "id": "extension_vs_valuation",
            "layers": ["technicals", "valuation"],
            "bullish_read": "Price trend remains bullish with momentum intact",
            "bearish_read": "Forward P/E in cautious bucket limits add aggression",
            "framework_rule": "Forward PE calibration — cautious bucket",
            "weight": "high",
            "chart_refs": ["01_chart.png"],
        }
    ],
    "primary_tension": "Bullish trend extension versus cautious valuation bucket",
    "signals": {
        "rsi14": 64.0,
        "fear_greed": 60,
        "fear_greed_zone": "greed",
        "intraday_close_position": "middle third",
    },
    "monte_carlo": {
        "effective_threshold": 65,
        "meets_threshold": False,
        "prob_up_first_raw": 0.58,
        "prob_down_first_raw": 0.42,
        "prob_up_first_adjusted": 0.53,
        "prob_down_first_adjusted": 0.47,
        "sigma": 0.18,
        "mu": 0.07,
        "upside_target": 7500.0,
        "downside_target": 7200.0,
        "rally_exhaustion_score": "Moderate",
        "conditional_cascade": "If 7200 breaks, P(7100)=76%",
        "median_days": "upside 25d / downside 18d",
        "drift_path": "5d=7445; 10d=7450",
        "cash_drag_prob": 0.35,
    },
    "decision_matrix": {"rows": _MATRIX_ROWS},
    "signal_alignment": {
        "trim_signals_met": 1,
        "buy_signals_met": 0,
        "overall": "mixed",
    },
}


def test_daily_state_round_trip(sample_state):
    dumped = sample_state.model_dump(mode="json")
    assert DailyState.model_validate(dumped) == sample_state


def _manifest(charts, chart_count=None):
    return {
        "date": "2026-06-12",
        "index_symbol": "SPX",
        "close": 7450.25,
        "chart_count": chart_count if chart_count is not None else len(charts),
        "charts": charts,
    }


def test_manifest_valid():
    charts = [
        {"order": 1, "file": "a.png", "label": "A", "category": "technical"},
        {"order": 2, "file": "b.png", "label": "B", "category": "technical"},
    ]
    m = DailyManifest.model_validate(_manifest(charts))
    assert [c.order for c in m.ordered_charts()] == [1, 2]


def test_manifest_rejects_duplicate_order():
    charts = [
        {"order": 1, "file": "a.png", "label": "A", "category": "technical"},
        {"order": 1, "file": "b.png", "label": "B", "category": "technical"},
    ]
    with pytest.raises(ValidationError):
        DailyManifest.model_validate(_manifest(charts))


def test_manifest_rejects_noncontiguous_order():
    charts = [
        {"order": 1, "file": "a.png", "label": "A", "category": "technical"},
        {"order": 3, "file": "b.png", "label": "B", "category": "technical"},
    ]
    with pytest.raises(ValidationError):
        DailyManifest.model_validate(_manifest(charts))


def test_manifest_rejects_count_mismatch():
    charts = [{"order": 1, "file": "a.png", "label": "A", "category": "technical"}]
    with pytest.raises(ValidationError):
        DailyManifest.model_validate(_manifest(charts, chart_count=5))


# --- flat_to_nested mapper tests ------------------------------------------------


def test_flat_to_nested_full_conversion():
    nested = flat_to_nested(_FLAT_SAMPLE)
    assert nested == _NESTED_SAMPLE


def test_flat_to_nested_idempotent():
    assert flat_to_nested(_NESTED_SAMPLE) is _NESTED_SAMPLE
    assert flat_to_nested(_NESTED_SAMPLE) == _NESTED_SAMPLE


def test_flat_to_nested_missing_signals_group():
    minimal = {
        "date": "2026-06-11",
        "framework_version": "daily-2026-06",
        "spx_close": 7440.0,
        "structural_bias": "Mid Bull",
        "base_case": "a",
        "trend_regime": "b",
        "valuation_bucket": "c",
        "what_changed_today": [],
        "narrative_summary": ".",
        "open_questions": [],
        "confirming_evidence": [],
        "primary_tension": ".",
        "conflicting_evidence": [],
        "decision_matrix_rows": _MATRIX_ROWS,
        "trim_signals_met": 0,
        "buy_signals_met": 0,
        "overall": "neutral",
        "mc_effective_threshold": 65,
        "mc_meets_threshold": False,
        "mc_prob_up_first_raw": 0.5,
        "mc_prob_down_first_raw": 0.5,
        "mc_prob_up_first_adjusted": 0.5,
        "mc_prob_down_first_adjusted": 0.5,
        "mc_sigma": 0.15,
        "mc_mu": 0.07,
        "mc_upside_target": 7500.0,
        "mc_downside_target": 7300.0,
        "mc_rally_exhaustion_score": "Low",
        "mc_conditional_cascade": "none",
        "mc_median_days": "upside 3d / downside 4d",
        "mc_drift_path": "5d=7445",
        "mc_cash_drag_prob": 0.2,
    }
    nested = flat_to_nested(minimal)
    assert nested["signals"] == {}


def test_flat_to_nested_missing_mc_group():
    no_mc = dict(_FLAT_SAMPLE)
    for k in list(no_mc):
        if k.startswith("mc_"):
            del no_mc[k]
    nested = flat_to_nested(no_mc)
    assert nested["monte_carlo"] == {}


def test_flat_to_nested_missing_decision_matrix_rows():
    no_rows = dict(_FLAT_SAMPLE)
    del no_rows["decision_matrix_rows"]
    nested = flat_to_nested(no_rows)
    assert nested["decision_matrix"] == {"rows": []}


def test_flat_to_nested_preserves_non_prefixed_fields():
    extra = dict(_FLAT_SAMPLE)
    extra["unknown_field"] = "should_pass_through"
    nested = flat_to_nested(extra)
    assert nested["unknown_field"] == "should_pass_through"


def test_flat_to_nested_produces_valid_daily_state():
    nested = flat_to_nested(_FLAT_SAMPLE)
    state = DailyState.model_validate(nested)
    assert state.date == "2026-06-11"
    assert state.spx_close == 7440.0
    assert state.signals.rsi14 == 64.0
    assert state.monte_carlo.sigma == 0.18
    assert state.signal_alignment.overall == "mixed"


def test_emit_input_schema_no_nested_wrappers():
    schema = EmitDailyStateInput.model_json_schema()
    props = schema.get("properties", {})
    for wrapper in ("signals", "monte_carlo", "decision_matrix", "signal_alignment"):
        assert wrapper not in props, (
            f"EmitDailyStateInput schema should not contain '{wrapper}' property"
        )
    assert "signals_rsi14" in props
    assert "mc_sigma" in props
    assert "decision_matrix_rows" in props
    assert "trim_signals_met" in props


@pytest.mark.parametrize("field", ["signals", "monte_carlo", "decision_matrix", "signal_alignment"])
def test_emit_input_schema_no_defs_for_wrappers(field):
    """The JSON Schema $defs should not reference the four nested wrapper types."""
    schema = EmitDailyStateInput.model_json_schema()
    defs = schema.get("$defs", {})
    wrapper_type_names = {"SignalSet", "MonteCarloDetail", "DecisionMatrix", "SignalAlignment"}
    assert not (wrapper_type_names & set(defs.keys())), (
        f"Schema $defs should not contain nested wrapper types, got {list(defs.keys())}"
    )
