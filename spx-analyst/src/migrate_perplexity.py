"""Migrate historical Perplexity daily analyses into engine artifacts.

Parses standalone Full 7-Step sessions from an exported markdown history file,
converts each to schema-valid DailyState JSON and a normalized analysis report,
and writes canonical output/ + memory/ files.
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
from .external_data import blank_context
from .files import MANIFEST_FILENAME, EXTERNAL_CONTEXT_FILENAME, read_json
from .memory import build_recent_summary, load_recent_states
from .prompts import (
    DECISION_MATRIX_ROWS,
    EVIDENCE_RECONCILIATION_HEADING,
    HARD_CONSTRAINTS,
    SYSTEM_ROLE,
    WORKFLOW_STEPS,
    PromptBundle,
)
from .schemas import DailyManifest, DailyState, ExternalContext, ValidationReport
from .validation import parse_daily_state, validate_report, validation_errors_text

logger = logging.getLogger(__name__)

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
    external_context: ExternalContext | None = None
    chart_ref_map: dict[str, str] = field(default_factory=dict)


@dataclass
class MigrationResult:
    date: str
    daily_state: DailyState
    report_md: str
    state_validation: ValidationReport
    report_validation: ValidationReport
    output_dir: Path
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
    """Attach manifest/external context when a run directory exists."""
    settings = settings or get_settings()
    run_dir = settings.runs_dir / date
    if not run_dir.is_dir():
        return SessionContext()

    manifest = None
    external = None
    chart_map: dict[str, str] = {}

    manifest_path = run_dir / MANIFEST_FILENAME
    if manifest_path.exists():
        manifest = DailyManifest.model_validate(read_json(manifest_path))
        for entry in manifest.ordered_charts():
            chart_map[entry.label.lower()] = entry.file

    ext_path = run_dir / EXTERNAL_CONTEXT_FILENAME
    if ext_path.exists():
        external = ExternalContext.model_validate(read_json(ext_path))
    else:
        external = blank_context(date)

    return SessionContext(
        manifest=manifest,
        external_context=external,
        chart_ref_map=chart_map,
    )


def _context_block(ctx: SessionContext, session: PerplexitySession) -> str:
    lines = [
        "## Session metadata",
        f"Date: {session.date}",
        f"SPX close (from Perplexity header): {session.spx_close}",
        "framework_version: perplexity-migration",
    ]
    if ctx.manifest:
        lines.append(f"Manifest close: {ctx.manifest.close}")
        lines.append("Chart filenames (use these in chart_refs when applicable):")
        for c in ctx.manifest.ordered_charts():
            lines.append(f"  - {c.file}: {c.label}")
    if ctx.external_context:
        lines.append(
            "## External context\n```json\n"
            + json.dumps(ctx.external_context.model_dump(mode="json"), indent=2)
            + "\n```"
        )
    return "\n".join(lines)


def build_migration_state_prompt(
    *,
    framework: str,
    session: PerplexitySession,
    ctx: SessionContext,
    recent_summary: str,
) -> PromptBundle:
    steps = "\n".join(f"{i + 1}. {s}" for i, s in enumerate(WORKFLOW_STEPS))
    body = "\n\n".join(
        [
            _context_block(ctx, session),
            "## Recent historical memory\n" + recent_summary,
            (
                "## Historical Perplexity analysis (source of truth)\n"
                "Extract structured state ONLY from facts stated below. "
                "Do NOT invent numbers, probabilities, or signals not present in the text. "
                "Use null for any signal you cannot determine.\n\n"
                f"{session.clean_markdown}"
            ),
            (
                "## Task\n"
                "Convert this historical Perplexity report into one `emit_daily_state` tool call.\n\n"
                f"Required fields follow the DailyState schema and methodology steps:\n{steps}\n\n"
                "Rules:\n"
                f"- Set date to {session.date!r} and spx_close to {session.spx_close} "
                "(override if manifest close differs only when Perplexity explicitly uses another close).\n"
                "- Set framework_version to 'perplexity-migration'.\n"
                "- monte_carlo.prob_up_first / prob_down_first: use the PRIMARY Step 5 "
                "first-hit row (upside target first vs downside target first).\n"
                "- monte_carlo.meets_threshold: true only if the dominant first-hit probability >= 0.65.\n"
                "- decision_matrix.recommended_action: normalize Perplexity RECOMMENDED ACTION to "
                "snake_case (e.g. hold_schk_wave1_trim_imminent, prepare_reentry_at_7151).\n"
                "- Enumerate genuine cross-layer tensions in conflicting_evidence with chart_refs "
                "(manifest filenames when known, else descriptive labels from the report).\n"
                "- Compare against recent sessions in what_changed_today.\n"
                "- narrative_summary: 2-4 sentence single paragraph, plain text.\n\n"
                + HARD_CONSTRAINTS
            ),
        ]
    )
    return PromptBundle(system_role=SYSTEM_ROLE, framework=framework, body=body)


def build_migration_report_prompt(
    *,
    framework: str,
    session: PerplexitySession,
    daily_state: DailyState,
    recent_summary: str,
) -> PromptBundle:
    state_json = json.dumps(daily_state.model_dump(mode="json"), indent=2)
    steps = "\n".join(f"{i + 1}. {s}" for i, s in enumerate(WORKFLOW_STEPS))
    action = daily_state.decision_matrix.recommended_action
    mixed = daily_state.signal_alignment.overall == "mixed"
    mixed_note = (
        " Because signal alignment is mixed, Decision Matrix rows MUST use qualified "
        "readings (e.g., 'Fear (mixed)', 'Moderate-to-Elevated')."
        if mixed
        else ""
    )
    body = "\n\n".join(
        [
            "## Recent historical memory\n" + recent_summary,
            (
                "## Validated daily state (immutable facts)\n"
                f"```json\n{state_json}\n```"
            ),
            (
                "## Historical Perplexity narrative (preserve analytical substance)\n"
                f"{session.clean_markdown}"
            ),
            (
                "## Task\n"
                "Write the full normalized daily markdown analysis report for engine storage.\n\n"
                "IMMUTABLE (do not recompute or contradict): numeric signals, signal_alignment, "
                f"monte_carlo values, and decision_matrix.recommended_action ({action!r}).\n\n"
                f"Use these exact workflow step headings in order:\n{steps}\n\n"
                f"Within or immediately after the Technical & Sentiment Pulse step, include "
                f"'## {EVIDENCE_RECONCILIATION_HEADING}' that restates primary_tension and "
                "addresses each conflicting_evidence item.\n\n"
                "In Narrative & Executive Summary, explain why today's evidence resolves to "
                f"{action!r} given the 3-of-5 rule and Monte Carlo threshold.\n\n"
                "The report MUST end with '## Updated Decision Matrix' as a markdown table "
                f"with exactly these rows: {', '.join(DECISION_MATRIX_ROWS)}."
                f"{mixed_note} "
                "Preserve key levels, probabilities, and trade guidance from the Perplexity text. "
                "Output only the markdown report."
            ),
        ]
    )
    return PromptBundle(system_role=SYSTEM_ROLE, framework=framework, body=body)


def _enforce_close(state: DailyState, session: PerplexitySession, ctx: SessionContext) -> DailyState:
    """Hard guardrail: header close is authoritative for migration."""
    data = state.model_dump(mode="json")
    data["date"] = session.date
    data["spx_close"] = session.spx_close
    data["framework_version"] = "perplexity-migration"
    if ctx.manifest and abs(ctx.manifest.close - session.spx_close) > 0.02:
        logger.warning(
            "%s: manifest close %.2f differs from Perplexity %.2f; using Perplexity",
            session.date,
            ctx.manifest.close,
            session.spx_close,
        )
    return DailyState.model_validate(data)


def migrate_session(
    session: PerplexitySession,
    *,
    settings: Settings | None = None,
    client: AnthropicClient | None = None,
) -> MigrationResult:
    settings = settings or get_settings()
    client = client or AnthropicClient(settings)
    framework = files.load_framework(settings)
    ctx = load_session_context(session.date, settings)
    recent_states = load_recent_states(before_date=session.date, settings=settings)
    recent_summary = build_recent_summary(recent_states)
    warnings: list[str] = []

    state_bundle = build_migration_state_prompt(
        framework=framework,
        session=session,
        ctx=ctx,
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

    daily_state = _enforce_close(daily_state, session, ctx)

    report_bundle = build_migration_report_prompt(
        framework=framework,
        session=session,
        daily_state=daily_state,
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

    run_log = {
        "date": session.date,
        "source": "perplexity_migration",
        "title_line": session.title_line,
        "perplexity_close": session.spx_close,
        "warnings": warnings,
        "state_validation_passed": state_validation.passed,
        "report_validation_passed": report_validation.passed,
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
        ],
        mirror_to_memory=True,
        settings=settings,
    )

    return MigrationResult(
        date=session.date,
        daily_state=daily_state,
        report_md=report_md,
        state_validation=state_validation,
        report_validation=report_validation,
        output_dir=output_dir,
        warnings=warnings,
    )


def migrate_history(
    history_path: Path,
    *,
    from_date: str | None = None,
    to_date: str | None = None,
    settings: Settings | None = None,
    client: AnthropicClient | None = None,
) -> list[MigrationResult]:
    sessions = filter_sessions(parse_history(history_path), from_date=from_date, to_date=to_date)
    if not sessions:
        raise MigrationError("no sessions matched the requested date range")

    results: list[MigrationResult] = []
    for session in sessions:
        logger.info("migrating %s (close %.2f)", session.date, session.spx_close)
        results.append(migrate_session(session, settings=settings, client=client))
    return results
