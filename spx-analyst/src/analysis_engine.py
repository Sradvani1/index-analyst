"""Orchestrates a full daily run: ingest -> context -> memory -> two-pass Claude
-> validate -> persist. Pure service callable from the CLI now and a web backend
later.
"""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass, field
from pathlib import Path

from . import files
from .anthropic_client import AnthropicClient
from .config import Settings, get_settings
from .external_data import load_external_context
from .memory import build_recent_summary, load_recent_states, rebuild_rolling_summary
from .prompts import build_report_prompt, build_state_prompt
from .schemas import DailyState, ValidationReport
from .validation import parse_daily_state, validate_report, validation_errors_text

logger = logging.getLogger(__name__)


class RunError(Exception):
    """Hard failure that aborts the run."""


@dataclass
class RunResult:
    date: str
    output_dir: Path
    daily_state: DailyState
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
) -> RunResult:
    settings = settings or get_settings()
    started = dt.datetime.now(dt.timezone.utc).isoformat()
    warnings: list[str] = []

    # Step 1-2: bootstrap + input validation
    framework = files.load_framework(settings)
    run_dir = files.resolve_run_dir(date, input_dir, settings)
    manifest = files.load_manifest(run_dir)
    image_paths = files.chart_paths(run_dir, manifest)
    logger.info("loaded manifest for %s with %d charts", date, len(image_paths))

    # Step 3: external context (user-supplied; never fetched)
    ext = load_external_context(date, run_dir, settings=settings)
    warnings.extend(ext.warnings)

    # Step 4: memory load (exclude today's own state on reruns)
    recent_states = load_recent_states(before_date=date, settings=settings)
    recent_summary = build_recent_summary(recent_states)

    client = client or AnthropicClient(settings)

    # Step 5: Pass 1 structured state
    state_bundle = build_state_prompt(
        framework=framework,
        manifest=manifest,
        external_context=ext.context,
        recent_states=recent_states,
        recent_summary=recent_summary,
    )
    state_call = client.run_structured_state(state_bundle, image_paths)

    # Step 6: JSON validation (+ one repair pass)
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
                daily_state=_placeholder_state(date, manifest),
                report_md="# Run failed: state validation\n\nSee validation_report.json.",
                request_snapshot=state_call.request_snapshot,
                response_raw=state_call.raw_response,
                run_log={"started": started, "status": "failed_state_validation"},
                validation_reports=[state_validation.model_dump(mode="json")],
                mirror_to_memory=False,
                settings=settings,
            )
            raise RunError(f"DailyState invalid after repair: {validation_errors_text(state_validation)}")

    # Step 7: Pass 2 markdown report
    report_bundle = build_report_prompt(
        framework=framework,
        daily_state=daily_state,
        manifest=manifest,
        external_context=ext.context,
        recent_states=recent_states,
        recent_summary=recent_summary,
    )
    report_call = client.run_markdown_report(report_bundle, image_paths)
    report_md = report_call.text or ""

    # Step 8: report validation
    report_validation = validate_report(report_md, date, settings.max_report_chars)
    warnings.extend(i.message for i in report_validation.warnings)

    # Step 9: finalize outputs + refresh rolling memory
    run_log = {
        "started": started,
        "finished": dt.datetime.now(dt.timezone.utc).isoformat(),
        "status": "ok",
        "chart_count": len(image_paths),
        "recent_states_used": len(recent_states),
        "model": settings.model,
        "warnings": warnings,
    }
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
        ],
        settings=settings,
    )
    rebuild_rolling_summary(settings=settings)

    return RunResult(
        date=date,
        output_dir=out,
        daily_state=daily_state,
        report_path=out / f"{date}-analysis.md",
        state_validation=state_validation,
        report_validation=report_validation,
        warnings=warnings,
    )


def _placeholder_state(date: str, manifest) -> DailyState:
    """Minimal valid state used only to persist artifacts on a failed run."""
    from .schemas import DecisionMatrix, SignalSet

    return DailyState(
        date=date,
        framework_version="unknown",
        spx_close=manifest.close,
        base_case="unknown",
        trend_regime="unknown",
        valuation_bucket="unknown",
        signals=SignalSet(),
        what_changed_today=[],
        narrative_summary="Run failed before a valid state was produced.",
        open_questions=[],
        decision_matrix=DecisionMatrix(
            valuation="unknown",
            technicals="unknown",
            sentiment="unknown",
            risk="unknown",
            recommended_action="none",
        ),
    )
