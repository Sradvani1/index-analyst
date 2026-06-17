"""Rolling operational memory: load recent daily states and summarize them.

This is the engine's main continuity mechanism. The Claude API is stateless at
the application level, so prior context must be reloaded and reintroduced here.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError

from .config import Settings, get_settings
from .files import InputError, read_json
from .schemas import DailyState


def _state_date(path: Path) -> str:
    # Filenames look like 2026-06-11-state.json -> 2026-06-11
    return path.name.replace("-state.json", "")


def load_recent_states(
    limit: int | None = None,
    *,
    before_date: str | None = None,
    settings: Settings | None = None,
) -> list[DailyState]:
    """Return up to `limit` most recent valid DailyState objects, newest first.

    Malformed state files are skipped (a stale file should not break a new run).
    `before_date` excludes the current run's own state when present.
    """
    settings = settings or get_settings()
    limit = settings.recent_state_count if limit is None else limit

    states_dir = settings.daily_states_dir
    if not states_dir.is_dir():
        return []

    files = sorted(states_dir.glob("*-state.json"), key=_state_date, reverse=True)

    states: list[DailyState] = []
    for path in files:
        date = _state_date(path)
        if before_date is not None and date >= before_date:
            continue
        try:
            states.append(DailyState.model_validate(read_json(path)))
        except (ValidationError, ValueError, InputError):
            continue
        if len(states) >= limit:
            break
    return states


def build_recent_summary(states: list[DailyState]) -> str:
    """Compact, human- and model-readable rollup of recent sessions.

    Ordered oldest-to-newest so trend development reads naturally.
    """
    if not states:
        return "No prior sessions on record."

    lines = ["Recent sessions (oldest to newest):"]
    for s in reversed(states):
        action = s.decision_matrix.recommended_action
        vix_txt = (
            f"VIX regime {s.signals.vix_regime}"
            if s.signals.vix_regime
            else "VIX regime n/a"
        )
        tension = s.primary_tension.strip()
        tension_txt = f" Primary tension: {tension}" if tension else ""
        lines.append(
            f"- {s.date}: close {s.spx_close}, regime {s.trend_regime}, "
            f"base case {s.base_case}, {vix_txt}, action: {action}.{tension_txt} "
            f"{s.narrative_summary}"
        )
    return "\n".join(lines)


def rebuild_rolling_summary(
    days: int | None = None, settings: Settings | None = None
) -> tuple[str, Path]:
    """Regenerate the rolling summary artifact from recent states."""
    settings = settings or get_settings()
    states = load_recent_states(limit=days, settings=settings)
    summary = build_recent_summary(states)

    settings.rolling_dir.mkdir(parents=True, exist_ok=True)
    summary_path = settings.rolling_dir / "recent_summary.md"
    summary_path.write_text(summary + "\n", encoding="utf-8")

    import json

    memory_path = settings.rolling_dir / "recent_memory.json"
    memory_path.write_text(
        json.dumps([s.model_dump(mode="json") for s in states], indent=2, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )
    return summary, summary_path
