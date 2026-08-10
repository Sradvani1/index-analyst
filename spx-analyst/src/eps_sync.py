"""Synchronize the master EPS history from StreetStats."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Literal

from .config import Settings, get_settings
from .eps_history import get_eps_for_run, load_eps_history
from .files import EPS_SOURCE_FILENAME, InputError, write_json_atomic
from .schemas import EpsHistory
from .streetstats_eps import StreetStatsError, fetch_streetstats_history

SyncStatus = Literal["updated", "fallback", "missing"]


@dataclass(frozen=True)
class EpsSyncResult:
    status: SyncStatus
    requested_for: str
    provider: str = "streetstats"
    source_as_of_date: str | None = None
    forward_eps: float | None = None
    trailing_eps: float | None = None
    retrieved_at: str | None = None
    response_sha256: str | None = None
    history_sha256: str | None = None
    error: str | None = None


def _write_sync_artifact(run_date: str, result: EpsSyncResult, settings: Settings) -> None:
    path = settings.runs_dir / run_date / EPS_SOURCE_FILENAME
    write_json_atomic(path, dataclasses.asdict(result))


def _ensure_history_not_truncated(history: EpsHistory, settings: Settings) -> None:
    """Reject a valid-looking response that drops dates from the local history."""
    try:
        existing = load_eps_history(settings)
    except InputError:
        return
    if existing is None:
        return

    existing_dates = {entry.effective_from for entry in existing.entries}
    fetched_dates = {entry.effective_from for entry in history.entries}
    missing = sorted(existing_dates - fetched_dates)
    if missing:
        sample = ", ".join(missing[:3])
        if len(missing) > 3:
            sample += ", ..."
        raise StreetStatsError(
            "StreetStats growth history appears truncated: "
            f"{len(missing)} existing date(s) are missing ({sample})"
        )


def sync_eps_for_date(
    run_date: str,
    *,
    settings: Settings | None = None,
) -> EpsSyncResult:
    """Attempt one source sync; fall back to the existing local history without retrying."""
    settings = settings or get_settings()
    try:
        fetched = fetch_streetstats_history(run_date, settings=settings)
        _ensure_history_not_truncated(fetched.history, settings)
        write_json_atomic(settings.eps_history_path, fetched.history)
        result = EpsSyncResult(
            status="updated",
            requested_for=run_date,
            source_as_of_date=fetched.source_as_of_date,
            forward_eps=fetched.forward_eps,
            trailing_eps=fetched.trailing_eps,
            retrieved_at=fetched.retrieved_at,
            response_sha256=fetched.response_sha256,
            history_sha256=fetched.history_sha256,
        )
    except (StreetStatsError, InputError, OSError) as exc:
        local = get_eps_for_run(run_date, settings=settings)
        if local.eps is None:
            result = EpsSyncResult(
                status="missing",
                requested_for=run_date,
                error=str(exc),
            )
        else:
            result = EpsSyncResult(
                status="fallback",
                requested_for=run_date,
                source_as_of_date=local.effective_from,
                forward_eps=local.forward_eps,
                trailing_eps=local.trailing_eps,
                error=str(exc),
            )

    _write_sync_artifact(run_date, result, settings)
    return result
