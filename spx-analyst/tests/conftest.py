"""Shared pytest fixtures."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image

from src.config import Settings
from src.schemas import DailyState

SAMPLE_STATE = {
    "date": "2026-06-11",
    "framework_version": "2026-05-12",
    "spx_close": 7440.0,
    "schk_close": 28.0,
    "base_case": "bullish_but_extended",
    "trend_regime": "bullish",
    "valuation_bucket": "cautious",
    "signals": {"vix": 18.4, "rsi14": 64.0, "fear_greed": 60, "fear_greed_zone": "greed"},
    "what_changed_today": ["Breadth improved"],
    "narrative_summary": "Trend bullish but extended; hold and monitor.",
    "open_questions": ["Will VIX stay below 20?"],
    "decision_matrix": {
        "valuation": "cautious",
        "technicals": "bullish_but_stretched",
        "sentiment": "greed",
        "risk": "moderate",
        "recommended_action": "hold_and_monitor",
    },
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
            "framework_rule": "Forward P/E calibration table — cautious bucket",
            "weight": "high",
            "chart_refs": ["01_chart.png"],
        }
    ],
    "primary_tension": "Bullish trend extension versus cautious valuation bucket",
    "monte_carlo": {
        "prob_up_first": 0.58,
        "prob_down_first": 0.42,
        "conditional_cascade": "Moderate upside lean if resistance holds",
        "median_days": "~25 days to upside target",
        "cash_drag_prob": 0.35,
        "meets_threshold": False,
    },
}


def make_settings(tmp_path: Path) -> Settings:
    """Settings pointing all paths into a temp directory."""
    framework = tmp_path / "framework" / "method.md"
    framework.parent.mkdir(parents=True, exist_ok=True)
    framework.write_text("# Methodology\nRules.\n", encoding="utf-8")
    return Settings(
        anthropic_api_key="test",
        framework_path_raw=str(framework),
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
        "instrument_symbol": "SCHK",
        "close": 7450.25,
        "chart_count": n,
        "charts": entries,
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return run_dir
