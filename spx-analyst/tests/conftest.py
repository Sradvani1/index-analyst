"""Shared pytest fixtures."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image

from src.config import Settings
from src.schemas import DailyState
from src.prompts import DECISION_MATRIX_ROWS

MATRIX_ROWS = [
    {"signal_layer": layer, "current_reading": "n/a", "signal": "n/a"}
    for layer in DECISION_MATRIX_ROWS[:-1]
]
MATRIX_ROWS.append(
    {
        "signal_layer": "Recommended Action",
        "current_reading": "hold_and_monitor",
        "signal": "hold_and_monitor",
    }
)

SAMPLE_STATE = {
    "date": "2026-06-11",
    "framework_version": "daily-2026-06",
    "spx_close": 7440.0,
    "structural_bias": "Mid Bull",
    "base_case": "bullish_but_extended",
    "trend_regime": "bullish",
    "valuation_bucket": "cautious",
    "signals": {
        "rsi14": 64.0,
        "fear_greed": 60,
        "fear_greed_zone": "greed",
        "intraday_close_position": "middle third",
    },
    "what_changed_today": ["Breadth improved"],
    "narrative_summary": "Trend bullish but extended; hold and monitor.",
    "open_questions": ["Will VIX stay below 20?"],
    "decision_matrix": {"rows": MATRIX_ROWS},
    "signal_alignment": {
        "trim_signals_met": 1,
        "buy_signals_met": 0,
        "overall": "mixed",
    },
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
}


def make_settings(tmp_path: Path) -> Settings:
    fw_dir = tmp_path / "framework"
    fw_dir.mkdir(parents=True, exist_ok=True)
    framework = fw_dir / "framework.md"
    framework.write_text("# SPX Daily Analysis Framework\n", encoding="utf-8")
    role = fw_dir / "role.md"
    role.write_text("# SPX Claude Role Block\n", encoding="utf-8")
    return Settings(
        anthropic_api_key="test",
        framework_path_raw=str(framework),
        role_path_raw=str(role),
        data_dir_raw=str(tmp_path / "data"),
        memory_dir_raw=str(tmp_path / "memory"),
        output_dir_raw=str(tmp_path / "output"),
    )


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return make_settings(tmp_path)


@pytest.fixture
def sample_state() -> DailyState:
    return DailyState.model_validate(SAMPLE_STATE)


def write_state(settings: Settings, date: str, **overrides) -> None:
    data = dict(SAMPLE_STATE)
    data["date"] = date
    data.update(overrides)
    path = settings.daily_states_dir / f"{date}-state.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def build_run_dir(tmp_path: Path, date: str = "2026-06-12", n: int = 3) -> Path:
    run_dir = tmp_path / "runs" / date
    charts = run_dir / "charts"
    charts.mkdir(parents=True, exist_ok=True)
    entries = []
    for i in range(1, n + 1):
        fname = f"{i:02d}_chart.png"
        Image.new("RGB", (32, 32), color=(i * 10, i * 10, i * 10)).save(charts / fname)
        entries.append(
            {"order": i, "file": fname, "label": f"Chart {i}", "category": "technical"}
        )
    manifest = {
        "date": date,
        "index_symbol": "SPX",
        "close": 7450.25,
        "chart_count": n,
        "charts": entries,
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    ext = {
        "date": date,
        "forward_eps": 354.0,
        "trailing_eps": 220.0,
    }
    (run_dir / "external_context.json").write_text(json.dumps(ext), encoding="utf-8")
    return run_dir
