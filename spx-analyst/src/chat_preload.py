"""Deterministic compact chat preload: constitution + current brief + arc brief."""

from __future__ import annotations

import logging
import re

from .config import Settings, get_settings
from .files import InputError, read_json, read_text
from .formatting import format_event_headline, format_price
from .memory import build_arc_brief, first_sentence, load_recent_states, select_top_conflicts
from .prompts import INVESTOR_REPORT_SECTIONS
from .schemas import (
    ArcBrief,
    ArcBriefCaps,
    ChatPreloadContext,
    ConstitutionCaps,
    CurrentBrief,
    CurrentBriefCaps,
    CurrentBriefRow,
    DailyState,
    DecisionMatrixRow,
)

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


def _truncate(text: str, max_len: int) -> str:
    text = text.strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def load_instructions(settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    path = settings.chat_assistant_instructions_path
    if not path.is_file():
        raise InputError(f"chat assistant instructions not found: {path}")
    text = read_text(path).strip()
    if not text:
        raise InputError(f"chat assistant instructions are empty: {path}")
    if len(text) > ConstitutionCaps.MAX_RENDERED_CHARS:
        text = _truncate(text, ConstitutionCaps.MAX_RENDERED_CHARS)
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


def _matrix_row(state: DailyState, layer_name: str) -> DecisionMatrixRow | None:
    target = layer_name.strip().lower()
    for row in state.decision_matrix.rows:
        if row.signal_layer.strip().lower() == target:
            return row
    return None


def _matrix_signal(state: DailyState, layer_name: str, *, fallback: str = "n/a") -> str:
    row = _matrix_row(state, layer_name)
    if row is None:
        return fallback
    return row.signal or row.current_reading or fallback


def _opening_house_view(brief: DailyState) -> str:
    opening = (
        f"As of {brief.date} (SPX close {format_price(brief.spx_close)}): "
        f"{brief.structural_bias} — "
        f"{_matrix_signal(brief, 'Recommended Action', fallback=brief.decision_matrix.recommended_action)}. "
        f"Signal balance: {_matrix_signal(brief, 'Overall Signal Balance')}."
    )
    return _truncate(opening, CurrentBriefCaps.MAX_OPENING_CHARS)


def _setup_tension_sentence(state: DailyState) -> str:
    tension = first_sentence(state.primary_tension) or state.primary_tension.strip()
    return _truncate(tension, CurrentBriefCaps.MAX_SETUP_TENSION_CHARS)


def _risk_bullets(state: DailyState) -> list[str]:
    bullets: list[str] = []
    if state.what_changed_today:
        bullets.append(
            _truncate(
                format_event_headline(state.what_changed_today[0].strip()),
                CurrentBriefCaps.MAX_RISK_BULLET_CHARS,
            )
        )
    else:
        tension = first_sentence(state.primary_tension)
        if tension:
            bullets.append(_truncate(tension, CurrentBriefCaps.MAX_RISK_BULLET_CHARS))
    for divergence in select_top_conflicts(state.conflicting_evidence):
        bullets.append(
            _truncate(
                divergence.framework_rule.strip(),
                CurrentBriefCaps.MAX_RISK_BULLET_CHARS,
            )
        )
    return bullets[: CurrentBriefCaps.MAX_RISK_BULLETS]


def _view_change_bullets(state: DailyState) -> list[str]:
    bullets: list[str] = []
    for question in state.open_questions:
        text = question.strip()
        if not text:
            continue
        bullets.append(_truncate(text, CurrentBriefCaps.MAX_VIEW_CHANGE_BULLET_CHARS))
        if len(bullets) >= CurrentBriefCaps.MAX_VIEW_CHANGE_BULLETS:
            break
    return bullets


def _trigger_levels(state: DailyState) -> list[str]:
    levels: list[str] = []
    mc = state.monte_carlo
    levels.append(f"MC upside: {format_price(mc.upside_target)}")
    levels.append(f"MC downside: {format_price(mc.downside_target)}")
    if mc.conditional_cascade.strip():
        levels.append(
            f"MC cascade: {_truncate(mc.conditional_cascade, CurrentBriefCaps.MAX_TRIGGER_BULLET_CHARS)}"
        )
    leverage = _matrix_row(state, "Leverage Risk State")
    if leverage is not None:
        snippet = leverage.signal or leverage.current_reading
        if snippet:
            levels.append(
                f"Leverage: {_truncate(snippet, CurrentBriefCaps.MAX_TRIGGER_BULLET_CHARS)}"
            )
    return levels[: CurrentBriefCaps.MAX_TRIGGER_BULLETS]


def _authoritative_rows(state: DailyState) -> list[CurrentBriefRow]:
    trend_regime = _truncate(state.trend_regime, CurrentBriefCaps.MAX_TREND_REGIME_CHARS)
    leverage = _matrix_row(state, "Leverage Risk State")
    mc_edge = _matrix_row(state, "Monte Carlo Edge")
    rows = [
        CurrentBriefRow(
            signal_layer="Structural Bias",
            signal=_matrix_signal(state, "Structural Bias", fallback=state.structural_bias),
        ),
        CurrentBriefRow(
            signal_layer="Overall Signal Balance",
            signal=_matrix_signal(state, "Overall Signal Balance"),
        ),
        CurrentBriefRow(signal_layer="Trend Regime", signal=trend_regime),
        CurrentBriefRow(
            signal_layer="Recommended Action",
            signal=_matrix_signal(
                state,
                "Recommended Action",
                fallback=state.decision_matrix.recommended_action,
            ),
        ),
        CurrentBriefRow(
            signal_layer="Leverage Risk State",
            signal=(
                leverage.signal or leverage.current_reading or "n/a"
                if leverage is not None
                else "n/a"
            ),
        ),
        CurrentBriefRow(
            signal_layer="Monte Carlo Edge",
            signal=(
                mc_edge.signal or mc_edge.current_reading or "n/a"
                if mc_edge is not None
                else "n/a"
            ),
        ),
    ]
    return rows[: CurrentBriefCaps.MAX_MATRIX_ROWS]


def build_current_brief(state: DailyState) -> CurrentBrief:
    """Build authoritative present-tense slice from latest DailyState."""
    recommended_action = _matrix_signal(
        state,
        "Recommended Action",
        fallback=state.decision_matrix.recommended_action,
    )
    return CurrentBrief(
        latest_run_date=state.date,
        spx_close=state.spx_close,
        structural_bias=state.structural_bias,
        recommended_action=recommended_action,
        overall_signal_balance=_matrix_signal(state, "Overall Signal Balance"),
        opening_house_view=_opening_house_view(state),
        setup_tension=_setup_tension_sentence(state),
        key_risks_or_tensions=_risk_bullets(state),
        key_trigger_levels=_trigger_levels(state),
        view_change_bullets=_view_change_bullets(state),
        authoritative_rows=_authoritative_rows(state),
    )


def render_current_brief(brief: CurrentBrief) -> str:
    """Render compact current brief markdown (no matrix JSON)."""
    lines = [
        "## Current house view",
        "Authoritative for present-tense posture.",
        "",
        brief.opening_house_view,
        "",
        f"Setup / tension: {brief.setup_tension}",
        "",
        "| Signal Layer | Signal |",
        "|---|---|",
    ]
    for row in brief.authoritative_rows:
        layer = row.signal_layer.replace("|", "\\|")
        signal = row.signal.replace("|", "\\|")
        lines.append(f"| {layer} | {signal} |")

    if brief.key_risks_or_tensions:
        lines.extend(["", "What shifted:"])
        lines.extend(f"- {item}" for item in brief.key_risks_or_tensions)

    if brief.key_trigger_levels:
        lines.extend(["", "Triggers to watch:"])
        lines.extend(f"- {item}" for item in brief.key_trigger_levels)

    if brief.view_change_bullets:
        lines.extend(["", "What changes the view:"])
        lines.extend(f"- {item}" for item in brief.view_change_bullets)

    rendered = "\n".join(lines)
    if len(rendered) > CurrentBriefCaps.MAX_RENDERED_CHARS:
        rendered = _truncate(rendered, CurrentBriefCaps.MAX_RENDERED_CHARS)
    return rendered


def render_arc_brief(arc: ArcBrief) -> str:
    """Render compressed arc brief (no PR-3 delta replay markers)."""
    lines = [
        "## Recent arc",
        "Current house view wins on same-date conflict.",
        "",
        arc.regime_arc,
        "",
    ]
    for snapshot in arc.session_snapshots:
        lines.append(
            f"{snapshot.date} | {snapshot.bias} | {snapshot.action} | {snapshot.tension_fragment}"
        )
    if arc.inflection_bullets:
        lines.extend(["", "Inflection points:"])
        lines.extend(f"- {item}" for item in arc.inflection_bullets)
    if arc.still_open_bullets:
        lines.extend(["", "Still open:"])
        lines.extend(f"- {item}" for item in arc.still_open_bullets)
    rendered = "\n".join(lines)
    if len(rendered) > ArcBriefCaps.MAX_RENDERED_CHARS:
        rendered = _truncate(rendered, ArcBriefCaps.MAX_RENDERED_CHARS)
    return rendered


def build_additional_instructions(settings: Settings | None = None) -> ChatPreloadContext:
    """Assemble compact preload: constitution + current brief + arc brief."""
    settings = settings or get_settings()
    instructions = load_instructions(settings)
    daily_state = load_latest_daily_state(settings)

    for warning in validate_report_matrix_section(daily_state.date, daily_state, settings):
        logger.warning(warning)

    states = load_recent_states(settings=settings)
    brief = build_current_brief(daily_state)
    arc = build_arc_brief(states)

    parts = [
        instructions,
        "",
        render_current_brief(brief),
        "",
        render_arc_brief(arc),
    ]
    additional_instructions = "\n".join(parts).strip()

    return ChatPreloadContext(
        instructions=instructions,
        current_brief=brief,
        arc_brief=arc,
        additional_instructions=additional_instructions,
    )


def answer_posture_from_preload(context: ChatPreloadContext) -> str:
    """Deterministic posture answer from preload only (no vector retrieval)."""
    brief = context.current_brief
    bias_row = next(
        (row for row in brief.authoritative_rows if row.signal_layer == "Structural Bias"),
        None,
    )
    action_row = next(
        (row for row in brief.authoritative_rows if row.signal_layer == "Recommended Action"),
        None,
    )
    bias_text = bias_row.signal if bias_row is not None else brief.structural_bias
    action_text = action_row.signal if action_row is not None else brief.recommended_action

    return (
        f"As of {brief.latest_run_date}, structural bias is {bias_text} "
        f"with recommended action: {action_text} "
        f"(SPX close {format_price(brief.spx_close)})."
    )
