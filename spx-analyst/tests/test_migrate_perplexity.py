"""Tests for Perplexity history parsing and backfill pipeline."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.anthropic_client import CallResult
from src.memory import build_recent_summary
from src.migrate_perplexity import (
    FRAMEWORK_VERSION,
    RUN_LOG_SOURCE,
    MigrationError,
    build_migration_state_prompt,
    filter_sessions,
    migrate_session,
    parse_history,
)
from src.schemas import DailyState
from tests.conftest import SAMPLE_STATE, make_settings, write_eps_history
from tests.sample_analysis_context import sample_analysis_context

JUNE_10_SNIPPET = """\
---

# 📊 SPX Full 7-Step Analysis — Tuesday, June 10, 2026 | Close: 7,266.99

---

## Step 1 — Price Action: 23.6% Fib Broken, Correction Accelerating

SPX closed at 7,266.99, down −119.66 (−1.62%).

## Step 5 — Monte Carlo: 100,000 Paths, 60 Days

| Test | Probability |
| :-- | :-- |
| **P(Wave 1 7,696 first vs 38.2% Fib 7,151)** | **29.1% / 70.6%** |

**🎯 RECOMMENDED ACTION: HOLD SCHK — PREPARE ACTIVE RE-ENTRY DEPLOYMENT AT 7,151**

<span style="display:none">[^58_12]</span>

<div align="center">⁂</div>

[^58_1]: IMG_1058.jpeg
[^58_2]: IMG_1055.jpeg
"""


def test_parse_history_extracts_june_10(tmp_path: Path):
    path = tmp_path / "history.md"
    path.write_text(JUNE_10_SNIPPET, encoding="utf-8")
    sessions = parse_history(path)
    assert len(sessions) == 1
    s = sessions[0]
    assert s.date == "2026-06-10"
    assert s.spx_close == 7266.99
    assert "23.6% Fib Broken" in s.clean_markdown
    assert "IMG_1058.jpeg" not in s.clean_markdown
    assert "[^58_1]" not in s.clean_markdown


def test_filter_sessions_by_date_range(tmp_path: Path):
    path = tmp_path / "history.md"
    path.write_text(
        JUNE_10_SNIPPET
        + "\n---\n\n"
        + JUNE_10_SNIPPET.replace("June 10", "June 8").replace("7,266.99", "7,405.73"),
        encoding="utf-8",
    )
    sessions = parse_history(path)
    assert len(sessions) == 2
    filtered = filter_sessions(sessions, from_date="2026-06-10", to_date="2026-06-10")
    assert len(filtered) == 1
    assert filtered[0].date == "2026-06-10"


def test_parse_history_empty_raises(tmp_path: Path):
    path = tmp_path / "empty.md"
    path.write_text("# unrelated content\n", encoding="utf-8")
    with pytest.raises(MigrationError):
        parse_history(path)


def test_build_migration_state_prompt_uses_posture_snapshot():
    from src.migrate_perplexity import PerplexitySession, SessionContext

    session = PerplexitySession(
        date="2026-06-01",
        spx_close=7599.96,
        raw_markdown="",
        clean_markdown="Sample body",
        title_line="title",
    )
    ctx = SessionContext()
    analysis_context = sample_analysis_context("2026-06-01")
    recent = "### 2026-05-30\nMid Bull | mixed | action: hold and monitor"

    bundle = build_migration_state_prompt(
        framework="# Framework",
        system_role="# Role",
        session=session,
        ctx=ctx,
        analysis_context=analysis_context,
        recent_summary=recent,
    )
    assert "Prior posture snapshot" in bundle.body
    assert "Precomputed analysis context" in bundle.body
    assert "Historical Perplexity analysis" in bundle.body
    assert FRAMEWORK_VERSION in bundle.body
    assert "Recent historical memory" not in bundle.body


@patch("src.migrate_perplexity.rebuild_rolling_summary")
@patch("src.migrate_perplexity.run_precompute")
def test_migrate_session_applies_precompute(mock_precompute, mock_rebuild, tmp_path: Path):
    from src.files import scaffold_run_dir
    from src.migrate_perplexity import PerplexitySession

    settings = make_settings(tmp_path)
    write_eps_history(tmp_path)
    date = "2026-06-01"
    run_dir = settings.runs_dir / date
    scaffold_run_dir(run_dir, date)

    analysis_context = sample_analysis_context(date)
    mock_precompute.return_value = analysis_context

    session = PerplexitySession(
        date=date,
        spx_close=7599.96,
        raw_markdown=JUNE_10_SNIPPET,
        clean_markdown="Perplexity narrative",
        title_line="# title",
    )

    state_payload = dict(SAMPLE_STATE)
    state_payload["date"] = date
    state_payload["framework_version"] = FRAMEWORK_VERSION

    client = MagicMock()
    client.run_text_structured_state.return_value = CallResult(
        text=None,
        tool_input=state_payload,
        raw_response={},
        request_snapshot={"pass": 1},
    )
    client.run_text_markdown_report.return_value = CallResult(
        text="# Report\n\n## Structural Regime Classification\n",
        tool_input=None,
        raw_response={},
        request_snapshot={"pass": 2},
    )

    result = migrate_session(session, settings=settings, client=client)

    assert result.daily_state.framework_version == FRAMEWORK_VERSION
    assert result.daily_state.date == date
    mock_precompute.assert_called_once()
    mock_rebuild.assert_called_once()

    run_log = json.loads((result.output_dir / "run_log.json").read_text(encoding="utf-8"))
    assert run_log["source"] == RUN_LOG_SOURCE
    assert run_log["precompute_enforcement"]["applied"] is True
    assert (result.output_dir / "analysis_context.json").is_file()

    memory_state = settings.daily_states_dir / f"{date}-state.json"
    assert memory_state.is_file()
    saved = DailyState.model_validate(json.loads(memory_state.read_text(encoding="utf-8")))
    assert saved.framework_version == FRAMEWORK_VERSION


def test_migrated_state_produces_categorical_rollup(tmp_path: Path):
    from tests.conftest import write_state

    settings = make_settings(tmp_path)
    write_state(
        settings,
        "2026-06-01",
        structural_bias="Late Bull / Topping",
        signals={
            "rsi14": 42.0,
            "fear_greed": 27,
            "fear_greed_zone": "Fear",
            "vix_regime": "Elevated (15-20+)",
            "high_yield_spread": 1.37,
            "pct_vs_50dma": -0.64,
        },
    )
    summary = build_recent_summary(
        [DailyState.model_validate(json.loads((settings.daily_states_dir / "2026-06-01-state.json").read_text()))]
    )
    assert "7599" not in summary and "7266" not in summary
    assert "signals:" in summary
    assert "F&G" in summary or "fear" in summary.lower()
    assert "spx_close" not in summary
