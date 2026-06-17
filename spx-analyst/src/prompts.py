"""Prompt construction for the two-pass pipeline."""

from __future__ import annotations

import json
from dataclasses import dataclass

from .schemas import AnalysisContext, DailyManifest, DailyState, ExternalContext

PRE_STEP = "Structural Regime Classification"

WORKFLOW_STEPS: list[str] = [
    "Price Action and Trend Recentering",
    "Technical and Sentiment Pulse",
    "Fundamental Valuation and ERP",
    "Leverage and Liquidation Structure",
    "Monte Carlo and Brownian Motion",
    "Tactical Matrix",
    "Narrative and Executive Summary",
]

DECISION_MATRIX_ROWS: list[str] = [
    "Structural Bias",
    "Monte Carlo Threshold",
    "Volatility Input",
    "Drift Input",
    "Rally Exhaustion Score",
    "Trend Regime",
    "Intraday Close Position",
    "RSI / MFI State",
    "20-Day SMA Status",
    "Bollinger Band State",
    "ERP State and Trend",
    "Credit Condition",
    "Breadth Condition",
    "VIX Regime",
    "Leverage Risk State",
    "Monte Carlo Edge",
    "Overall Signal Balance",
    "Recommended Action",
]

EVIDENCE_RECONCILIATION_HEADING = "Evidence Reconciliation"

STRUCTURAL_BIAS_THRESHOLDS: dict[str, int] = {
    "Early Bull": 65,
    "Mid Bull": 65,
    "Late Bull / Topping": 70,
    "Bear Market": 75,
}

HARD_CONSTRAINTS = """\
Non-negotiable constraints (from the framework):
- Complete Structural Regime Classification before Step 1.
- Signals are actionable only when multiple independent indicators align; mixed data means hold and monitor.
- Never use Monte Carlo output in isolation — interpret through structural bias and chart evidence.
- Monte Carlo values come from analysis_context (Python precompute). Select effective_threshold from \
structural_bias (Early/Mid Bull=65, Late Bull=70, Bear=75), copy the matching threshold_evaluation row \
and simulation fields into emit_daily_state. Do not recalculate or adjust probabilities.
- Use analysis_context for ERP, structural levels, and all precomputed numerics (close, VIX, 10Y).
- Chart labels never override analysis_context numeric values.
- Always end with the Updated Decision Matrix (18 rows)."""


def load_system_role(role_text: str) -> str:
    return role_text.strip() + "\n\n" + HARD_CONSTRAINTS


@dataclass
class PromptBundle:
    system_role: str
    framework: str
    body: str


def _external_block(ctx: ExternalContext) -> str:
    payload = ctx.model_dump(mode="json")
    return "## External context (manual EPS inputs)\n```json\n" + json.dumps(payload, indent=2) + "\n```"


def _analysis_context_block(ctx: AnalysisContext) -> str:
    payload = ctx.model_dump(mode="json")
    return (
        "## Precomputed analysis context (immutable numeric truth for this run)\n"
        "Use these values for ERP, structure, and Monte Carlo. Do not recalculate.\n"
        f"```json\n{json.dumps(payload, indent=2)}\n```"
    )


def _manifest_block(manifest: DailyManifest) -> str:
    lines = [
        "## Today's chart pack (images attached in this order)",
        f"Date: {manifest.date} | Index: {manifest.index_symbol} | "
        f"Reference close (validation only): {manifest.close}",
        "",
    ]
    for c in manifest.ordered_charts():
        tf = f" [{c.timeframe}]" if c.timeframe else ""
        lines.append(f"{c.order}. {c.label}{tf} ({c.category}) -- file: {c.file}")
    return "\n".join(lines)


def _optional_memory_block(recent_summary: str | None) -> str:
    if not recent_summary:
        return ""
    return (
        "## Optional prior-run narrative context (non-authoritative)\n"
        "Use only for day-over-day narrative continuity — never for numeric calculations.\n"
        f"{recent_summary}"
    )


