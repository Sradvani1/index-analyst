"""Thin wrapper over chat_preload for the Phase 1 preload contract."""

from __future__ import annotations

import warnings

from .chat_preload import build_additional_instructions, load_latest_daily_state
from .config import Settings, get_settings
from .files import InputError, read_json, read_text
from .memory import build_recent_summary, load_recent_states
from .schemas import ChatPreloadContext, ChatSessionContext, DailyState


def load_chat_preload(settings: Settings | None = None) -> ChatPreloadContext:
    """Load authority-ordered preload for Assistants runs (latest state + rolling summary)."""
    return build_additional_instructions(settings)


def load_chat_context(date: str, settings: Settings | None = None) -> ChatSessionContext:
    """Deprecated: date-anchored full-report load. Prefer :func:`load_chat_preload`."""
    warnings.warn(
        "load_chat_context is deprecated; use load_chat_preload() for latest-run authority",
        DeprecationWarning,
        stacklevel=2,
    )
    settings = settings or get_settings()

    state_path = settings.daily_states_dir / f"{date}-state.json"
    report_path = settings.daily_reports_dir / f"{date}-analysis.md"
    if not state_path.exists() or not report_path.exists():
        raise InputError(f"no canonical artifacts found for {date}; run analysis first")

    daily_state = DailyState.model_validate(read_json(state_path))
    recent_states = load_recent_states(before_date=date, settings=settings)

    return ChatSessionContext(
        date=date,
        report_markdown=read_text(report_path),
        daily_state=daily_state,
        recent_states=recent_states,
        recent_summary=build_recent_summary(recent_states),
    )


__all__ = [
    "load_chat_preload",
    "load_chat_context",
    "load_latest_daily_state",
    "build_additional_instructions",
]
