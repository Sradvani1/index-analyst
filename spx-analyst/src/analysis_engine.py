"""Orchestrates a full daily run: ingest -> precompute -> two-pass Claude -> persist."""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass, field
from pathlib import Path

from . import files
from .anthropic_client import AnthropicClient
from .config import Settings, get_settings
from .eps_history import eps_resolution_log, require_eps_for_run
from .memory import (
    build_recent_summary,
    load_recent_states_with_stats,
    rebuild_rolling_summary,
)
from .pass2_images import Pass2ImagePlan, resolve_pass2_images
from .precompute import run_precompute
from .prompts import build_report_prompt, build_state_prompt, load_system_role
from .schemas import AnalysisContext, DailyState, ValidationIssue, ValidationReport
from .state_enforcement import apply_precomputed_fields, audit_enforcement_issues
from .validation import parse_daily_state, validate_report, validation_errors_text

logger = logging.getLogger(__name__)


class RunError(Exception):
    """Hard failure that aborts the run."""


@dataclass
class RunResult:
    date: str
    output_dir: Path
    daily_state: DailyState
    analysis_context: AnalysisContext
    report_path: Path
    state_validation: ValidationReport
    report_validation: ValidationReport
    warnings: list[str] = field(default_factory=list)


def run_daily_analysis(
    date: str,
    input_dir: str | None = None,
    *,
    settings: Settings | None = None,
    client: AnthropicClient | None = None,
    force_fetch: bool = False,
) -> RunResult:
    settings = settings or get_settings()
    started = dt.datetime.now(dt.timezone.utc).isoformat()
    warnings: list[str] = []

    framework = files.load_framework(settings)
    role_text = files.load_role(settings)
    system_role = load_system_role(role_text)

    run_dir = files.resolve_run_dir(date, input_dir, settings)
    manifest = files.load_manifest(run_dir)
    image_paths = files.chart_paths(run_dir, manifest)
    logger.info("loaded manifest for %s with %d charts", date, len(image_paths))

    eps, eps_resolution = require_eps_for_run(date, settings=settings)

    analysis_context = run_precompute(
        date,
        run_dir,
        manifest,
        eps,
        settings=settings,
        force_fetch=force_fetch,
    )
    warnings.extend(analysis_context.market_data.precompute_warnings)

    recent_summary: str | None = None
    memory_load: dict[str, int] | None = None
    if settings.include_memory:
        recent_states, mem_stats = load_recent_states_with_stats(
            before_date=date, settings=settings
        )
        recent_summary = build_recent_summary(recent_states)
        memory_load = {
            "requested": mem_stats.requested,
            "loaded": mem_stats.loaded,
            "skipped_invalid": mem_stats.skipped_invalid,
            "skipped_before_date": mem_stats.skipped_before_date,
        }
        if mem_stats.skipped_invalid > 0:
            warnings.append(
                f"memory load skipped {mem_stats.skipped_invalid} invalid prior state file(s)"
            )

    client = client or AnthropicClient(settings)

    state_bundle = build_state_prompt(
        system_role=system_role,
        framework=framework,
        manifest=manifest,
        resolved_eps=eps,
        analysis_context=analysis_context,
        recent_summary=recent_summary,
    )
    state_call = client.run_structured_state(state_bundle, image_paths)

    daily_state, state_validation = parse_daily_state(state_call.tool_input or {}, date)
    if daily_state is None:
        logger.warning("state failed validation; attempting one repair pass")
        repair_call = client.repair_structured_state(
            state_call.tool_input or {}, validation_errors_text(state_validation)
        )
        daily_state, state_validation = parse_daily_state(repair_call.tool_input or {}, date)
        if daily_state is None:
            files.save_outputs(
                date=date,
                daily_state=_placeholder_state(date, analysis_context),
                report_md="# Run failed: state validation\n\nSee validation_report.json.",
                request_snapshot=state_call.request_snapshot,
                response_raw=state_call.raw_response,
                run_log={"started": started, "status": "failed_state_validation"},
                validation_reports=[state_validation.model_dump(mode="json")],
                mirror_to_memory=False,
                settings=settings,
            )
            raise RunError(f"DailyState invalid after repair: {validation_errors_text(state_validation)}")

    daily_state, enforce_warnings = apply_precomputed_fields(daily_state, analysis_context)
    warnings.extend(enforce_warnings)
    state_validation = _merge_enforcement_audit(state_validation, enforce_warnings)

    pass2_plan = resolve_pass2_images(run_dir, manifest, daily_state, settings)
    attached_names = {p.name for p in pass2_plan.attached}
    pass2_attached_entries = [c for c in manifest.ordered_charts() if c.file in attached_names]
    for ref in pass2_plan.unresolved_chart_refs:
        warnings.append(ref.message)

    pass2_audit = _pass2_audit_payload(settings, pass2_plan, pass1_chart_count=len(image_paths))

    report_bundle = build_report_prompt(
        system_role=system_role,
        framework=framework,
        daily_state=daily_state,
        manifest=manifest,
        resolved_eps=eps,
        analysis_context=analysis_context,
        recent_summary=recent_summary,
        pass2_attached=pass2_attached_entries,
        pass2_reference_only=pass2_plan.reference_only,
        pass2_optimization_enabled=settings.pass2_image_optimization_enabled,
    )
    report_call = client.run_markdown_report(
        report_bundle, pass2_plan.attached, pass2_audit=pass2_audit
    )
    report_md = report_call.text or ""

    report_validation = validate_report(
        report_md, date, settings.max_report_chars, daily_state=daily_state
    )
    warnings.extend(i.message for i in report_validation.warnings)

    run_log: dict[str, object] = {
        "started": started,
        "finished": dt.datetime.now(dt.timezone.utc).isoformat(),
        "status": "ok",
        "chart_count": len(image_paths),
        "pass1_chart_count": len(image_paths),
        "pass2_chart_count": len(pass2_plan.attached),
        "pass2_image_optimization_enabled": settings.pass2_image_optimization_enabled,
        "pass2_image_max_dimension": settings.pass2_image_max_dimension,
        "pass2_charts_attached": [p.name for p in pass2_plan.attached],
        "pass2_charts_omitted": [c.file for c in pass2_plan.reference_only],
        "pass2_selection_reasons": pass2_plan.selection_reason,
        "pass2_unresolved_chart_refs": [
            {"original_ref": u.original_ref, "outcome": u.outcome, "message": u.message}
            for u in pass2_plan.unresolved_chart_refs
        ],
        "memory_included": settings.include_memory,
        "model": settings.model,
        "warnings": warnings,
        "precompute_enforcement": {
            "applied": True,
            "warnings": enforce_warnings,
        },
        "eps_resolution": eps_resolution_log(eps_resolution),
    }
    if memory_load is not None:
        run_log["memory_load"] = memory_load
    out = files.save_outputs(
        date=date,
        daily_state=daily_state,
        report_md=report_md,
        request_snapshot={
            "state_pass": state_call.request_snapshot,
            "report_pass": report_call.request_snapshot,
        },
        response_raw={
            "state_pass": state_call.raw_response,
            "report_pass": report_call.raw_response,
        },
        run_log=run_log,
        validation_reports=[
            state_validation.model_dump(mode="json"),
            report_validation.model_dump(mode="json"),
            {"target": "precompute_enforcement", "issues": audit_enforcement_issues(enforce_warnings)},
        ],
        settings=settings,
    )
    files.write_json(run_dir / files.ANALYSIS_CONTEXT_FILENAME, analysis_context)
    files.write_json(out / "analysis_context.json", analysis_context)

    rebuild_rolling_summary(settings=settings)

    return RunResult(
        date=date,
        output_dir=out,
        daily_state=daily_state,
        analysis_context=analysis_context,
        report_path=out / f"{date}-analysis.md",
        state_validation=state_validation,
        report_validation=report_validation,
        warnings=warnings,
    )


