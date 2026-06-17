"""Validation of the structured state and the markdown report."""

from __future__ import annotations

import re
from typing import Any

from pydantic import ValidationError

from .prompts import DECISION_MATRIX_ROWS, EVIDENCE_RECONCILIATION_HEADING, PRE_STEP, WORKFLOW_STEPS
from .schemas import DailyState, ValidationIssue, ValidationReport


def parse_daily_state(
    tool_input: dict[str, Any], date: str
) -> tuple[DailyState | None, ValidationReport]:
    issues: list[ValidationIssue] = []
    try:
        state = DailyState.model_validate(tool_input)
    except ValidationError as exc:
        for err in exc.errors():
            loc = ".".join(str(p) for p in err["loc"])
            issues.append(
                ValidationIssue(severity="error", code="schema", message=f"{loc}: {err['msg']}")
            )
        return None, ValidationReport(date=date, target="daily_state", passed=False, issues=issues)

    if state.date != date:
        issues.append(
            ValidationIssue(
                severity="warning",
                code="date_mismatch",
                message=f"state.date ({state.date}) does not match run date ({date})",
            )
        )

    issues.extend(_validate_decision_matrix(state))

    passed = not any(i.severity == "error" for i in issues)
    return state, ValidationReport(date=date, target="daily_state", passed=passed, issues=issues)


def _validate_decision_matrix(state: DailyState) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    rows = state.decision_matrix.rows
    if not rows:
        issues.append(
            ValidationIssue(
                severity="error",
                code="empty_decision_matrix",
                message="decision_matrix.rows must not be empty",
            )
        )
        return issues

    has_action = any(
        r.signal_layer.strip().lower() == "recommended action" for r in rows
    )
    if not has_action:
        issues.append(
            ValidationIssue(
                severity="error",
                code="missing_recommended_action",
                message="decision_matrix must include a Recommended Action row",
            )
        )

    if len(rows) != len(DECISION_MATRIX_ROWS):
        issues.append(
            ValidationIssue(
                severity="warning",
                code="decision_matrix_row_count",
                message=(
                    f"decision_matrix has {len(rows)} rows; "
                    f"framework expects {len(DECISION_MATRIX_ROWS)}"
                ),
            )
        )

    expected_layers = {layer.lower() for layer in DECISION_MATRIX_ROWS}
    actual_layers = {r.signal_layer.strip().lower() for r in rows}
    missing_layers = expected_layers - actual_layers
    if missing_layers:
        issues.append(
            ValidationIssue(
                severity="warning",
                code="decision_matrix_missing_layers",
                message=f"decision_matrix missing signal layers: {sorted(missing_layers)}",
            )
        )

    return issues


def validation_errors_text(report: ValidationReport) -> str:
    return "\n".join(f"- {i.message}" for i in report.errors)


def _hold_or_monitor_action(action: str) -> bool:
    lowered = action.lower()
    return "hold" in lowered or "monitor" in lowered


def _report_lower(report_md: str) -> str:
    return report_md.lower()


def _evidence_reconciliation_section(report_md: str) -> str:
    match = re.search(
        r"^#{1,6}\s.*" + re.escape(EVIDENCE_RECONCILIATION_HEADING),
        report_md,
        re.IGNORECASE | re.MULTILINE,
    )
    if match is None:
        return ""
    start = match.start()
    next_heading = re.search(r"^#{1,6}\s", report_md[match.end() :], re.MULTILINE)
    end = match.end() + next_heading.start() if next_heading else len(report_md)
    return report_md[start:end]


