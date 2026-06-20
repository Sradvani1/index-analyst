"""Rolling operational memory: load recent daily states and summarize them.

This is the engine's main continuity mechanism. The Claude API is stateless at
the application level, so prior context must be reloaded and reintroduced here.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from .config import Settings, get_settings
from .files import InputError, read_json
from .schemas import DailyState, Divergence, SignalSet

_WEIGHT_ORDER = {"high": 0, "medium": 1, "low": 2}


@dataclass
class MemoryLoadStats:
    requested: int
    loaded: int
    skipped_invalid: int
    skipped_before_date: int


def _state_date(path: Path) -> str:
    return path.name.replace("-state.json", "")


def load_recent_states_with_stats(
    limit: int | None = None,
    *,
    before_date: str | None = None,
    settings: Settings | None = None,
) -> tuple[list[DailyState], MemoryLoadStats]:
    """Return recent valid DailyState objects (newest first) plus load counters."""
    settings = settings or get_settings()
    requested = settings.recent_state_count if limit is None else limit

    stats = MemoryLoadStats(
        requested=requested,
        loaded=0,
        skipped_invalid=0,
        skipped_before_date=0,
    )

    states_dir = settings.daily_states_dir
    if not states_dir.is_dir():
        return [], stats

    files = sorted(states_dir.glob("*-state.json"), key=_state_date, reverse=True)

    states: list[DailyState] = []
    for path in files:
        date = _state_date(path)
        if before_date is not None and date >= before_date:
            stats.skipped_before_date += 1
            continue
        try:
            states.append(DailyState.model_validate(read_json(path)))
        except (ValidationError, ValueError, InputError):
            stats.skipped_invalid += 1
            continue
        if len(states) >= requested:
            break

    stats.loaded = len(states)
    return states, stats


def load_recent_states(
    limit: int | None = None,
    *,
    before_date: str | None = None,
    settings: Settings | None = None,
) -> list[DailyState]:
    """Return up to `limit` most recent valid DailyState objects, newest first."""
    states, _ = load_recent_states_with_stats(
        limit, before_date=before_date, settings=settings
    )
    return states


def _truncate(text: str, max_len: int) -> str:
    text = text.strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def _collapse_ws(text: str) -> str:
    return " ".join(text.split())


def _normalize_action(
    raw: str,
    *,
    current_reading: str = "",
    signal: str = "",
) -> str:
    """Map raw action strings to a closed-set posture token (max 60 chars)."""
    def _clean(s: str) -> str:
        s = _collapse_ws(s.lower())
        for prefix in ("hold_schk_", "schk_"):
            if s.startswith(prefix):
                s = s[len(prefix) :]
        return s

    raw_clean = _clean(raw)
    signal_clean = _clean(signal)
    reading_clean = _clean(current_reading)

    def _match(text: str) -> str | None:
        if not text:
            return None
        if any(k in text for k in ("partial trim", "defensive trim", "wave 1")):
            return "trim bias"
        if "trim" in text:
            return "trim bias"
        if "light deploy" in text:
            return "light deploy"
        if any(k in text for k in ("deploy", "reentry", "re-entry", "add tranche")):
            return "deploy"
        # Bare `tranche` only — `add tranche` is handled above as deploy.
        if any(k in text for k in ("partial", "25%", "light")) or (
            "tranche" in text and "add tranche" not in text
        ):
            return "light deploy"
        if any(k in text for k in ("defense", "defensive", "patience", "capital preservation", "protect")):
            return "defensive patience"
        if any(k in text for k in ("hold", "monitor", "wait", "gtc")):
            return "hold and monitor"
        return None

    for candidate in (raw_clean, signal_clean):
        mapped = _match(candidate)
        if mapped:
            return _truncate(mapped, 60)

    snake_noise = signal_clean.replace("_", "") in ("", "holdandmonitor", "hold", "monitor", "na", "none")
    if reading_clean and len(current_reading.strip()) <= 60 and snake_noise:
        if _match(reading_clean) is None:
            return _truncate(current_reading.strip(), 60)

    return "hold and monitor"


def _bucket_fear_greed(s: SignalSet) -> str:
    if s.fear_greed_zone:
        zone = s.fear_greed_zone.lower().replace(" ", "_").replace("-", "_")
        # Longest tokens first — "greed" is a substring of "extreme_greed".
        if "extreme_greed" in zone:
            return "extreme_greed"
        if "extreme_fear" in zone:
            return "extreme_fear"
        if "neutral" in zone:
            return "neutral"
        if "greed" in zone:
            return "greed"
        if "fear" in zone:
            return "fear"
    if s.fear_greed is not None:
        score = s.fear_greed
        if score <= 24:
            return "extreme_fear"
        if score <= 44:
            return "fear"
        if score <= 55:
            return "neutral"
        if score <= 74:
            return "greed"
        return "extreme_greed"
    return "unknown"


def _bucket_vix(s: SignalSet) -> str:
    if s.vix_regime:
        text = s.vix_regime.lower()
        if "elevated" in text:
            return "elevated"
        if "high" in text or "spike" in text:
            return "high"
        if "low" in text or "complacent" in text:
            return "low"
        if "normal" in text or "moderate" in text:
            return "normal"
    return "unknown"


def _bucket_rsi(s: SignalSet) -> str:
    if s.rsi14 is None:
        return "unknown"
    if s.rsi14 < 30:
        return "oversold"
    if s.rsi14 > 70:
        return "overbought"
    return "neutral"


def _bucket_credit(s: SignalSet) -> str:
    if s.high_yield_spread is None:
        return "unknown"
    spread = s.high_yield_spread
    if spread < 1.0:
        return "tight"
    if spread <= 1.3:
        return "normal"
    if spread <= 1.5:
        return "wide"
    return "extreme"


def _bucket_vs50d(s: SignalSet) -> str:
    if s.pct_vs_50dma is None:
        return "unknown"
    pct = s.pct_vs_50dma
    if pct < -1:
        return "below"
    if pct <= 3:
        return "near"
    if pct <= 8:
        return "above"
    return "extended"


def _display_signal_label(bucket: str) -> str:
    """Render internal bucket token as human-readable prompt text (spaces, not snake_case)."""
    return bucket.replace("_", " ")


def _signal_labels(s: DailyState) -> str:
    sig = s.signals
    fg = _display_signal_label(_bucket_fear_greed(sig))
    vix = _display_signal_label(_bucket_vix(sig))
    rsi = _display_signal_label(_bucket_rsi(sig))
    credit = _display_signal_label(_bucket_credit(sig))
    vs50 = _display_signal_label(_bucket_vs50d(sig))
    return (
        f"signals: F&G {fg} | VIX {vix} | RSI {rsi} | credit {credit} | vs50d {vs50}"
    )


def _conflict_line(d: Divergence) -> str:
    layers = "/".join(d.layers)
    rule_budget = max(0, 90 - len(d.id) - len(layers) - 6)
    rule = _truncate(d.framework_rule, rule_budget)
    return f"{d.id} | {layers} | {rule}"


def _select_conflicts(divergences: list[Divergence]) -> list[Divergence]:
    ordered = sorted(
        divergences,
        key=lambda d: (_WEIGHT_ORDER.get(d.weight, 9), d.id),
    )
    return ordered[:2]


def _action_for_state(s: DailyState) -> str:
    row = None
    for r in s.decision_matrix.rows:
        if r.signal_layer.strip().lower() == "recommended action":
            row = r
            break
    if row is None:
        return _normalize_action(s.decision_matrix.recommended_action)
    return _normalize_action(
        s.decision_matrix.recommended_action,
        current_reading=row.current_reading,
        signal=row.signal,
    )


def _format_day(s: DailyState) -> str:
    lines = [
        f"### {s.date}",
        f"{s.structural_bias} | {s.signal_alignment.overall} | action: {_action_for_state(s)}",
        _signal_labels(s),
    ]
    if s.what_changed_today:
        items = [_truncate(item, 60) for item in s.what_changed_today[:3]]
        lines.append(f"changed: {'; '.join(items)}")
    tension = s.primary_tension.strip()
    if tension:
        lines.append(f"tension: {_truncate(tension, 120)}")
    conflicts = _select_conflicts(s.conflicting_evidence)
    if conflicts:
        conflict_lines = [_truncate(_conflict_line(c), 90) for c in conflicts]
        lines.append(f"conflicts: {'; '.join(conflict_lines)}")
    return "\n".join(lines)


def _regime_arc(states: list[DailyState]) -> str:
    if not states:
        return "Regime arc (0 sessions): n/a"
    chronological = sorted(states, key=lambda s: s.date)
    biases = [s.structural_bias for s in chronological]
    n = len(biases)
    if len(set(biases)) == 1:
        return f"Regime arc ({n} sessions): {biases[0]} (held)"
    transitions: list[str] = []
    current = biases[0]
    for b in biases[1:]:
        if b != current:
            transitions.append(f"{current} → {b}")
            current = b
    tail = transitions[-1] if transitions else f"{biases[-1]} (held)"
    return f"Regime arc ({n} sessions): {tail}"


def _normalize_question(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _newest_wording(states: DailyState | list[DailyState], normalized: str) -> str:
    if isinstance(states, DailyState):
        states = [states]
    for s in states:
        for q in s.open_questions:
            if _normalize_question(q) == normalized:
                return q
    return ""


def _build_unresolved_watchlist(states: list[DailyState]) -> str:
    """Build rollup footer watchlist from open_questions (states newest-first)."""
    if not states:
        return "Unresolved watchlist: (none)"

    # Collect normalized -> {dates newest-first, wordings by date}
    by_norm: dict[str, list[tuple[str, str]]] = {}
    for s in states:
        for q in s.open_questions:
            norm = _normalize_question(q)
            if not norm:
                continue
            by_norm.setdefault(norm, []).append((s.date, q))

    selected: list[tuple[str, str]] = []
    for norm, occurrences in by_norm.items():
        dates = [d for d, _ in occurrences]
        in_newest = states[0].date in dates
        in_last_three = sum(1 for s in states[:3] if any(_normalize_question(q) == norm for q in s.open_questions))
        two_consecutive_miss = True
        for s in states[:2]:
            if any(_normalize_question(q) == norm for q in s.open_questions):
                two_consecutive_miss = False
                break

        if two_consecutive_miss and not in_newest:
            continue
        if not in_newest and in_last_three < 2:
            continue

        newest_date = max(dates)
        wording = _newest_wording(
            [s for s in states if s.date == newest_date],
            norm,
        )
        if not wording:
            wording = occurrences[0][1]
        selected.append((newest_date, wording))

    selected.sort(key=lambda x: x[0], reverse=True)
    items = [_truncate(w, 80) for _, w in selected[:2]]
    if not items:
        return "Unresolved watchlist: (none)"
    return "Unresolved watchlist: " + " | ".join(items)


def build_recent_summary(states: list[DailyState]) -> str:
    """Compact posture snapshot rollup — categorical labels only, no historical numerics.

    Expects `states` in newest-first order (same as `load_recent_states` output).
    Per-day blocks are emitted oldest-to-newest.
    """
    if not states:
        return "No prior sessions on record."

    blocks = [_format_day(s) for s in reversed(states)]
    footer = [
        "---",
        _regime_arc(states),
        _build_unresolved_watchlist(states),
    ]
    return "\n\n".join(blocks + footer)


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

    memory_path = settings.rolling_dir / "recent_memory.json"
    memory_path.write_text(
        json.dumps([s.model_dump(mode="json") for s in states], indent=2, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )
    return summary, summary_path
