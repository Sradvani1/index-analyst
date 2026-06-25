"""Prompt construction for the two-pass pipeline."""

from __future__ import annotations

import json
from dataclasses import dataclass

from .schemas import AnalysisContext, ChartEntry, DailyManifest, DailyState, ResolvedEps

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

EVIDENCE_RECONCILIATION_HEADING = "Evidence Reconciliation"  # legacy; Pass 2 uses EVIDENCE_AND_TENSIONS_HEADING

INVESTOR_REPORT_SECTIONS: list[str] = [
    "Today's Posture",
    "Market Regime",
    "Price and Trend",
    "Technicals and Sentiment",
    "Valuation and ERP",
    "Risk and Monte Carlo",
    "Tactical Levels and Next Session Plan",
    "Evidence and Tensions",
    "Updated Decision Matrix",
]

PASS2_PROSE_SECTIONS: list[str] = INVESTOR_REPORT_SECTIONS[:-1]

EVIDENCE_AND_TENSIONS_HEADING = "Evidence and Tensions"

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
rows after Pass 1, so spend your effort on the qualitative chart reads and structural_bias, not on \
transcribing numbers precisely.
- Pass 1: emit decision_matrix.rows with all 18 framework rows via emit_daily_state.
- Pass 2: prose only — eight ## sections ending with Evidence and Tensions; do not emit a # title, \
injected fact blocks, or Updated Decision Matrix (Python assembles those for publish)."""


def load_system_role(role_text: str) -> str:
    return role_text.strip() + "\n\n" + HARD_CONSTRAINTS


@dataclass
class PromptBundle:
    system_role: str
    framework: str
    body: str


def _eps_block(eps: ResolvedEps) -> str:
    payload = eps.model_dump(mode="json")
    return "## EPS inputs (resolved from master history)\n```json\n" + json.dumps(payload, indent=2) + "\n```"


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


def _pass2_manifest_block(
    attached: list[ChartEntry],
    reference_only: list[ChartEntry],
    manifest: DailyManifest,
) -> str:
    lines = [
        "## Pass 2 chart pack",
        f"Date: {manifest.date} | Index: {manifest.index_symbol} | "
        f"Reference close (validation only): {manifest.close}",
        "",
    ]
    if attached:
        lines.append(f"Attached images ({len(attached)}) — inspectable evidence:")
        for i, c in enumerate(attached, start=1):
            tf = f" [{c.timeframe}]" if c.timeframe else ""
            lines.append(f"  {i}. {c.label}{tf} ({c.file})")
    else:
        lines.append("Attached images (0) — no chart images are attached for this pass.")

    lines.append("")
    if reference_only:
        lines.append("Reference only (not attached) — filename visible, not visually inspectable:")
        for c in reference_only:
            tf = f" [{c.timeframe}]" if c.timeframe else ""
            lines.append(f"  - {c.label}{tf} ({c.file})")
    else:
        lines.append("Reference only (not attached): (none)")

    lines.extend(
        [
            "",
            "Authority: Attached images may be used for descriptive detail and conflict reconciliation.",
            "Reference-only charts may be cited by filename and explained using validated state only.",
            "Do NOT infer fresh numeric values, new divergences, or pixel-level observations from "
            "reference-only charts.",
        ]
    )
    return "\n".join(lines)


def _optional_memory_block(recent_summary: str | None) -> str:
    if not recent_summary:
        return ""
    return (
        "## Prior posture snapshot (continuity only — not authoritative for today's numerics)\n"
        "Each run is a fresh analysis. Use this block only to track regime shifts, action posture, "
        "day-over-day changes, and unresolved tensions. All calculations, thresholds, targets, and "
        "price levels come from today's analysis_context and charts — never from prior sessions.\n\n"
        f"{recent_summary}"
    )


def _investor_fact_snippets(analysis_context: AnalysisContext) -> str:
    v = analysis_context.valuation
    mc = analysis_context.monte_carlo
    s = analysis_context.structure
    m = analysis_context.market_data
    lines = [
        "## Read-only fact snippets (Python injects these under sections 5–7 — do not duplicate numerics in prose)",
        "",
        "**Valuation and ERP (section 5):**",
        f"- Forward P/E: {v.forward_pe}x | Trailing P/E: {v.trailing_pe}x",
        f"- Forward earnings yield: {v.forward_earnings_yield:.2%}" if v.forward_earnings_yield else "- Forward earnings yield: n/a",
        f"- 10-year Treasury: {m.us10y:.3f}%",
        f"- ERP: {v.erp:.2%} ({v.erp_trend})" if v.erp is not None else "- ERP: n/a",
        f"- ERP re-entry floor at 0.5% ERP: {v.erp_reentry_floor_at_0_5pct:,.2f}"
        if v.erp_reentry_floor_at_0_5pct is not None
        else "- ERP re-entry floor: n/a",
        "",
        "**Risk and Monte Carlo (section 6):**",
        f"- σ (20d realized vol): {mc.sigma:.4f} | μ (drift): {mc.mu:.4f}",
        f"- Raw up-first: {mc.prob_up_first_raw:.1%} | Raw down-first: {mc.prob_down_first_raw:.1%}",
        f"- Adjusted up-first: {mc.prob_up_first_adjusted:.1%} | Adjusted down-first: {mc.prob_down_first_adjusted:.1%}",
        f"- Rally exhaustion: {mc.rally_exhaustion_score} (discount {mc.exhaustion_discount:.0%})",
        f"- Upside target: {mc.upside_target:,.2f} ({mc.upside_target_rule})",
        f"- Downside target: {mc.downside_target:,.2f} ({mc.downside_target_rule})",
        f"- Median days: {mc.median_days} | Cascades: {mc.cascades}",
        "",
        "**Tactical levels (section 7):**",
        f"- Active swing high: {s.active_swing_high_price:,.2f} ({s.active_swing_high_date})",
        f"- Active swing low: {s.active_swing_low_price:,.2f} ({s.active_swing_low_date})",
        f"- Fib 23.6%: {s.fib_236:,.2f} | 38.2%: {s.fib_382:,.2f} | 50%: {s.fib_500:,.2f} | 61.8%: {s.fib_618:,.2f}",
        f"- Liquidation caution: {s.liquidation_caution:,.2f} | nervous: {s.liquidation_nervous:,.2f}",
        f"- Margin call: {s.liquidation_margin_call:,.2f} | cascade: {s.liquidation_cascade:,.2f}",
    ]
    return "\n".join(lines)


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
    resolved_eps: ResolvedEps,
    analysis_context: AnalysisContext,
    recent_summary: str | None = None,
) -> PromptBundle:
    parts = [
        _analysis_context_block(analysis_context),
        _eps_block(resolved_eps),
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
        "`signals` contract (schema is strict — extra keys fail validation):\n"
        "- Use only keys defined on `emit_daily_state.signals`; no `*_detail`, `*_note`, or extra "
        "`*_zone` fields.\n"
        "- `fear_greed` + `fear_greed_zone` is the only score+label pair.\n"
        "- `vix_regime`: one string with zone and level/MA context; no `vix_regime_detail` or "
        "`signals.vix`.\n"
        "- `put_call`: numeric ratio only; no `put_call_zone`.\n\n"
        "`what_changed_today` contract:\n"
        "- Must be a JSON array of 3–5 strings (never a single string).\n"
        "- Each item: one material change vs prior session (price structure, VIX, "
        "breadth/credit, valuation, Monte Carlo).\n"
        "- Compare against prior posture snapshot when memory is present.\n\n"
        "Divergences and zone labels:\n"
        "- RSI/MFI divergences belong in `conflicting_evidence`, not new `signals` keys.\n"
        "- No `rsi_divergence`, `rsi14_zone`, `mfi_zone`, or other invented signal fields.\n\n"
        "Set `framework_version` to 'daily-2026-06'."
    )
    return PromptBundle(system_role=system_role, framework=framework, body="\n\n".join(parts))


def build_report_prompt(
    *,
    system_role: str,
    framework: str,
    daily_state: DailyState,
    manifest: DailyManifest,
    resolved_eps: ResolvedEps,
    analysis_context: AnalysisContext,
    recent_summary: str | None = None,
    pass2_attached: list[ChartEntry] | None = None,
    pass2_reference_only: list[ChartEntry] | None = None,
    pass2_optimization_enabled: bool = True,
) -> PromptBundle:
    state_json = json.dumps(daily_state.model_dump(mode="json"), indent=2)
    section_list = "\n".join(f"{i + 1}. `## {title}`" for i, title in enumerate(PASS2_PROSE_SECTIONS))
    action = daily_state.decision_matrix.recommended_action
    mixed = daily_state.signal_alignment.overall == "mixed"
    mixed_note = (
        " When alignment is mixed, present qualified/hedged readings without altering validated signal values."
        if mixed
        else ""
    )

    if pass2_optimization_enabled and pass2_attached is not None and pass2_reference_only is not None:
        chart_block = _pass2_manifest_block(pass2_attached, pass2_reference_only, manifest)
    else:
        chart_block = _manifest_block(manifest)

    parts = [
        _analysis_context_block(analysis_context),
        _eps_block(resolved_eps),
        chart_block,
        _investor_fact_snippets(analysis_context),
        f"## Validated daily state (immutable)\n```json\n{state_json}\n```",
        _conflict_block(daily_state),
    ]
    mem = _optional_memory_block(recent_summary)
    if mem:
        parts.insert(0, mem)

    pass2_task_extra = ""
    if pass2_optimization_enabled and pass2_attached is not None:
        pass2_task_extra = (
            "\n\nPass 2 chart authority:\n"
            "- Attached images: reconciliation and descriptive detail for listed conflicts only where cited.\n"
            "- Reference-only charts: workflow citations from validated state / conflict checklist text only.\n"
            "- Do not contradict validated state.\n"
            "- Prior-run posture block (if present): continuity only — not today's chart evidence.\n"
            "- When attached-image impressions, prompt wording, and validated daily state differ, "
            "validated daily state is authoritative."
        )

    parts.append(
        "## Task\n"
        "Pass 1 already completed in a separate API call — structured state was emitted via "
        "`emit_daily_state`. Do NOT call tools or emit JSON in this pass. Your entire response "
        "must be markdown prose only.\n\n"
        "Write investor-facing narrative for an already-decided posture. The validated state is "
        "final: do not introduce or imply signal readings that contradict its structural_bias, "
        "signal_alignment, decision_matrix, or recommended action. Your job is exposition and "
        "reconciliation, not re-deciding.\n\n"
        f"Recommended action (verbatim): {action!r}.\n\n"
        "Re-open charts only to add descriptive detail and to reconcile the conflicts already listed in "
        "the conflict checklist — not to form new conclusions.\n\n"
        "Output exactly these eight `##` sections in order — nothing else:\n"
        f"{section_list}\n\n"
        "Do NOT emit:\n"
        "- A `#` title line or Header Snapshot (Python assembles the preamble)\n"
        "- Injected numeric fact blocks under sections 5–7 (Python inserts them during assembly)\n"
        "- `## Updated Decision Matrix` (Python renders the matrix from validated state)\n\n"
        "Tone: write for market participants, not internal framework review. No methodology "
        "meta-commentary (e.g. 'Step 2 requires…'). Do not regenerate numerics in prose where "
        "Python injects a facts block — interpret the read-only snippets instead.\n\n"
        "Section budgets: Today's Posture 150–250 words (lead with action); Market Regime 200–300; "
        "Price and Trend through Tactical Levels 150–350 each; Evidence and Tensions ≥100 words when "
        "no divergences remain.\n\n"
        f"`## {EVIDENCE_AND_TENSIONS_HEADING}` is required every run. For each item in "
        "conflicting_evidence from the conflict checklist, give the bullish read, the bearish read, "
        "and how the framework rule resolves it. On zero-divergence days, cover primary_tension "
        "and confirming evidence explicitly."
        f"{mixed_note}"
        f"{pass2_task_extra}"
    )
    return PromptBundle(system_role=system_role, framework=framework, body="\n\n".join(parts))