def _merge_enforcement_audit(
    report: ValidationReport,
    enforce_warnings: list[str],
) -> ValidationReport:
    issues = list(report.issues)
    for entry in audit_enforcement_issues(enforce_warnings):
        issues.append(ValidationIssue(**entry))
    return report.model_copy(update={"issues": issues})


def _pass2_audit_payload(
    settings: Settings, plan: Pass2ImagePlan, *, pass1_chart_count: int
) -> dict[str, object]:
    return {
        "pass1_chart_count": pass1_chart_count,
        "pass2_chart_count": len(plan.attached),
        "pass2_image_optimization_enabled": settings.pass2_image_optimization_enabled,
        "pass2_image_max_dimension": settings.pass2_image_max_dimension,
        "pass2_charts_attached": [p.name for p in plan.attached],
        "pass2_charts_omitted": [c.file for c in plan.reference_only],
        "pass2_selection_reasons": plan.selection_reason,
        "pass2_unresolved_chart_refs": [
            {"original_ref": u.original_ref, "outcome": u.outcome, "message": u.message}
            for u in plan.unresolved_chart_refs
        ],
    }


def _placeholder_state(date: str, ctx: AnalysisContext) -> DailyState:
    from .schemas import DecisionMatrix, DecisionMatrixRow, MonteCarloDetail, SignalAlignment, SignalSet

    mc = ctx.monte_carlo
    row65 = mc.threshold_evaluation["65"]
    return DailyState(
        date=date,
        framework_version="unknown",
        spx_close=ctx.market_data.spx_close,
        structural_bias="Mid Bull",
        base_case="unknown",
        trend_regime="unknown",
        valuation_bucket="unknown",
        signals=SignalSet(),
        what_changed_today=[],
        narrative_summary="Run failed before a valid state was produced.",
        open_questions=[],
        decision_matrix=DecisionMatrix(
            rows=[
                DecisionMatrixRow(
                    signal_layer="Recommended Action",
                    current_reading="none",
                    signal="none",
                )
            ]
        ),
        signal_alignment=SignalAlignment(
            trim_signals_met=0,
            buy_signals_met=0,
            overall="neutral",
        ),
        confirming_evidence=[],
        conflicting_evidence=[],
        primary_tension="Run failed before conflicts were classified.",
        monte_carlo=MonteCarloDetail(
            effective_threshold=65,
            meets_threshold=row65.actionable,
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
        ),
    )