def _mentions_tension(report_md: str, tension: str) -> bool:
    section = _evidence_reconciliation_section(report_md)
    if not section.strip() or not tension.strip():
        return False
    lowered = section.lower()
    if tension.lower() in lowered:
        return True
    tokens = [t for t in re.findall(r"[a-z0-9]+", tension.lower()) if len(t) >= 4]
    if not tokens:
        return tension.lower() in lowered
    hits = sum(1 for t in tokens if t in lowered)
    return hits >= max(2, (len(tokens) + 1) // 2)


def _conflict_addressed(report_md: str, divergence_id: str, bullish: str, bearish: str) -> bool:
    lowered = _report_lower(report_md)
    if divergence_id.lower().replace("_", " ") in lowered:
        return True
    if divergence_id.lower().replace("_", "-") in lowered:
        return True
    bull_tokens = [t for t in re.findall(r"[a-z0-9]+", bullish.lower()) if len(t) >= 5][:3]
    bear_tokens = [t for t in re.findall(r"[a-z0-9]+", bearish.lower()) if len(t) >= 5][:3]
    bull_hits = sum(1 for t in bull_tokens if t in lowered)
    bear_hits = sum(1 for t in bear_tokens if t in lowered)
    return bull_hits >= 1 and bear_hits >= 1


def _matrix_uniformly_directional(report_md: str) -> bool:
    matrix_match = re.search(
        r"^#{1,6}\s.*Decision Matrix", report_md, re.IGNORECASE | re.MULTILINE
    )
    if matrix_match is None:
        return False
    tail = report_md[matrix_match.start() :]
    mixed_markers = ("mixed", "caution", "monitor", "insufficient", "neutral", "within")
    if any(m in tail.lower() for m in mixed_markers):
        return False
    bullish = sum(1 for w in ("bull", "greed", "actionable", "attractive") if w in tail.lower())
    bearish = sum(1 for w in ("bear", "fear", "trim", "ceiling") if w in tail.lower())
    return bullish >= 3 and bearish == 0


def validate_report(
    report_md: str,
    date: str,
    max_chars: int,
    daily_state: DailyState | None = None,
) -> ValidationReport:
    issues: list[ValidationIssue] = []

    if not report_md.strip():
        issues.append(
            ValidationIssue(severity="error", code="empty", message="report is empty")
        )
        return ValidationReport(date=date, target="report", passed=False, issues=issues)

    pre_match = re.search(
        r"^#{1,6}\s.*" + re.escape(PRE_STEP.split()[0]),
        report_md,
        re.IGNORECASE | re.MULTILINE,
    )
    if pre_match is None and not re.search(r"Structural Regime", report_md, re.IGNORECASE):
        issues.append(
            ValidationIssue(
                severity="warning",
                code="missing_pre_step",
                message=f"missing pre-step heading: {PRE_STEP}",
            )
        )

    last_pos = -1
    out_of_order = False
    for step in WORKFLOW_STEPS:
        key = step.split(" & ")[0].split(" (")[0]
        match = re.search(
            r"^#{1,6}\s.*" + re.escape(key), report_md, re.IGNORECASE | re.MULTILINE
        )
        if not match:
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="missing_step",
                    message=f"missing workflow step heading: {step}",
                )
            )
            continue
        if match.start() < last_pos:
            out_of_order = True
        last_pos = match.start()

    if out_of_order:
        issues.append(
            ValidationIssue(
                severity="warning",
                code="step_order",
                message="workflow step headings appear out of methodology order",
            )
        )

    matrix_match = re.search(
        r"^#{1,6}\s.*Decision Matrix", report_md, re.IGNORECASE | re.MULTILINE
    )
    if matrix_match is None:
        issues.append(
            ValidationIssue(
                severity="error",
                code="missing_decision_matrix",
                message="report is missing the Updated Decision Matrix",
            )
        )
    else:
        missing_rows = [
            row for row in DECISION_MATRIX_ROWS if row.lower() not in report_md.lower()
        ]
        if missing_rows:
            issues.append(
                ValidationIssue(
                    severity="warning",
                    code="decision_matrix_rows",
                    message=f"decision matrix may be missing rows: {missing_rows}",
                )
            )
        if re.search(r"^#{1,6}\s", report_md[matrix_match.end() :], re.MULTILINE):
            issues.append(
                ValidationIssue(
                    severity="warning",
                    code="matrix_not_last",
                    message="content appears after the Updated Decision Matrix; it should be the final section",
                )
            )

    if len(report_md) > max_chars:
        issues.append(
            ValidationIssue(
                severity="warning",
                code="too_long",
                message=f"report is {len(report_md)} chars (> {max_chars} hint)",
            )
        )

    if daily_state is not None:
        mixed_day = (
            daily_state.signal_alignment.overall == "mixed"
            or _hold_or_monitor_action(daily_state.decision_matrix.recommended_action)
        )
        if mixed_day:
            recon_match = re.search(
                r"^#{1,6}\s.*" + re.escape(EVIDENCE_RECONCILIATION_HEADING),
                report_md,
                re.IGNORECASE | re.MULTILINE,
            )
            if recon_match is None:
                issues.append(
                    ValidationIssue(
                        severity="error",
                        code="missing_evidence_reconciliation",
                        message=f"mixed-signal day requires '## {EVIDENCE_RECONCILIATION_HEADING}' section",
                    )
                )
            elif not _mentions_tension(report_md, daily_state.primary_tension):
                issues.append(
                    ValidationIssue(
                        severity="error",
                        code="missing_primary_tension",
                        message="report does not address primary_tension from validated state",
                    )
                )

            for div in daily_state.conflicting_evidence:
                if div.weight != "high":
                    continue
                if not _conflict_addressed(
                    report_md, div.id, div.bullish_read, div.bearish_read
                ):
                    issues.append(
                        ValidationIssue(
                            severity="warning",
                            code="missing_high_weight_conflict",
                            message=f"high-weight conflict not addressed: {div.id}",
                        )
                    )

            if (
                daily_state.signal_alignment.overall == "mixed"
                and _matrix_uniformly_directional(report_md)
            ):
                issues.append(
                    ValidationIssue(
                        severity="warning",
                        code="matrix_uniformly_directional",
                        message="decision matrix reads uniformly directional despite mixed alignment",
                    )
                )

    passed = not any(i.severity == "error" for i in issues)
    return ValidationReport(date=date, target="report", passed=passed, issues=issues)
