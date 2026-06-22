"""Load and resolve forward/trailing EPS from the master history file."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from pydantic import ValidationError

from .config import Settings, get_settings
from .files import InputError, read_json
from .schemas import EpsHistory, EpsHistoryEntry, ResolvedEps


@dataclass
class EpsResolution:
    eps: ResolvedEps | None
    source: Literal["master", "missing"]
    effective_from: str | None
    forward_eps: float | None
    trailing_eps: float | None
    warnings: list[str] = field(default_factory=list)


def load_eps_history(settings: Settings | None = None) -> EpsHistory | None:
    settings = settings or get_settings()
    path = settings.eps_history_path
    if not path.is_file():
        return None
    try:
        return EpsHistory.model_validate(read_json(path))
    except ValidationError as exc:
        raise InputError(f"invalid EPS history in {path}: {exc}") from exc


def resolve_eps_for_date(run_date: str, history: EpsHistory) -> EpsHistoryEntry | None:
    qualifying = [e for e in history.entries if e.effective_from <= run_date]
    if not qualifying:
        return None
    qualifying.sort(key=lambda e: e.effective_from)
    return qualifying[-1]


def earliest_effective_from(history: EpsHistory) -> str:
    return min(e.effective_from for e in history.entries)


def get_eps_for_run(run_date: str, *, settings: Settings | None = None) -> EpsResolution:
    settings = settings or get_settings()
    path = settings.eps_history_path
    try:
        history = load_eps_history(settings)
    except InputError as exc:
        return EpsResolution(
            eps=None,
            source="missing",
            effective_from=None,
            forward_eps=None,
            trailing_eps=None,
            warnings=[str(exc)],
        )
    if history is None:
        return EpsResolution(
            eps=None,
            source="missing",
            effective_from=None,
            forward_eps=None,
            trailing_eps=None,
            warnings=[f"EPS history file not found: {path}"],
        )

    entry = resolve_eps_for_date(run_date, history)
    if entry is None:
        earliest = earliest_effective_from(history)
        return EpsResolution(
            eps=None,
            source="missing",
            effective_from=None,
            forward_eps=None,
            trailing_eps=None,
            warnings=[
                f"No qualifying EPS entry for {run_date} in {path} "
                f"(earliest entry: {earliest})"
            ],
        )

    eps = ResolvedEps(
        forward_eps=entry.forward_eps,
        trailing_eps=entry.trailing_eps,
        effective_from=entry.effective_from,
    )
    return EpsResolution(
        eps=eps,
        source="master",
        effective_from=entry.effective_from,
        forward_eps=entry.forward_eps,
        trailing_eps=entry.trailing_eps,
        warnings=[],
    )


def eps_resolution_error_message(
    run_date: str, resolution: EpsResolution, settings: Settings
) -> str:
    if resolution.warnings:
        return resolution.warnings[0]
    return (
        f"No qualifying EPS entry for {run_date} in {settings.eps_history_path} "
        "— append a row with effective_from on or before the run date"
    )


def require_eps_for_run(
    run_date: str, *, settings: Settings | None = None
) -> tuple[ResolvedEps, EpsResolution]:
    settings = settings or get_settings()
    resolution = get_eps_for_run(run_date, settings=settings)
    if resolution.eps is None:
        raise InputError(eps_resolution_error_message(run_date, resolution, settings))
    return resolution.eps, resolution


def eps_resolution_log(resolution: EpsResolution) -> dict[str, object]:
    return {
        "source": resolution.source,
        "effective_from": resolution.effective_from,
        "forward_eps": resolution.forward_eps,
        "trailing_eps": resolution.trailing_eps,
    }
