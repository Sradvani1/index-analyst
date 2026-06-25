from src.prompts import (
    EVIDENCE_AND_TENSIONS_HEADING,
    INVESTOR_REPORT_SECTIONS,
    PASS2_PROSE_SECTIONS,
    _analysis_context_block,
    build_report_prompt,
    build_state_prompt,
    load_system_role,
)
from src.schemas import DailyManifest, ResolvedEps

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
    return ResolvedEps(forward_eps=354.0, trailing_eps=220.0, effective_from="2026-06-12")


def test_state_prompt_contains_blocks(sample_state):
    role = load_system_role("You are an SPX analyst.")
    ac = sample_analysis_context()
    bundle = build_state_prompt(
        system_role=role,
        framework="FRAMEWORK_TEXT",
        manifest=_manifest(),
        resolved_eps=_context(),
        analysis_context=ac,
        recent_summary="prior summary",
    )
    assert bundle.framework == "FRAMEWORK_TEXT"
    assert "never force" in bundle.system_role.lower() or "hold and monitor" in bundle.system_role.lower()
    assert "analysis_context" in bundle.body
    assert "resolved from master history" in bundle.body
    assert "emit_daily_state" in bundle.body
    assert "structural_bias" in bundle.body
    assert "prior summary" in bundle.body
    assert "Prior posture snapshot" in bundle.body
    assert "Optional prior-run narrative context" not in bundle.body
    assert "7450.25" in bundle.body
    assert "signals` contract" in bundle.body
    assert "vix_regime_detail" in bundle.body
    assert "put_call_zone" in bundle.body
    assert "`what_changed_today` contract" in bundle.body
    assert "Must be a JSON array of 3–5 strings" in bundle.body
    assert "conflicting_evidence" in bundle.body
    assert "rsi_divergence" in bundle.body


def test_daily_state_schema_includes_list_field_descriptions():
    from src.schemas import DailyState

    props = DailyState.model_json_schema()["properties"]
    for field in ("what_changed_today", "open_questions"):
        assert "description" in props[field]
        assert props[field]["description"]


def test_signal_set_schema_includes_field_descriptions():
    from src.schemas import DailyState

    props = DailyState.model_json_schema()["$defs"]["SignalSet"]["properties"]
    for field in ("vix_regime", "fear_greed_zone", "put_call"):
        assert "description" in props[field]
        assert props[field]["description"]


def test_memory_block_absent_when_none(sample_state):
    """Memory block omitted when recent_summary is None (covers include_memory=false path)."""
    role = load_system_role("Role.")
    ac = sample_analysis_context()
    for builder in (build_state_prompt, build_report_prompt):
        kwargs = dict(
            system_role=role,
            framework="FW",
            manifest=_manifest(),
            resolved_eps=_context(),
            analysis_context=ac,
            recent_summary=None,
        )
        if builder is build_report_prompt:
            kwargs["daily_state"] = sample_state
        bundle = builder(**kwargs)
        assert "Prior posture snapshot" not in bundle.body
        assert "Optional prior-run narrative context" not in bundle.body


def test_report_prompt_lists_investor_sections(sample_state):
    role = load_system_role("Role.")
    ac = sample_analysis_context()
    bundle = build_report_prompt(
        system_role=role,
        framework="FW",
        daily_state=sample_state,
        manifest=_manifest(),
        resolved_eps=_context(),
        analysis_context=ac,
        recent_summary=None,
    )
    for title in PASS2_PROSE_SECTIONS:
        assert title in bundle.body
    assert "Updated Decision Matrix" in bundle.body
    assert "Do NOT emit" in bundle.body
    assert EVIDENCE_AND_TENSIONS_HEADING in bundle.body
    assert "Evidence Reconciliation" not in bundle.body
    assert sample_state.primary_tension in bundle.body
    assert "Read-only fact snippets" in bundle.body
    assert len(PASS2_PROSE_SECTIONS) == 8
    assert len(INVESTOR_REPORT_SECTIONS) == 9


def test_system_role_pass_split_constraints():
    role = load_system_role("You are an SPX analyst.").lower()
    assert "pass 1:" in role
    assert "pass 2:" in role
    assert "evidence and tensions" in role
    assert "always end with the updated decision matrix" not in role


def test_system_role_has_precompute_authority():
    role = load_system_role("You are an SPX analyst.").lower()
    assert "sole numeric source of truth" in role
    assert "never recompute" in role


def test_state_prompt_reduced_numeric_load():
    bundle = build_state_prompt(
        system_role=load_system_role("R"),
        framework="FW",
        manifest=_manifest(),
        resolved_eps=_context(),
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
        resolved_eps=_context(),
        analysis_context=sample_analysis_context(),
        recent_summary=None,
    )
    body = bundle.body.lower()
    assert "not re-deciding" in body
    assert "investor-facing" in body
    assert "conflicting_evidence" in body
    assert "evidence and tensions headings" not in body
    assert "snake_case" not in body
    assert "do not call tools" in body
    assert "emit_daily_state" in body


def test_analysis_context_block_rounds_floats():
    ctx = sample_analysis_context()
    ctx = ctx.model_copy(
        update={"market_data": ctx.market_data.model_copy(update={"spx_close": 7266.990234375})}
    )
    block = _analysis_context_block(ctx)
    assert "7266.990234375" not in block
    assert "7266.99" in block


def test_report_prompt_pass2_attached_reference_block(sample_state):
    manifest = DailyManifest.model_validate(
        {
            "date": "2026-06-12",
            "index_symbol": "SPX",
            "close": 7450.25,
            "chart_count": 2,
            "charts": [
                {"order": 1, "file": "a.png", "label": "Attached chart", "category": "technical"},
                {
                    "order": 2,
                    "file": "b.png",
                    "label": "Reference chart",
                    "category": "credit",
                },
            ],
        }
    )
    attached = [manifest.charts[0]]
    reference = [manifest.charts[1]]
    bundle = build_report_prompt(
        system_role=load_system_role("R"),
        framework="FW",
        daily_state=sample_state,
        manifest=manifest,
        resolved_eps=_context(),
        analysis_context=sample_analysis_context(),
        recent_summary="prior summary",
        pass2_attached=attached,
        pass2_reference_only=reference,
        pass2_optimization_enabled=True,
    )
    assert "Pass 2 chart pack" in bundle.body
    assert "Attached images (1)" in bundle.body
    assert "Reference only (not attached)" in bundle.body
    assert "a.png" in bundle.body
    assert "b.png" in bundle.body
    assert "validated daily state is authoritative" in bundle.body.lower()
    assert "Prior posture snapshot" in bundle.body
    assert "prior summary" in bundle.body
    assert "Today's chart pack (images attached in this order)" not in bundle.body
    assert "Do NOT infer fresh numeric values" in bundle.body


def test_report_prompt_pass2_body_order(sample_state):
    manifest = _manifest()
    bundle = build_report_prompt(
        system_role=load_system_role("R"),
        framework="FW",
        daily_state=sample_state,
        manifest=manifest,
        resolved_eps=_context(),
        analysis_context=sample_analysis_context(),
        recent_summary="snap",
        pass2_attached=manifest.charts,
        pass2_reference_only=[],
        pass2_optimization_enabled=True,
    )
    body = bundle.body
    assert body.index("Prior posture snapshot") < body.index("Precomputed analysis context")
    assert body.index("Precomputed analysis context") < body.index("Pass 2 chart pack")
    assert body.index("Pass 2 chart pack") < body.index("Validated daily state")
    assert body.index("Validated daily state") < body.index("Conflict checklist")
    assert body.index("Conflict checklist") < body.index("## Task")
