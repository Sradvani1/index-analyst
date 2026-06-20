from src.prompts import (
    DECISION_MATRIX_ROWS,
    PRE_STEP,
    WORKFLOW_STEPS,
    _analysis_context_block,
    build_report_prompt,
    build_state_prompt,
    load_system_role,
)
from src.schemas import DailyManifest, ExternalContext

from tests.sample_analysis_context import sample_analysis_context


def _manifest():
    return DailyManifest.model_validate(
        {
            "date": "2026-06-12",
            "index_symbol": "SPX",
            "close": 7450.25,
            "chart_count": 1,
            "charts": [{"order": 1, "file": "a.png", "label": "SPX daily", "category": "technical"}],
        }
    )


def _context():
    return ExternalContext(date="2026-06-12", forward_eps=354.0, trailing_eps=220.0)


def test_state_prompt_contains_blocks(sample_state):
    role = load_system_role("You are an SPX analyst.")
    ac = sample_analysis_context()
    bundle = build_state_prompt(
        system_role=role,
        framework="FRAMEWORK_TEXT",
        manifest=_manifest(),
        external_context=_context(),
        analysis_context=ac,
        recent_summary="prior summary",
    )
    assert bundle.framework == "FRAMEWORK_TEXT"
    assert "never force" in bundle.system_role.lower() or "hold and monitor" in bundle.system_role.lower()
    assert "analysis_context" in bundle.body
    assert "emit_daily_state" in bundle.body
    assert "structural_bias" in bundle.body
    assert "prior summary" in bundle.body
    assert "Prior posture snapshot" in bundle.body
    assert "Optional prior-run narrative context" not in bundle.body
    assert "7450.25" in bundle.body


def test_memory_block_absent_when_none(sample_state):
    """Memory block omitted when recent_summary is None (covers include_memory=false path)."""
    role = load_system_role("Role.")
    ac = sample_analysis_context()
    for builder in (build_state_prompt, build_report_prompt):
        kwargs = dict(
            system_role=role,
            framework="FW",
            manifest=_manifest(),
            external_context=_context(),
            analysis_context=ac,
            recent_summary=None,
        )
        if builder is build_report_prompt:
            kwargs["daily_state"] = sample_state
        bundle = builder(**kwargs)
        assert "Prior posture snapshot" not in bundle.body
        assert "Optional prior-run narrative context" not in bundle.body


def test_report_prompt_lists_steps_and_matrix(sample_state):
    role = load_system_role("Role.")
    ac = sample_analysis_context()
    bundle = build_report_prompt(
        system_role=role,
        framework="FW",
        daily_state=sample_state,
        manifest=_manifest(),
        external_context=_context(),
        analysis_context=ac,
        recent_summary=None,
    )
    assert PRE_STEP in bundle.body
    for step in WORKFLOW_STEPS:
        assert step in bundle.body
    for row in DECISION_MATRIX_ROWS:
        assert row in bundle.body
    assert "Updated Decision Matrix" in bundle.body
    assert "Evidence Reconciliation" in bundle.body
    assert sample_state.primary_tension in bundle.body


def test_system_role_has_precompute_authority():
    role = load_system_role("You are an SPX analyst.").lower()
    assert "sole numeric source of truth" in role
    assert "never recompute" in role


def test_state_prompt_reduced_numeric_load():
    bundle = build_state_prompt(
        system_role=load_system_role("R"),
        framework="FW",
        manifest=_manifest(),
        external_context=_context(),
        analysis_context=sample_analysis_context(),
        recent_summary=None,
    )
    # Injected threshold map and explicit spx_close step are gone.
    assert '"Late Bull / Topping": 70' not in bundle.body
    assert "from analysis_context.market_data.spx_close" not in bundle.body
    # Precompute-owned rows get a placeholder instead of reasoned numbers.
    assert "(engine-filled)" in bundle.body


def test_report_prompt_exposition_lock_and_divergence_ids(sample_state):
    bundle = build_report_prompt(
        system_role=load_system_role("R"),
        framework="FW",
        daily_state=sample_state,
        manifest=_manifest(),
        external_context=_context(),
        analysis_context=sample_analysis_context(),
        recent_summary=None,
    )
    body = bundle.body.lower()
    assert "not re-deciding" in body
    assert "by its id" in body


def test_analysis_context_block_rounds_floats():
    ctx = sample_analysis_context()
    ctx = ctx.model_copy(
        update={"market_data": ctx.market_data.model_copy(update={"spx_close": 7266.990234375})}
    )
    block = _analysis_context_block(ctx)
    assert "7266.990234375" not in block
    assert "7266.99" in block
