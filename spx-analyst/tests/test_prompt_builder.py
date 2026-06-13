from src.prompts import (
    DECISION_MATRIX_ROWS,
    WORKFLOW_STEPS,
    build_report_prompt,
    build_state_prompt,
)
from src.schemas import (
    DailyManifest,
    ExternalContext,
    FearGreedComponents,
    MetricReading,
)


def _manifest():
    return DailyManifest.model_validate(
        {
            "date": "2026-06-12",
            "index_symbol": "SPX",
            "instrument_symbol": "SCHK",
            "close": 7450.25,
            "chart_count": 1,
            "charts": [{"order": 1, "file": "a.png", "label": "SPX daily", "category": "technical"}],
        }
    )


def _context():
    return ExternalContext(
        date="2026-06-12",
        forward_eps=300.0,
        fear_greed_components=FearGreedComponents(
            market_volatility=MetricReading(value=18.4, reading="neutral")
        ),
    )


def test_state_prompt_contains_blocks(sample_state):
    bundle = build_state_prompt(
        framework="FRAMEWORK_TEXT",
        manifest=_manifest(),
        external_context=_context(),
        recent_states=[sample_state],
        recent_summary="prior summary",
    )
    assert bundle.framework == "FRAMEWORK_TEXT"
    assert "no forced" in bundle.system_role.lower() or "never force" in bundle.system_role.lower()
    assert "emit_daily_state" in bundle.body
    assert "prior summary" in bundle.body
    assert "SPX daily" in bundle.body
    assert "18.4" in bundle.body


def test_report_prompt_lists_steps_and_matrix(sample_state):
    bundle = build_report_prompt(
        framework="FW",
        daily_state=sample_state,
        manifest=_manifest(),
        external_context=_context(),
        recent_states=[],
        recent_summary="none",
    )
    for step in WORKFLOW_STEPS:
        assert step in bundle.body
    for row in DECISION_MATRIX_ROWS:
        assert row in bundle.body
    assert "Updated Decision Matrix" in bundle.body
