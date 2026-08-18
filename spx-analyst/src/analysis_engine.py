"""Orchestrates a full daily run: ingest -> precompute -> two-pass LLM -> persist."""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass, field
from pathlib import Path

from . import files
from .anthropic_client import AnthropicClient
from .config import Settings, get_settings
from .pipeline_client import PipelineLLMClient
from .eps_history import eps_resolution_log, load_eps_history, require_eps_for_run
from .memory import (
    build_recent_summary,
    build_structural_bias_arcs,
    load_all_states,
    load_recent_states_with_stats,
    rebuild_rolling_summary,
    rebuild_structural_bias_history,
    structural_bias_arc_prompt,
    one_year_before,
)
from .pass2_images import Pass2ImagePlan, resolve_pass2_images
from .precompute import run_precompute
from .prompts import build_report_prompt, build_state_prompt, load_system_role
from .report_assembly import assemble_investor_report, extract_prose_sections
from .schemas import AnalysisContext, DailyState, ValidationIssue, ValidationReport, flat_to_nested
from .state_enforcement import apply_precomputed_fields, audit_enforcement_issues
from .state_normalize import resolve_pass1_daily_state
from .validation import validate_report, validation_errors_text
from .substack import render_substack_html, render_substack_markdown

logger = logging.getLogger(__name__)


class RunError(Exception):
    """Hard failure that aborts the run."""


def _pipeline_model(settings: Settings) -> str:
    """Return the effective model name used by the selected pipeline provider."""
    provider = settings.llm_provider.strip().lower()
    if provider == "openai":
        return settings.openai_pipeline_model.strip() or "gpt-5.6-sol"
    if provider == "google":
        return settings.google_pipeline_model.strip() or "gemini-3.7-flash"
    return settings.model


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


def _resolve_pipeline_client(settings: Settings) -> PipelineLLMClient:
    """Return a pipeline client for the configured provider."""
    provider = settings.llm_provider.strip().lower()
    if provider == "openai":
        from .openai_pipeline_client import OpenAIPipelineClient, OpenAIPipelineError

        try:
            return OpenAIPipelineClient(settings)
        except OpenAIPipelineError as exc:
            raise RunError(str(exc)) from exc
    if provider == "google":
        from .google_pipeline_client import GooglePipelineClient, GooglePipelineError

        try:
            return GooglePipelineClient(settings)
        except GooglePipelineError as exc:
            raise RunError(str(exc)) from exc
    if provider != "anthropic":
        raise RunError(
            f"Unknown LLM provider: {settings.llm_provider!r}. "
            "Expected 'anthropic', 'openai', or 'google'."
        )
    return AnthropicClient(settings)


