"""Phase 2 retrieval contract (stub).

Loads a day's canonical artifacts read-only so a future conversational agent can
discuss them. Never mutates the daily-state memory.
"""

from __future__ import annotations

from .config import Settings, get_settings
from .files import InputError, read_json, read_text
from .memory import build_recent_summary, load_recent_states
from .schemas import ChatSessionContext, DailyState


def load_chat_context(date: str, settings: Settings | None = None) -> ChatSessionContext:
    """Assemble the read-only context for a chat session about `date`."""
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
