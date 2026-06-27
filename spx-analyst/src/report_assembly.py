"""Assemble the investor-facing daily report from Pass 2 prose and Python-owned facts."""

from __future__ import annotations

import re

from .divergence_titles import rewrite_divergence_headings
from .formatting import format_price
from .prompts import INVESTOR_REPORT_SECTIONS, PASS2_PROSE_SECTIONS
from .schemas import AnalysisContext, DailyState

_SECTION_HEADING_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
_H1_RE = re.compile(r"^#\s+.+$", re.MULTILINE)
_MATRIX_HEADING = INVESTOR_REPORT_SECTIONS[-1]


def _format_close(value: float) -> str:
    return format_price(value)


def _posture_display(state: DailyState) -> str:
    for row in state.decision_matrix.rows:
        if row.signal_layer.strip().lower() == "recommended action":
            text = (row.signal or row.current_reading or "").strip()
            if text and (" " in text or "/" in text):
                return text
            return text.replace("_", " ").title() if text else state.decision_matrix.recommended_action
    action = state.decision_matrix.recommended_action
    return action.replace("_", " ").title()


def render_header_snapshot(
    *,
    date: str,
    daily_state: DailyState,
    analysis_context: AnalysisContext,
) -> str:
    close = analysis_context.market_data.spx_close
    lines = [
        f"# SPX Daily Analysis — {date}",
        "",
        f"**Framework version:** {daily_state.framework_version}",
        (
            f"**Close:** {_format_close(close)} | "
            f"**Structural Bias:** {daily_state.structural_bias} | "
            f"**Posture:** {_posture_display(daily_state)}"
        ),
        "",
    ]
    return "\n".join(lines)


def render_valuation_facts_block(
    *,
    daily_state: DailyState,
    analysis_context: AnalysisContext,
) -> str:
    v = analysis_context.valuation
    m = analysis_context.market_data
    lines = [
        "**Key valuation levels:**",
        "",
    ]
    if v.forward_pe is not None:
        lines.append(f"- Forward P/E: **{v.forward_pe:.2f}x** (bucket: {daily_state.valuation_bucket})")
    if v.trailing_pe is not None:
        lines.append(f"- Trailing P/E: **{v.trailing_pe:.2f}x**")
    if v.forward_earnings_yield is not None:
        lines.append(f"- Forward earnings yield: **{v.forward_earnings_yield:.2%}**")
    lines.append(f"- 10-year Treasury yield: **{m.us10y:.3f}%**")
    if v.erp is not None:
        trend = v.erp_trend or "n/a"
        lines.append(f"- ERP: **{v.erp:.2%}** ({trend})")
    if v.erp_reentry_floor_at_0_5pct is not None:
        lines.append(
            f"- ERP re-entry floor at 0.5% ERP: **{_format_close(v.erp_reentry_floor_at_0_5pct)}**"
        )
    lines.append("")
    return "\n".join(lines)


def render_monte_carlo_facts_block(
    *,
    daily_state: DailyState,
    analysis_context: AnalysisContext,
) -> str:
    mc_ctx = analysis_context.monte_carlo
    mc_state = daily_state.monte_carlo
    threshold = mc_state.effective_threshold
    lines = [
        "**Probability snapshot:**",
        "",
        f"- σ (20d realized vol): **{mc_ctx.sigma:.4f}** | μ (drift): **{mc_ctx.mu:.4f}**",
        (
            f"- Raw up-first: **{mc_ctx.prob_up_first_raw:.1%}** | "
            f"Raw down-first: **{mc_ctx.prob_down_first_raw:.1%}**"
        ),
        (
            f"- Adjusted up-first: **{mc_ctx.prob_up_first_adjusted:.1%}** | "
            f"Adjusted down-first: **{mc_ctx.prob_down_first_adjusted:.1%}**"
        ),
        f"- Effective threshold ({threshold}%): **{'actionable' if mc_state.meets_threshold else 'below threshold'}**",
        f"- Rally exhaustion: **{mc_ctx.rally_exhaustion_score}** (discount {mc_ctx.exhaustion_discount:.0%})",
        (
            f"- Upside target: **{_format_close(mc_ctx.upside_target)}** ({mc_ctx.upside_target_rule}) | "
            f"Downside target: **{_format_close(mc_ctx.downside_target)}** ({mc_ctx.downside_target_rule})"
        ),
        f"- Median days: {mc_ctx.median_days}",
        f"- Conditional cascade: {mc_ctx.cascades}",
        f"- Drift path: {mc_ctx.drift_path} | Cash-drag probability: {mc_ctx.cash_drag_prob:.0%}",
        "",
    ]
    return "\n".join(lines)


