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

# Rows deterministically overwritten by state_enforcement.sync_matrix_precomputed_rows;
# the model emits placeholders for these instead of reasoning out numbers.
PRECOMPUTE_OWNED_MATRIX_ROWS: list[str] = [
    "Structural Bias",
    "Monte Carlo Threshold",
    "Volatility Input",
    "Drift Input",
    "Rally Exhaustion Score",
    "Monte Carlo Edge",
    "ERP State and Trend",
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
- Complete Structural Regime Classification before Step 1; assign exactly one structural_bias.
- Signals are actionable only when multiple independent indicators align; mixed data means hold and monitor.
- Never use Monte Carlo output in isolation — interpret it through structural_bias and chart evidence.
- analysis_context is the sole numeric source of truth. Wherever the framework says "Calculate" (ERP, \
Fibonacci, drawdown/liquidation zones, volatility, drift, Monte Carlo), read and interpret the precomputed \
value instead — never recompute or adjust it. Chart labels never override analysis_context numerics.
- The engine deterministically re-derives spx_close, the Monte Carlo block, and the numeric decision-matrix \
rows after this step, so spend your effort on the qualitative chart reads and structural_bias, not on \
transcribing numbers precisely.
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


def _round_floats(obj: object, places: int = 4) -> object:
    """Strip float32 noise from rendered numbers (prompt-only; never persisted)."""
    if isinstance(obj, float):
        return round(obj, places)
    if isinstance(obj, dict):
        return {k: _round_floats(v, places) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_round_floats(v, places) for v in obj]
    return obj


def _analysis_context_block(ctx: AnalysisContext) -> str:
    payload = _round_floats(ctx.model_dump(mode="json"))
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

    owned_rows = ", ".join(PRECOMPUTE_OWNED_MATRIX_ROWS)
    parts.append(
        "## Task\n"
        f"Complete `{PRE_STEP}` first, then the Daily 7-Step Workflow in order. "
        "Read all charts for qualitative technical and sentiment evidence. "
        "Call `emit_daily_state` exactly once.\n\n"
        "Priorities (these survive into the report — spend your effort here):\n"
        "1. Assign `structural_bias` from chart evidence (Pre-Step). This single choice selects the "
        "Monte Carlo threshold downstream, so justify it against extension, ERP, credit, and breadth.\n"
        "2. Read charts for `signals`, `signal_alignment`, `confirming_evidence`, and "
        "`conflicting_evidence` (cite chart files in each divergence's `chart_refs`).\n"
        "3. Set `primary_tension` and a 2-4 sentence plain-text `narrative_summary`.\n"
        "4. Build `decision_matrix.rows` with all 18 framework rows using their exact labels.\n\n"
        "Numeric fields are re-verified by the engine, so do not tune them:\n"
        f"- Emit `monte_carlo` and `spx_close` as schema-valid copies from analysis_context.\n"
        f"- For these precompute-owned rows, put a brief '(engine-filled)' placeholder in "
        f"current_reading/signal: {owned_rows}.\n\n"
        "Set `framework_version` to 'daily-2026-06'."
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
        " When alignment is mixed, present qualified/hedged readings in the matrix cells without "
        "altering the validated signal values."
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
        "Write the full daily markdown report for an already-decided posture. The validated state is "
        "final: do not introduce or imply signal readings that contradict its structural_bias, "
        "signal_alignment, decision_matrix, or recommended action. Your job is exposition and "
        "reconciliation, not re-deciding.\n\n"
        f"Recommended action (verbatim): {action!r}.\n\n"
        "Re-open charts only to add descriptive detail and to reconcile the conflicts already listed in "
        "the conflict checklist — not to form new conclusions.\n\n"
        f"Workflow headings in order:\n{pre}\n\n"
        f"After Step 2, include `## {EVIDENCE_RECONCILIATION_HEADING}` and address each listed divergence "
        "by its id (e.g. DIV-1), giving the bullish read, the bearish read, and how the framework rule "
        "resolves it.\n\n"
        "Step 5 must cite precomputed Monte Carlo from analysis_context (do not recompute).\n\n"
        f"End with `## Updated Decision Matrix` table rows: {', '.join(DECISION_MATRIX_ROWS)}."
        f"{mixed_note}"
    )
    return PromptBundle(system_role=system_role, framework=framework, body="\n\n".join(parts))
