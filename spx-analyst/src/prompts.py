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
                "tool exactly once with the structured result. Compare today against the recent "
                "sessions above and capture genuine day-over-day changes in `what_changed_today`. "
                "Keep `narrative_summary` to a concise 2-4 sentence, single-paragraph synthesis "
                "in plain text (no line breaks, no step headers, no markdown) — the full "
                "step-by-step write-up belongs only in the later report, not in this field. "
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
    body = "\n\n".join(
        [
            _memory_block(recent_summary, recent_states),
            _external_block(external_context),
            _manifest_block(manifest),
            (
                "## Validated daily state (use as the factual backbone)\n"
                f"```json\n{state_json}\n```"
            ),
            (
                "## Task\n"
                "Write the full daily markdown analysis report. Follow the methodology's "
                "Daily 7-Step Workflow in this exact order, using a clear heading for each step:\n"
                f"{steps}\n\n"
                "Keep numbers consistent with the validated state above. Discuss both confirming "
                "and conflicting evidence. The report MUST end with the '## Updated Decision Matrix' "
                "as a markdown table containing these rows: "
                f"{', '.join(DECISION_MATRIX_ROWS)}. "
                "If the data are mixed, explicitly recommend 'hold and monitor'. Output only the "
                "markdown report."
            ),
        ]
    )
    return PromptBundle(system_role=SYSTEM_ROLE, framework=framework, body=body)
