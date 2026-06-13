"""Prompt construction for the two-pass pipeline.

All prompt text lives here (templated, version-controlled) rather than inline in
the engine. Blocks are assembled in a stable order so runs stay deterministic.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from .schemas import DailyManifest, DailyState, ExternalContext

# Canonical methodology structure -- shared with validation.py so the report
# checks stay in lockstep with what the prompt asks for.
WORKFLOW_STEPS: list[str] = [
    "Price Action & Trend Recentering",
    "Technical & Sentiment Pulse",
    "Fundamental Valuation & ERP",
    "Leverage & Margin Debt Monitor",
    "Monte Carlo & Brownian Motion",
    "Tactical Matrix",
    "Narrative & Executive Summary",
]

DECISION_MATRIX_ROWS: list[str] = [
    "Trend Regime",
    "RSI / MFI",
    "Bollinger Band",
    "ERP",
    "Leverage Risk",
    "Monte Carlo Edge",
    "Sentiment",
    "RECOMMENDED ACTION",
]

EVIDENCE_RECONCILIATION_HEADING = "Evidence Reconciliation"

HARD_CONSTRAINTS = """\
Non-negotiable constraints (from the methodology):
- A trim or re-entry is "overwhelmingly favorable" only when 3+ independent \
indicators align (3-of-5 confirmation rule).
- Never force a signal. Mixed or ambiguous data means "hold and monitor".
- Never recommend trimming the entire position; remaining equity always participates.
- Scale in and out; never recommend full deployment if the market can fall further.
- VIX > 20 is an elevated-risk flag: note reduced reliability of moving averages \
and increased forced-selling risk. VIX > 30 is crisis -- do not recommend action.
- Monte Carlo edge < 65% is insufficient: flag as monitor-only or no action.
- Analyze both confirming and conflicting evidence honestly.
- Always end with the Updated Decision Matrix."""

SYSTEM_ROLE = """\
You are a disciplined S&P 500 / SCHK tactical allocation analyst. You execute the \
provided methodology exactly and in order. You do not invent your own process or \
override the methodology's rules. You reason jointly across all supplied charts, \
the external market context, and recent session history.

Chart-reading discipline: read each chart for exact levels AND for geometry and \
divergence (e.g., MFI higher-low vs price lower-low, spreads holding stress while \
price rallies, breadth weakening while the index recovers). Reason across evidence \
layers, not chart-by-chart in isolation.

