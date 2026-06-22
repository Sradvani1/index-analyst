"""Migrate historical Perplexity daily analyses into engine artifacts.

Parses standalone Full 7-Step sessions from an exported markdown history file,
converts each to schema-valid DailyState JSON and a normalized analysis report,
and writes canonical output/ + memory/ files.

Backfill path (no chart packs): Step 0 precompute + apply_precomputed_fields +
text-only Pass 1/2 with Perplexity markdown as qualitative evidence.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

from . import files
from .anthropic_client import AnthropicClient
from .config import Settings, get_settings
from .eps_history import EpsResolution, eps_resolution_log, get_eps_for_run, require_eps_for_run
from .files import (
    ANALYSIS_CONTEXT_FILENAME,
    MANIFEST_FILENAME,
    read_json,
    scaffold_run_dir,
    write_json,
)
from .memory import (
    build_recent_summary,
    load_recent_states_with_stats,
    rebuild_rolling_summary,
)
from .precompute import run_precompute
from .prompts import (
    DECISION_MATRIX_ROWS,
    EVIDENCE_RECONCILIATION_HEADING,
    HARD_CONSTRAINTS,
    PRECOMPUTE_OWNED_MATRIX_ROWS,
    PRE_STEP,
    WORKFLOW_STEPS,
    PromptBundle,
    _analysis_context_block,
    _optional_memory_block,
    load_system_role,
)
from .schemas import (
    AnalysisContext,
    DailyManifest,
    DailyState,
    ResolvedEps,
    ValidationIssue,
    ValidationReport,
)
from .state_enforcement import apply_precomputed_fields, audit_enforcement_issues
from .validation import parse_daily_state, validate_report, validation_errors_text

logger = logging.getLogger(__name__)

FRAMEWORK_VERSION = "daily-2026-06"
RUN_LOG_SOURCE = "perplexity_backfill"

SESSION_HEADER_RE = re.compile(
    r"^#\s*📊\s*SPX Full 7-Step Analysis —\s*.+?,\s*"
    r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+"
    r"(\d{1,2}),\s*(\d{4})\s*\|\s*Close:\s*([\d,]+\.?\d*)",
    re.MULTILINE,
)

_MONTHS = {
    "January": 1,
    "February": 2,
    "March": 3,
    "April": 4,
    "May": 5,
    "June": 6,
    "July": 7,
    "August": 8,
    "September": 9,
    "October": 10,
    "November": 11,
    "December": 12,
}

_FOOTNOTE_BLOCK_RE = re.compile(
    r"(?:<span style=\"display:none\">.*?</span>\s*)?"
    r"(?:<div align=\"center\">⁂</div>\s*)?"
    r"(?:\[\^[^\]]+\]:.*\n?)+$",
    re.DOTALL,
)


@dataclass
class PerplexitySession:
    date: str
    spx_close: float
    raw_markdown: str
    clean_markdown: str
    title_line: str


@dataclass
class SessionContext:
    manifest: DailyManifest | None = None
    resolved_eps: ResolvedEps | None = None
    chart_ref_map: dict[str, str] = field(default_factory=dict)


@dataclass
class MigrationResult:
    date: str
    daily_state: DailyState
    report_md: str
    state_validation: ValidationReport
    report_validation: ValidationReport
    output_dir: Path
    analysis_context: AnalysisContext
    warnings: list[str] = field(default_factory=list)


class MigrationError(Exception):
    pass


def _parse_close(value: str) -> float:
    return float(value.replace(",", ""))


def _to_iso(month_name: str, day: str, year: str) -> str:
    month = _MONTHS[month_name]
    return dt.date(int(year), month, int(day)).isoformat()


def _clean_body(markdown: str) -> str:
    text = markdown.strip()
    text = _FOOTNOTE_BLOCK_RE.sub("", text).strip()
    text = re.sub(r"\[\^[^\]]+\]", "", text)
    return text.strip()


def parse_history(path: Path) -> list[PerplexitySession]:
    """Split the export into standalone Full 7-Step sessions."""
    content = path.read_text(encoding="utf-8")
    matches = list(SESSION_HEADER_RE.finditer(content))
    if not matches:
        raise MigrationError(f"no Full 7-Step sessions found in {path}")

    sessions: list[PerplexitySession] = []
    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        block = content[start:end].strip()
        date = _to_iso(match.group(1), match.group(2), match.group(3))
        close = _parse_close(match.group(4))
        title_line = match.group(0).strip()
        sessions.append(
            PerplexitySession(
                date=date,
                spx_close=close,
                raw_markdown=block,
                clean_markdown=_clean_body(block),
                title_line=title_line,
            )
        )
    return sessions


def filter_sessions(
    sessions: list[PerplexitySession],
    *,
    from_date: str | None = None,
    to_date: str | None = None,
) -> list[PerplexitySession]:
    filtered = sessions
    if from_date:
        filtered = [s for s in filtered if s.date >= from_date]
    if to_date:
        filtered = [s for s in filtered if s.date <= to_date]
    return sorted(filtered, key=lambda s: s.date)


def load_session_context(date: str, settings: Settings | None = None) -> SessionContext:
    """Attach manifest and resolved EPS when a run directory exists."""
    settings = settings or get_settings()
    run_dir = settings.runs_dir / date
    if not run_dir.is_dir():
        return SessionContext()

    manifest = None
    chart_map: dict[str, str] = {}

    manifest_path = run_dir / MANIFEST_FILENAME
    if manifest_path.exists():
        manifest = DailyManifest.model_validate(read_json(manifest_path))
        for entry in manifest.ordered_charts():
            chart_map[entry.label.lower()] = entry.file

    resolution = get_eps_for_run(date, settings=settings)

    return SessionContext(
        manifest=manifest,
        resolved_eps=resolution.eps,
        chart_ref_map=chart_map,
    )


def _patch_manifest_close(run_dir: Path, session: PerplexitySession) -> None:
    manifest_path = run_dir / MANIFEST_FILENAME
    if not manifest_path.exists():
        return
    raw = read_json(manifest_path)
    if raw.get("close", 0) == 0:
        raw["close"] = session.spx_close
        write_json(manifest_path, raw)


def _prepare_session_precompute(
    session: PerplexitySession,
    settings: Settings,
    *,
    force_fetch: bool = False,
) -> tuple[AnalysisContext, SessionContext, EpsResolution]:
    """Scaffold run dir, require EPS, run Step 0 precompute for the session date."""
    run_dir = settings.runs_dir / session.date
    scaffold_run_dir(run_dir, session.date)

    eps, eps_resolution = require_eps_for_run(session.date, settings=settings)

    _patch_manifest_close(run_dir, session)
    manifest = files.load_manifest(run_dir)
    analysis_context = run_precompute(
        session.date,
        run_dir,
        manifest,
        eps,
        settings=settings,
        force_fetch=force_fetch,
    )
    write_json(run_dir / ANALYSIS_CONTEXT_FILENAME, analysis_context)

    ctx = load_session_context(session.date, settings)
    return analysis_context, ctx, eps_resolution


def _session_metadata_block(session: PerplexitySession, ctx: SessionContext) -> str:
    lines = [
        "## Session metadata",
        f"Date: {session.date}",
        f"SPX close (Perplexity header, reference only): {session.spx_close}",
        f"framework_version: {FRAMEWORK_VERSION}",
        f"source: {RUN_LOG_SOURCE}",
    ]
    if ctx.manifest:
        lines.append(f"Manifest close: {ctx.manifest.close}")
        lines.append("Chart filenames (use in chart_refs when applicable):")
        for c in ctx.manifest.ordered_charts():
            lines.append(f"  - {c.file}: {c.label}")
    if ctx.resolved_eps:
        lines.append(
            "## EPS inputs (resolved from master history)\n```json\n"
            + json.dumps(ctx.resolved_eps.model_dump(mode="json"), indent=2)
            + "\n```"
        )
    return "\n".join(lines)


def build_migration_state_prompt(
    *,
    framework: str,
    system_role: str,
    session: PerplexitySession,
    ctx: SessionContext,
    analysis_context: AnalysisContext,
    recent_summary: str,
) -> PromptBundle:
    steps = "\n".join(f"{i + 1}. {s}" for i, s in enumerate(WORKFLOW_STEPS))
    pre = f"0. {PRE_STEP}\n" + steps
    owned_rows = ", ".join(PRECOMPUTE_OWNED_MATRIX_ROWS)
    memory = _optional_memory_block(recent_summary)
    parts = [
        _analysis_context_block(analysis_context),
        _session_metadata_block(session, ctx),
        (
            "## Historical Perplexity analysis (qualitative evidence)\n"
            "Extract qualitative state from facts stated below. "
            "Do NOT invent signals or divergences not present in the text. "
            "Use null for any signal you cannot determine.\n\n"
            f"{session.clean_markdown}"
        ),
        (
            "## Task\n"
            "Convert this historical Perplexity report into one `emit_daily_state` tool call.\n\n"
            f"Complete `{PRE_STEP}` first, then the Daily 7-Step Workflow in order:\n{pre}\n\n"
            "Rules:\n"
            f"- Set date to {session.date!r}.\n"
            f"- Set framework_version to {FRAMEWORK_VERSION!r}.\n"
            "- structural_bias: infer from narrative (Early Bull, Mid Bull, Late Bull / Topping, Bear Market).\n"
            "- Emit schema-valid copies of spx_close and monte_carlo from analysis_context; "
            "the engine overwrites them after Pass 1.\n"
            f"- For precompute-owned matrix rows, use '(engine-filled)' placeholders: {owned_rows}.\n"
            "- decision_matrix.rows: 18 rows per framework; Recommended Action row signal in snake_case "
            "(e.g. hold_and_monitor, prepare_reentry_at_7151).\n"
            "- Enumerate genuine cross-layer tensions in conflicting_evidence with chart_refs "
            "(manifest filenames when known, else descriptive labels from the report).\n"
            "- Compare against prior posture snapshot in what_changed_today.\n"
            "- narrative_summary: 2-4 sentence single paragraph, plain text.\n\n"
            + HARD_CONSTRAINTS
        ),
    ]
    if memory:
        parts.insert(0, memory)
    return PromptBundle(system_role=system_role, framework=framework, body="\n\n".join(parts))


def build_migration_report_prompt(
    *,
    framework: str,
    system_role: str,
    session: PerplexitySession,
    daily_state: DailyState,
    analysis_context: AnalysisContext,
    recent_summary: str,
) -> PromptBundle:
    state_json = json.dumps(daily_state.model_dump(mode="json"), indent=2)
    steps = "\n".join(f"{i + 1}. {s}" for i, s in enumerate(WORKFLOW_STEPS))
    pre = f"0. {PRE_STEP}\n" + steps
    action = daily_state.decision_matrix.recommended_action
    mixed = daily_state.signal_alignment.overall == "mixed"
    mixed_note = (
        " Because signal alignment is mixed, Decision Matrix rows MUST use qualified "
        "readings (e.g., 'Fear (mixed)', 'Moderate-to-Elevated')."
        if mixed
        else ""
    )
    memory = _optional_memory_block(recent_summary)
    parts = [
        _analysis_context_block(analysis_context),
        f"## Validated daily state (immutable facts)\n```json\n{state_json}\n```",
        (
            "## Historical Perplexity narrative (preserve analytical substance)\n"
            f"{session.clean_markdown}"
        ),
        (
            "## Task\n"
            "Write the full normalized daily markdown analysis report for engine storage.\n\n"
            "This is a text-only Pass 2 (no chart images). Use the Perplexity narrative and "
            "validated state for exposition — do not re-open charts.\n\n"
            "IMMUTABLE (do not recompute or contradict): numeric signals, signal_alignment, "
            f"monte_carlo values, and decision_matrix.recommended_action ({action!r}).\n\n"
            f"Use these exact workflow step headings in order:\n{pre}\n\n"
            f"Within or immediately after the Technical & Sentiment Pulse step, include "
            f"'## {EVIDENCE_RECONCILIATION_HEADING}' that restates primary_tension and "
            "addresses each conflicting_evidence item.\n\n"
            "Step 5 must cite precomputed Monte Carlo from analysis_context (do not recompute).\n\n"
            "In Narrative & Executive Summary, explain why today's evidence resolves to "
            f"{action!r} given the 3-of-5 rule and Monte Carlo threshold.\n\n"
            "The report MUST end with '## Updated Decision Matrix' as a markdown table "
            f"with exactly these rows: {', '.join(DECISION_MATRIX_ROWS)}."
            f"{mixed_note} "
            "Preserve key levels, probabilities, and trade guidance from the Perplexity text. "
            "Output only the markdown report."
        ),
    ]
    if memory:
        parts.insert(0, memory)
    return PromptBundle(system_role=system_role, framework=framework, body="\n\n".join(parts))


def _finalize_migrated_state(state: DailyState, session: PerplexitySession) -> DailyState:
    return state.model_copy(
        update={"date": session.date, "framework_version": FRAMEWORK_VERSION}
    )


def _merge_enforcement_audit(
    report: ValidationReport,
    enforce_warnings: list[str],
) -> ValidationReport:
    issues = list(report.issues)
    for entry in audit_enforcement_issues(enforce_warnings):
        issues.append(ValidationIssue(**entry))
    return report.model_copy(update={"issues": issues})


def migrate_session(
    session: PerplexitySession,
    *,
    settings: Settings | None = None,
    client: AnthropicClient | None = None,
    force_fetch: bool = False,
) -> MigrationResult:
    settings = settings or get_settings()
    client = client or AnthropicClient(settings)
    framework = files.load_framework(settings)
    system_role = load_system_role(files.load_role(settings))
    warnings: list[str] = []

    analysis_context, ctx, eps_resolution = _prepare_session_precompute(
        session, settings, force_fetch=force_fetch
    )
    warnings.extend(analysis_context.market_data.precompute_warnings)

    yfinance_close = analysis_context.market_data.spx_close
    if abs(yfinance_close - session.spx_close) > 0.02:
        msg = (
            f"Perplexity header close {session.spx_close:.2f} differs from "
            f"yfinance precompute {yfinance_close:.2f}; enforcement uses precompute"
        )
        logger.warning("%s: %s", session.date, msg)
        warnings.append(msg)

    recent_states, mem_stats = load_recent_states_with_stats(
        before_date=session.date, settings=settings
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

    state_bundle = build_migration_state_prompt(
        framework=framework,
        system_role=system_role,
        session=session,
        ctx=ctx,
        analysis_context=analysis_context,
        recent_summary=recent_summary,
    )
    state_call = client.run_text_structured_state(state_bundle)
    daily_state, state_validation = parse_daily_state(state_call.tool_input or {}, session.date)

    if daily_state is None:
        repair = client.repair_structured_state(
            state_call.tool_input or {},
            validation_errors_text(state_validation),
        )
        daily_state, state_validation = parse_daily_state(repair.tool_input or {}, session.date)
        if daily_state is None:
            raise MigrationError(
                f"{session.date}: state validation failed after repair: "
                f"{validation_errors_text(state_validation)}"
            )
        warnings.append("state required one repair pass")

    daily_state, enforce_warnings = apply_precomputed_fields(daily_state, analysis_context)
    warnings.extend(enforce_warnings)
    state_validation = _merge_enforcement_audit(state_validation, enforce_warnings)
    daily_state = _finalize_migrated_state(daily_state, session)

    report_bundle = build_migration_report_prompt(
        framework=framework,
        system_role=system_role,
        session=session,
        daily_state=daily_state,
        analysis_context=analysis_context,
        recent_summary=recent_summary,
    )
    report_call = client.run_text_markdown_report(report_bundle)
    report_md = report_call.text or ""
    report_validation = validate_report(
        report_md,
        session.date,
        settings.max_report_chars,
        daily_state=daily_state,
    )

    if not report_validation.passed:
        warnings.append(
            "report validation issues: "
            + "; ".join(i.message for i in report_validation.issues)
        )

    run_log: dict[str, object] = {
        "date": session.date,
        "source": RUN_LOG_SOURCE,
        "title_line": session.title_line,
        "perplexity_close": session.spx_close,
        "yfinance_close": yfinance_close,
        "memory_load": memory_load,
        "warnings": warnings,
        "state_validation_passed": state_validation.passed,
        "report_validation_passed": report_validation.passed,
        "precompute_enforcement": {
            "applied": True,
            "warnings": enforce_warnings,
        },
        "eps_resolution": eps_resolution_log(eps_resolution),
    }

    output_dir = files.save_outputs(
        date=session.date,
        daily_state=daily_state,
        report_md=report_md,
        request_snapshot={
            "pass1": state_call.request_snapshot,
            "pass2": report_call.request_snapshot,
        },
        response_raw={
            "pass1": state_call.raw_response,
            "pass2": report_call.raw_response,
        },
        run_log=run_log,
        validation_reports=[
            state_validation.model_dump(mode="json"),
            report_validation.model_dump(mode="json"),
            {"target": "precompute_enforcement", "issues": audit_enforcement_issues(enforce_warnings)},
        ],
        mirror_to_memory=True,
        settings=settings,
    )
    files.write_json(output_dir / "analysis_context.json", analysis_context)
    files.write_json(settings.runs_dir / session.date / ANALYSIS_CONTEXT_FILENAME, analysis_context)

    rebuild_rolling_summary(settings=settings)

    return MigrationResult(
        date=session.date,
        daily_state=daily_state,
        report_md=report_md,
        state_validation=state_validation,
        report_validation=report_validation,
        output_dir=output_dir,
        analysis_context=analysis_context,
        warnings=warnings,
    )


def migrate_history(
    history_path: Path,
    *,
    from_date: str | None = None,
    to_date: str | None = None,
    settings: Settings | None = None,
    client: AnthropicClient | None = None,
    force_fetch: bool = False,
) -> list[MigrationResult]:
    sessions = filter_sessions(parse_history(history_path), from_date=from_date, to_date=to_date)
    if not sessions:
        raise MigrationError("no sessions matched the requested date range")

    results: list[MigrationResult] = []
    for session in sessions:
        logger.info("migrating %s (close %.2f)", session.date, session.spx_close)
        results.append(
            migrate_session(
                session,
                settings=settings,
                client=client,
                force_fetch=force_fetch,
            )
        )
    return results
