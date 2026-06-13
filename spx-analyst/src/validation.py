"""Validation of the structured state and the markdown report.

State validation is schema conformance (Pydantic). Report validation checks that
the methodology's workflow steps and the Updated Decision Matrix are present.
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import ValidationError

from .prompts import DECISION_MATRIX_ROWS, WORKFLOW_STEPS
from .schemas import DailyState, ValidationIssue, ValidationReport


def parse_daily_state(
    tool_input: dict[str, Any], date: str
) -> tuple[DailyState | None, ValidationReport]:
    """Parse and schema-validate the Pass 1 tool output."""
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
    return state, ValidationReport(date=date, target="daily_state", passed=True, issues=issues)


def validation_errors_text(report: ValidationReport) -> str:
    return "\n".join(f"- {i.message}" for i in report.errors)


def validate_report(report_md: str, date: str, max_chars: int) -> ValidationReport:
    issues: list[ValidationIssue] = []

    if not report_md.strip():
        issues.append(
            ValidationIssue(severity="error", code="empty", message="report is empty")
        )
        return ValidationReport(date=date, target="report", passed=False, issues=issues)

    # Each workflow step should appear as a heading, in order.
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

    # Updated Decision Matrix must be present and should be the final section.
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
        # Acceptance criterion: the report should END with the decision matrix.
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

    passed = not any(i.severity == "error" for i in issues)
    return ValidationReport(date=date, target="report", passed=passed, issues=issues)