def _conflict_block(daily_state: DailyState) -> str:
    conflicts_json = json.dumps(
        [d.model_dump(mode="json") for d in daily_state.conflicting_evidence],
        indent=2,
    )
    confirming = "\n".join(f"- {item}" for item in daily_state.confirming_evidence) or "- (none listed)"
    return (
        "## Conflict checklist (from validated state)\n"
        f"Primary tension: {daily_state.primary_tension}\n\n"
        f"Structural bias: {daily_state.structural_bias}\n"
        f"Signal alignment: trim {daily_state.signal_alignment.trim_signals_met}/5, "
        f"buy {daily_state.signal_alignment.buy_signals_met}/5, "
        f"overall {daily_state.signal_alignment.overall}\n\n"
        "Confirming evidence:\n"
        f"{confirming}\n\n"
        "Conflicting evidence (re-examine cited charts for each):\n"
        f"```json\n{conflicts_json}\n```"
    )


def build_state_prompt(
    *,
    system_role: str,
    framework: str,
    manifest: DailyManifest,
    external_context: ExternalContext,
    analysis_context: AnalysisContext,
    recent_summary: str | None = None,
) -> PromptBundle:
    parts = [
        _analysis_context_block(analysis_context),
        _external_block(external_context),
        _manifest_block(manifest),
    ]
    mem = _optional_memory_block(recent_summary)
    if mem:
        parts.insert(0, mem)

    threshold_map = json.dumps(STRUCTURAL_BIAS_THRESHOLDS, indent=2)
    parts.append(
        "## Task\n"
        f"Complete `{PRE_STEP}` first, then the Daily 7-Step Workflow in order. "
        "Read all charts for qualitative technical and sentiment evidence. "
        "Call `emit_daily_state` exactly once.\n\n"
        "Before calling the tool:\n"
        "1. Set `structural_bias` from chart evidence (Pre-Step).\n"
        f"2. Map structural_bias to effective_threshold using: {threshold_map}\n"
        "3. Copy Monte Carlo fields from analysis_context — select threshold_evaluation row "
        "for effective_threshold; set meets_threshold from row.actionable. Do not recalculate.\n"
        "4. Set `spx_close` from analysis_context.market_data.spx_close.\n"
        "5. Compute signal_alignment from chart evidence; list confirming_evidence and conflicting_evidence.\n"
        "6. Build decision_matrix.rows with all 18 framework rows.\n"
        "7. Set framework_version to 'daily-2026-06'.\n\n"
        "Keep narrative_summary to 2-4 sentences plain text."
    )
    return PromptBundle(system_role=system_role, framework=framework, body="\n\n".join(parts))


def build_report_prompt(
    *,
    system_role: str,
    framework: str,
    daily_state: DailyState,
    manifest: DailyManifest,
    external_context: ExternalContext,
    analysis_context: AnalysisContext,
    recent_summary: str | None = None,
) -> PromptBundle:
    state_json = json.dumps(daily_state.model_dump(mode="json"), indent=2)
    steps = "\n".join(f"{i + 1}. {s}" for i, s in enumerate(WORKFLOW_STEPS))
    pre = f"0. {PRE_STEP}\n" + steps
    action = daily_state.decision_matrix.recommended_action
    mixed = daily_state.signal_alignment.overall == "mixed"
    mixed_note = (
        " Use qualified readings in the Decision Matrix when alignment is mixed."
        if mixed
        else ""
    )

    parts = [
        _analysis_context_block(analysis_context),
        _external_block(external_context),
        _manifest_block(manifest),
        f"## Validated daily state (immutable)\n```json\n{state_json}\n```",
        _conflict_block(daily_state),
    ]
    mem = _optional_memory_block(recent_summary)
    if mem:
        parts.insert(0, mem)

    parts.append(
        "## Task\n"
        "Write the full daily markdown report. Re-open charts for Evidence Reconciliation.\n\n"
        "IMMUTABLE: structural_bias, monte_carlo, signal_alignment, decision_matrix, spx_close "
        f"from state. Recommended action: {action!r}.\n\n"
        f"Workflow headings in order:\n{pre}\n\n"
        f"Include `## {EVIDENCE_RECONCILIATION_HEADING}` after Step 2 for mixed/conflicting evidence.\n\n"
        "Step 5 must cite precomputed Monte Carlo from analysis_context (do not recompute).\n\n"
        f"End with `## Updated Decision Matrix` table rows: {', '.join(DECISION_MATRIX_ROWS)}."
        f"{mixed_note}"
    )
    return PromptBundle(system_role=system_role, framework=framework, body="\n\n".join(parts))