def render_tactical_levels_block(*, analysis_context: AnalysisContext) -> str:
    s = analysis_context.structure
    lines = [
        "**Tactical levels:**",
        "",
        f"- Active swing high: **{_format_close(s.active_swing_high_price)}** ({s.active_swing_high_date})",
        f"- Active swing low: **{_format_close(s.active_swing_low_price)}** ({s.active_swing_low_date})",
        (
            f"- Fibonacci: 23.6% **{_format_close(s.fib_236)}** | "
            f"38.2% **{_format_close(s.fib_382)}** | "
            f"50% **{_format_close(s.fib_500)}** | "
            f"61.8% **{_format_close(s.fib_618)}**"
        ),
        (
            f"- Liquidation zones: caution **{_format_close(s.liquidation_caution)}** | "
            f"nervous **{_format_close(s.liquidation_nervous)}** | "
            f"margin call **{_format_close(s.liquidation_margin_call)}** | "
            f"cascade **{_format_close(s.liquidation_cascade)}**"
        ),
        (
            f"- Monte Carlo targets: upside **{_format_close(s.upside_target)}** | "
            f"downside **{_format_close(s.downside_target)}**"
        ),
        "",
    ]
    return "\n".join(lines)


def render_decision_matrix_table(*, daily_state: DailyState) -> str:
    lines = [
        f"## {_MATRIX_HEADING}",
        "",
        "| Signal Layer | Current Reading | Signal |",
        "|---|---|---|",
    ]
    for row in daily_state.decision_matrix.rows:
        layer = row.signal_layer.replace("|", "\\|")
        reading = row.current_reading.replace("|", "\\|")
        signal = row.signal.replace("|", "\\|")
        lines.append(f"| {layer} | {reading} | {signal} |")
    lines.append("")
    return "\n".join(lines)


def _canonical_section_title(raw: str) -> str | None:
    title = raw.strip()
    for section in PASS2_PROSE_SECTIONS:
        if title.lower() == section.lower():
            return section
    return None


def extract_prose_sections(prose_md: str) -> dict[str, str]:
    """Parse Pass 2 prose into canonical section bodies; strip preamble and matrix drift."""
    text = prose_md.strip()
    if not text:
        return {}

    matrix_match = re.search(
        rf"^##\s+{re.escape(_MATRIX_HEADING)}\s*$",
        text,
        re.IGNORECASE | re.MULTILINE,
    )
    if matrix_match:
        text = text[: matrix_match.start()].strip()

    text = _H1_RE.sub("", text).strip()

    sections: dict[str, str] = {}
    matches = list(_SECTION_HEADING_RE.finditer(text))
    for idx, match in enumerate(matches):
        title = _canonical_section_title(match.group(1))
        if title is None:
            continue
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        sections[title] = body

    return sections


def assemble_investor_report(
    *,
    date: str,
    daily_state: DailyState,
    analysis_context: AnalysisContext,
    prose_md: str,
) -> str:
    """Compose publish markdown: Header Snapshot + eight prose sections + fact injections + matrix."""
    sections = extract_prose_sections(prose_md)
    parts: list[str] = [render_header_snapshot(date=date, daily_state=daily_state, analysis_context=analysis_context)]

    for title in PASS2_PROSE_SECTIONS:
        parts.append(f"## {title}")
        parts.append("")
        body = sections.get(title, "").strip()
        if title == "Evidence and Tensions" and body:
            body = rewrite_divergence_headings(body, daily_state.conflicting_evidence)
        if body:
            parts.append(body)
            parts.append("")

        if title == "Valuation and ERP":
            parts.append(render_valuation_facts_block(daily_state=daily_state, analysis_context=analysis_context))
        elif title == "Risk and Monte Carlo":
            parts.append(render_monte_carlo_facts_block(daily_state=daily_state, analysis_context=analysis_context))
        elif title == "Tactical Levels and Next Session Plan":
            parts.append(render_tactical_levels_block(analysis_context=analysis_context))

    parts.append(render_decision_matrix_table(daily_state=daily_state))
    return "\n".join(parts).rstrip() + "\n"