""" + HARD_CONSTRAINTS


@dataclass
class PromptBundle:
    """Components for one Claude request.

    `system_role` and `framework` are sent as system blocks (framework is the
    cacheable static prefix). `body` is the user-message text; images are added
    separately by the client in manifest order.
    """

    system_role: str
    framework: str
    body: str


def _external_block(ctx: ExternalContext) -> str:
    payload = ctx.model_dump(mode="json")
    return "## Current external market context\n```json\n" + json.dumps(payload, indent=2) + "\n```"


def _manifest_block(manifest: DailyManifest) -> str:
    lines = [
        "## Today's chart pack (images attached in this order)",
        f"Date: {manifest.date} | Index: {manifest.index_symbol} | "
        f"Instrument: {manifest.instrument_symbol} | Close: {manifest.close}",
        "",
    ]
    for c in manifest.ordered_charts():
        tf = f" [{c.timeframe}]" if c.timeframe else ""
        lines.append(f"{c.order}. {c.label}{tf} ({c.category}) -- file: {c.file}")
    return "\n".join(lines)


def _memory_block(recent_summary: str, recent_states: list[DailyState]) -> str:
    states_json = json.dumps([s.model_dump(mode="json") for s in recent_states], indent=2)
    return (
        "## Recent historical memory\n"
        f"{recent_summary}\n\n"
        "Full recent state objects (newest first):\n"
        f"```json\n{states_json}\n```"
    )


def _conflict_block(daily_state: DailyState) -> str:
    """Compact conflict checklist for Pass 2 reconciliation."""
    conflicts_json = json.dumps(
        [d.model_dump(mode="json") for d in daily_state.conflicting_evidence],
        indent=2,
    )
    confirming = "\n".join(f"- {item}" for item in daily_state.confirming_evidence) or "- (none listed)"
    return (
        "## Conflict checklist (from validated state)\n"
        f"Primary tension: {daily_state.primary_tension}\n\n"
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
    framework: str,
    manifest: DailyManifest,
    external_context: ExternalContext,
    recent_states: list[DailyState],
    recent_summary: str,
) -> PromptBundle:
    """Pass 1: produce schema-valid DailyState JSON."""
    body = "\n\n".join(
        [
            _memory_block(recent_summary, recent_states),
            _external_block(external_context),
            _manifest_block(manifest),
            (
                "## Task\n"
                "Work through the methodology's Daily 7-Step Workflow in order, reasoning "
                "across every chart and the external context. Then call the `emit_daily_state` "
                "tool exactly once with the structured result.\n\n"
                "Before calling the tool, you MUST:\n"
                "1. Compute `signal_alignment` from the 3-of-5 confirmation table (Layer 2D / "
                "Step 6): count trim signals met (0-5), buy signals met (0-5), and set `overall` "
                "to aligned_trim (3+ trim), aligned_buy (3+ buy), mixed (material cross-layer "
                "tensions or neither side reaches 3), or neutral.\n"
                "2. List bullet points of genuinely confirming evidence in `confirming_evidence`.\n"
                "3. Enumerate EVERY material cross-layer tension in `conflicting_evidence`. For "
                "each Divergence: assign a stable `id`, name the `layers` in conflict, state the "
                "`bullish_read` and `bearish_read`, cite the governing `framework_rule` from the "
                "methodology, assign `weight` (high/medium/low), and list `chart_refs` (exact "
                "filenames from the manifest) that show each side of the conflict.\n"
                "4. Set `primary_tension` to the single most decision-relevant conflict today.\n"
                "5. Populate `monte_carlo` with all Step 5 outputs (prob_up_first, prob_down_first, "
                "conditional_cascade, median_days, cash_drag_prob, meets_threshold).\n"
                "6. Compare today against recent sessions and capture genuine day-over-day changes "
                "in `what_changed_today`.\n\n"
                "Keep `narrative_summary` to a concise 2-4 sentence, single-paragraph synthesis "
                "in plain text (no line breaks, no step headers, no markdown) — the full "
                "step-by-step write-up and Evidence Reconciliation belong only in the later report. "
                "Use null for any signal you cannot determine from the evidence. Honor every hard "
                "constraint, including the no-forced-signal rule."
            ),
        ]
    )
    return PromptBundle(system_role=SYSTEM_ROLE, framework=framework, body=body)


def build_report_prompt(
    *,
    framework: str,
    daily_state: DailyState,
    manifest: DailyManifest,
    external_context: ExternalContext,
    recent_states: list[DailyState],
    recent_summary: str,
) -> PromptBundle:
    """Pass 2: produce the markdown report scaffolded by the validated state."""
    state_json = json.dumps(daily_state.model_dump(mode="json"), indent=2)
    steps = "\n".join(f"{i + 1}. {s}" for i, s in enumerate(WORKFLOW_STEPS))
    action = daily_state.decision_matrix.recommended_action
    mixed = daily_state.signal_alignment.overall == "mixed"
    mixed_note = (
        " Because signal alignment is mixed, Decision Matrix rows MUST use qualified "
        "readings (e.g., 'Fear (mixed)', 'Moderate-to-Elevated') — do not flatten into "
        "a uniformly bullish or bearish tone."
        if mixed
        else ""
    )
    body = "\n\n".join(
        [
            _memory_block(recent_summary, recent_states),
            _external_block(external_context),
            _manifest_block(manifest),
            (
                "## Validated daily state (immutable facts)\n"
                f"```json\n{state_json}\n```"
            ),
            _conflict_block(daily_state),
            (
                "## Task\n"
                "Write the full daily markdown analysis report. Re-open the attached charts "
                "to reconcile conflicting evidence — your job is interpretation, not re-decision.\n\n"
                "IMMUTABLE (do not recompute or contradict): numeric signals, `signal_alignment`, "
                "`monte_carlo` values, and `decision_matrix.recommended_action` "
                f"({action!r}).\n\n"
                "Follow the methodology's Daily 7-Step Workflow in this exact order, using a clear "
                f"heading for each step:\n{steps}\n\n"
                f"Within or immediately after Step 2, include a '## {EVIDENCE_RECONCILIATION_HEADING}' "
                "section that opens by restating `primary_tension` in your own words. Then, for EACH "
                "item in `conflicting_evidence`, re-examine the cited `chart_refs` and explain: the "
                "bullish read, the bearish read, which chart shows each side, the framework rule that "
                "governs the conflict, and whether it blocks trim, buy, or both.\n\n"
                "In Step 7, explicitly answer: given mixed/conflicting evidence, why does today's "
                f"evidence resolve to {action!r}? Cite `primary_tension`, the 3-of-5 rule, Monte "
                "Carlo threshold, and any VIX/ERP gates that apply.\n\n"
                "The report MUST end with the '## Updated Decision Matrix' as a markdown table "
                f"containing these rows: {', '.join(DECISION_MATRIX_ROWS)}."
                f"{mixed_note} "
                "If the data are mixed, explicitly recommend 'hold and monitor'. Output only the "
                "markdown report."
            ),
        ]
    )
    return PromptBundle(system_role=SYSTEM_ROLE, framework=framework, body=body)
