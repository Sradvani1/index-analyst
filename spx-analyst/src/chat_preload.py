"""Deterministic chat preload: latest-run state + rolling summary + instructions."""

from __future__ import annotations

import json
import logging
import re

from .config import Settings, get_settings
from .files import InputError, read_json, read_text
from .prompts import INVESTOR_REPORT_SECTIONS
from .schemas import ChatPreloadContext, DailyState, LatestRunState

logger = logging.getLogger(__name__)

_MATRIX_HEADING = INVESTOR_REPORT_SECTIONS[-1]


def find_latest_run_date(settings: Settings | None = None) -> str:
    """Return the newest trade date with a saved DailyState in memory."""
    settings = settings or get_settings()
    states_dir = settings.daily_states_dir
    if not states_dir.is_dir():
        raise InputError("no daily states found in memory; run analysis first")

    dates = sorted(
        (p.name.replace("-state.json", "") for p in states_dir.glob("*-state.json")),
        reverse=True,
    )
    if not dates:
        raise InputError("no daily states found in memory; run analysis first")
    return dates[0]


def load_latest_daily_state(settings: Settings | None = None) -> DailyState:
    """Load DailyState for the latest run date."""
    settings = settings or get_settings()
    date = find_latest_run_date(settings)
    path = settings.daily_states_dir / f"{date}-state.json"
    return DailyState.model_validate(read_json(path))


def load_rolling_summary(settings: Settings | None = None) -> str:
    """Load rolling summary markdown; empty string if not yet generated."""
    settings = settings or get_settings()
    path = settings.rolling_dir / "recent_summary.md"
    if not path.is_file():
        return ""
    return read_text(path).strip()


def load_instructions(settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    path = settings.chat_assistant_instructions_path
    if not path.is_file():
        raise InputError(f"chat assistant instructions not found: {path}")
    text = read_text(path).strip()
    if not text:
        raise InputError(f"chat assistant instructions are empty: {path}")
    return text


def _report_has_matrix_section(report_md: str) -> bool:
    return bool(
        re.search(
            rf"^##\s+{re.escape(_MATRIX_HEADING)}\s*$",
            report_md,
            re.IGNORECASE | re.MULTILINE,
        )
    )


def validate_report_matrix_section(
    date: str,
    daily_state: DailyState,
    settings: Settings | None = None,
) -> list[str]:
    """Optional validation: warn if same-date report matrix section is missing."""
    settings = settings or get_settings()
    report_path = settings.daily_reports_dir / f"{date}-analysis.md"
    if not report_path.is_file():
        return [f"same-date report missing for {date}; matrix preload uses DailyState only"]

    report_md = read_text(report_path)
    warnings: list[str] = []
    if not _report_has_matrix_section(report_md):
        warnings.append(
            f"same-date report for {date} is missing '{_MATRIX_HEADING}' section"
        )
        return warnings

    for row in daily_state.decision_matrix.rows:
        if row.signal_layer not in report_md:
            warnings.append(
                f"matrix row '{row.signal_layer}' not found in same-date report for {date}"
            )
    return warnings


def build_latest_run_state(daily_state: DailyState) -> LatestRunState:
    return LatestRunState.from_daily_state(daily_state)


def _format_matrix_table(latest: LatestRunState) -> str:
    lines = [
        "| Signal Layer | Current Reading | Signal |",
        "|---|---|---|",
    ]
    for row in latest.decision_matrix.rows:
        layer = row.signal_layer.replace("|", "\\|")
        reading = row.current_reading.replace("|", "\\|")
        signal = row.signal.replace("|", "\\|")
        lines.append(f"| {layer} | {reading} | {signal} |")
    return "\n".join(lines)


def build_latest_run_block(latest: LatestRunState) -> str:
    """Serialize LatestRunState for Assistants additional_instructions."""
    mc = latest.monte_carlo
    changes = latest.what_changed_today or ["(none)"]
    lines = [
        "## Latest-run state (authoritative for current posture)",
        "",
        f"latest_run_date: {latest.latest_run_date}",
        f"structural_bias: {latest.structural_bias}",
        f"spx_close: {latest.spx_close}",
        (
            f"signal_alignment: trim={latest.signal_alignment.trim_signals_met} "
            f"buy={latest.signal_alignment.buy_signals_met} "
            f"overall={latest.signal_alignment.overall}"
        ),
        f"recommended_action: {latest.recommended_action}",
        "",
        "what_changed_today:",
        *[f"- {item}" for item in changes],
        "",
        "monte_carlo:",
        f"- effective_threshold: {mc.effective_threshold}",
        f"- meets_threshold: {mc.meets_threshold}",
        f"- prob_up_first_adjusted: {mc.prob_up_first_adjusted:.4f}",
        f"- prob_down_first_adjusted: {mc.prob_down_first_adjusted:.4f}",
        f"- rally_exhaustion_score: {mc.rally_exhaustion_score}",
        f"- upside_target: {mc.upside_target}",
        f"- downside_target: {mc.downside_target}",
        "",
        "decision_matrix.rows (Updated Decision Matrix — authoritative):",
        _format_matrix_table(latest),
        "",
        "decision_matrix.rows (JSON):",
        json.dumps(
            [r.model_dump(mode="json") for r in latest.decision_matrix.rows],
            indent=2,
        ),
    ]
    return "\n".join(lines)


def build_additional_instructions(settings: Settings | None = None) -> ChatPreloadContext:
    """Assemble full preload: static instructions + latest-run block + rolling summary."""
    settings = settings or get_settings()
    instructions = load_instructions(settings)
    daily_state = load_latest_daily_state(settings)
    latest_run = build_latest_run_state(daily_state)

    for warning in validate_report_matrix_section(daily_state.date, daily_state, settings):
        logger.warning(warning)

    rolling_summary = load_rolling_summary(settings)
    latest_block = build_latest_run_block(latest_run)

    parts = [
        instructions,
        "",
        latest_block,
        "",
        "## Rolling summary (multi-day arc)",
        "",
        rolling_summary or "(no rolling summary on record)",
    ]
    additional_instructions = "\n".join(parts).strip()

    return ChatPreloadContext(
        instructions=instructions,
        latest_run=latest_run,
        rolling_summary=rolling_summary,
        additional_instructions=additional_instructions,
    )


def answer_posture_from_preload(context: ChatPreloadContext) -> str:
    """Deterministic posture answer from preload only (no vector retrieval)."""
    latest = context.latest_run
    action_row = None
    bias_row = None
    for row in latest.decision_matrix.rows:
        layer = row.signal_layer.strip().lower()
        if layer == "recommended action":
            action_row = row
        elif layer == "structural bias":
            bias_row = row

    action_text = latest.recommended_action
    if action_row is not None:
        action_text = action_row.signal or action_row.current_reading or action_text
    bias_text = latest.structural_bias
    if bias_row is not None:
        bias_text = bias_row.current_reading or bias_row.signal or bias_text

    return (
        f"As of {latest.latest_run_date}, structural bias is {bias_text} "
        f"with recommended action: {action_text} "
        f"(SPX close {latest.spx_close})."
    )
