"""Read-only archive access for the Phase 2 web viewer."""

from __future__ import annotations

import logging
import re
from pathlib import Path

from pydantic import ValidationError

from ..config import Settings, get_settings
from ..files import InputError, read_json, read_text
from ..schemas import DailyState
from .models import RunDetail, RunSummary

logger = logging.getLogger(__name__)

DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
STATE_FILENAME_PATTERN = re.compile(r"^(\d{4}-\d{2}-\d{2})-state\.json$")


class RunNotFoundError(Exception):
    """Raised when canonical artifacts for a date are missing or invalid."""


def _validate_date(date: str) -> None:
    if not DATE_PATTERN.fullmatch(date):
        raise RunNotFoundError(f"no canonical artifacts found for {date}")


def _artifact_path(base_dir: Path, date: str, suffix: str) -> Path:
    _validate_date(date)
    path = (base_dir / f"{date}{suffix}").resolve()
    if not path.is_relative_to(base_dir.resolve()):
        raise RunNotFoundError(f"no canonical artifacts found for {date}")
    return path


def _state_path(settings: Settings, date: str) -> Path:
    return _artifact_path(settings.daily_states_dir, date, "-state.json")


def _report_path(settings: Settings, date: str) -> Path:
    return _artifact_path(settings.daily_reports_dir, date, "-analysis.md")


def _load_state(path: Path) -> DailyState:
    return DailyState.model_validate(read_json(path))


def _state_to_summary(state: DailyState) -> RunSummary:
    return RunSummary(
        date=state.date,
        spx_close=state.spx_close,
        structural_bias=state.structural_bias,
        trend_regime=state.trend_regime,
        valuation_bucket=state.valuation_bucket,
        recommended_action=state.decision_matrix.recommended_action,
        signal_alignment=state.signal_alignment,
    )


def _try_load_summary(settings: Settings, date: str) -> RunSummary | None:
    state_path = settings.daily_states_dir / f"{date}-state.json"
    report_path = settings.daily_reports_dir / f"{date}-analysis.md"
    if not state_path.exists() or not report_path.exists():
        return None
    try:
        return _state_to_summary(_load_state(state_path))
    except (InputError, ValidationError, ValueError) as exc:
        logger.warning("skipping unreadable state for %s: %s", date, exc)
        return None


def list_runs(settings: Settings | None = None) -> list[RunSummary]:
    """List archived runs that have both state and report, newest first."""
    settings = settings or get_settings()
    states_dir = settings.daily_states_dir
    if not states_dir.exists():
        return []

    summaries: list[RunSummary] = []
    for path in states_dir.glob("*-state.json"):
        match = STATE_FILENAME_PATTERN.fullmatch(path.name)
        if not match:
            continue
        summary = _try_load_summary(settings, match.group(1))
        if summary is not None:
            summaries.append(summary)

    summaries.sort(key=lambda r: r.date, reverse=True)
    return summaries


def get_run(date: str, settings: Settings | None = None) -> RunDetail:
    """Load a single run's markdown report and structured state."""
    settings = settings or get_settings()
    _validate_date(date)
    state_path = _state_path(settings, date)
    report_path = _report_path(settings, date)

    if not state_path.exists() or not report_path.exists():
        raise RunNotFoundError(f"no canonical artifacts found for {date}")

    daily_state = _load_state(state_path)
    report_markdown = read_text(report_path)
    return RunDetail(
        date=date,
        report_markdown=report_markdown,
        daily_state=daily_state,
    )