def run_daily_analysis(
    date: str,
    input_dir: str | None = None,
    *,
    settings: Settings | None = None,
    client: PipelineLLMClient | None = None,
    force_fetch: bool = False,
) -> RunResult:
    settings = settings or get_settings()
    started = dt.datetime.now(dt.timezone.utc).isoformat()
    warnings: list[str] = []
    client_injected = client is not None

    framework = files.load_framework(settings)
    role_text = files.load_role(settings)
    system_role = load_system_role(role_text)

    run_dir = files.resolve_run_dir(date, input_dir, settings)
    manifest = files.load_manifest(run_dir)
    image_paths = files.chart_paths(run_dir, manifest)
    logger.info("loaded manifest for %s with %d charts", date, len(image_paths))

    eps, eps_resolution = require_eps_for_run(date, settings=settings)
    eps_history = load_eps_history(settings)

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
    prior_bias_states = load_all_states(before_date=date, settings=settings)
    prior_bias_arc = structural_bias_arc_prompt(
        build_structural_bias_arcs(
            prior_bias_states,
            display_from=one_year_before(date),
        )
    )
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

    configured_provider = settings.llm_provider.strip().lower() or "default"
    resolved_provider: str
    if client is not None:
        resolved_provider = "injected"
    else:
        client = _resolve_pipeline_client(settings)
        provider_name = settings.llm_provider.strip().lower()
        resolved_provider = (
            provider_name
            if provider_name in ("anthropic", "openai", "google")
            else "unknown"
        )

    state_bundle = build_state_prompt(
        system_role=system_role,
        framework=framework,
        manifest=manifest,
        resolved_eps=eps,
        analysis_context=analysis_context,
        recent_summary=recent_summary,
        eps_history=eps_history,
        structural_bias_arc=prior_bias_arc,
    )
    state_call = client.run_structured_state(state_bundle, image_paths)
    nested_tool_input = flat_to_nested(state_call.tool_input or {})

    def _repair(invalid: dict, errors: str):
        repair_call = client.repair_structured_state(invalid, errors)
        return repair_call.tool_input or {}, repair_call.raw_response

    pass1 = resolve_pass1_daily_state(
        nested_tool_input,
        date,
        repair_fn=_repair,
    )
    daily_state = pass1.daily_state
    state_validation = pass1.validation
    if daily_state is None:
        files.save_outputs(
            date=date,
            daily_state=_placeholder_state(date, analysis_context),
            report_md="# Run failed: state validation\n\nSee validation_report.json.",
            request_snapshot=state_call.request_snapshot,
            response_raw=_pass1_response_raw(state_call, pass1),
            run_log={
                "started": started,
                "status": "failed_state_validation",
                "pass1_schema_status": pass1.pass1_schema_status(),
            },
            validation_reports=[state_validation.model_dump(mode="json")],
            mirror_to_memory=False,
            settings=settings,
        )
        raise RunError(f"DailyState invalid after repair: {validation_errors_text(state_validation)}")

    if pass1.normalized and not pass1.original_valid:
        warnings.append("Pass 1 state coalesced known signals drift before validation")
    if pass1.repair_triggered:
        logger.warning("state failed validation; attempted one repair pass")
        warnings.append("state required one repair pass")

    daily_state, enforce_warnings = apply_precomputed_fields(daily_state, analysis_context)
    warnings.extend(enforce_warnings)
    state_validation = _merge_enforcement_audit(state_validation, enforce_warnings)

    current_bias_states = prior_bias_states + [daily_state]
    current_bias_arc = structural_bias_arc_prompt(
        build_structural_bias_arcs(
            current_bias_states,
            display_from=one_year_before(date),
        )
    )

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
        eps_history=eps_history,
        structural_bias_arc=current_bias_arc,
    )
    report_call = client.run_markdown_report(
        report_bundle, pass2_plan.attached, pass2_audit=pass2_audit
    )
    report_prose = report_call.text or ""
    prose_section_count = len(extract_prose_sections(report_prose))
    report_md = assemble_investor_report(
        date=date,
        daily_state=daily_state,
        analysis_context=analysis_context,
        prose_md=report_prose,
    )

    report_validation = validate_report(
        report_md, date, settings.max_report_chars, daily_state=daily_state
    )
    warnings.extend(i.message for i in report_validation.warnings)
    if not report_validation.passed:
        warnings.extend(
            f"report validation [{issue.code}]: {issue.message}"
            for issue in report_validation.errors
        )

    substack_article = None
    substack_audit: dict[str, object] | None = None
    if not client_injected and hasattr(client, "run_substack_article"):
        substack_article, substack_audit = client.run_substack_article(
            daily_state, report_md
        )
        substack_md = render_substack_markdown(substack_article)
    else:
        warnings.append("Substack article skipped: selected pipeline has no editorial client")
        substack_md = None

    run_log: dict[str, object] = {
        "started": started,
        "finished": dt.datetime.now(dt.timezone.utc).isoformat(),
        "configured_provider": configured_provider,
        "resolved_provider": resolved_provider,
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
        "model": _pipeline_model(settings),
        "warnings": warnings,
        "precompute_enforcement": {
            "applied": True,
            "warnings": enforce_warnings,
        },
        "eps_resolution": eps_resolution_log(eps_resolution),
        "pass1_schema_status": pass1.pass1_schema_status(),
        "report_assembly": {
            "matrix_source": "daily_state",
            "prose_sections": prose_section_count,
            "prose_chars": len(report_prose),
            "assembled_chars": len(report_md),
        },
        "report_validation": report_validation.model_dump(mode="json"),
    }
    if substack_article is not None and substack_audit is not None:
        assert substack_md is not None
        telemetry = substack_audit.get("telemetry")
        if not isinstance(telemetry, dict):
            telemetry = {}
        run_log["substack"] = {
            "status": "ok",
            "title": substack_article.title,
            "word_count": len(substack_md.split()),
            "model": substack_audit["model"],
            "input_tokens": telemetry.get("input_tokens"),
            "output_tokens": telemetry.get("output_tokens"),
            "cache_read_tokens": telemetry.get("cache_read_tokens"),
            "latency_ms": telemetry.get("latency_ms"),
        }
    if memory_load is not None:
        run_log["memory_load"] = memory_load
    eps_sync_log = _load_eps_sync_log(run_dir)
    if eps_sync_log is not None:
        run_log["eps_sync"] = eps_sync_log
    out = files.save_outputs(
        date=date,
        daily_state=daily_state,
        report_md=report_md,
        request_snapshot={
            "state_pass": state_call.request_snapshot,
            "report_pass": report_call.request_snapshot,
        },
        response_raw=_pass1_response_raw(
            state_call, pass1, report_raw=report_call.raw_response, report_prose=report_prose
        ),
        run_log=run_log,
        validation_reports=[
            state_validation.model_dump(mode="json"),
            report_validation.model_dump(mode="json"),
            {"target": "precompute_enforcement", "issues": audit_enforcement_issues(enforce_warnings)},
        ],
        settings=settings,
    )
    if substack_md is not None:
        assert substack_article is not None
        files.write_text(out / f"{date}-substack.md", substack_md)
        files.write_text(settings.daily_reports_dir / f"{date}-substack.md", substack_md)
        files.write_text(
            out / f"{date}-substack.html",
            render_substack_html(substack_article),
        )
        files.write_text(
            settings.daily_reports_dir / f"{date}-substack.html",
            render_substack_html(substack_article),
        )
    else:
        for directory in (out, settings.daily_reports_dir):
            (directory / f"{date}-substack.md").unlink(missing_ok=True)
            (directory / f"{date}-substack.html").unlink(missing_ok=True)
    files.write_json(run_dir / files.ANALYSIS_CONTEXT_FILENAME, analysis_context)
    files.write_json(out / "analysis_context.json", analysis_context)

    rebuild_rolling_summary(settings=settings)
    rebuild_structural_bias_history(as_of_date=date, settings=settings)

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


def _pass1_response_raw(
    state_call,
    pass1,
    *,
    report_raw: dict | None = None,
    report_prose: str | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "state_pass": state_call.raw_response,
        "state_pass_original": state_call.tool_input or {},
    }
    if pass1.normalized:
        payload["state_pass_normalized"] = pass1.normalized_tool_input
    if pass1.repair_triggered and pass1.repair_raw_response is not None:
        payload["repair_pass"] = pass1.repair_raw_response
    if report_raw is not None:
        payload["report_pass"] = report_raw
    if report_prose is not None:
        payload["report_pass_prose"] = report_prose
    return payload


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


def _load_eps_sync_log(run_dir: Path) -> dict[str, object] | None:
    path = run_dir / files.EPS_SOURCE_FILENAME
    if not path.is_file():
        return None
    try:
        payload = files.read_json(path)
    except files.InputError as exc:
        logger.warning("could not read EPS sync artifact %s: %s", path, exc)
        return None
    return payload if isinstance(payload, dict) else None


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
