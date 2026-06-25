"""Contract-preserving coalescer for observed Pass 1 signals drift."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Callable

from .schemas import DailyState, ValidationReport
from .validation import parse_daily_state, validation_errors_text

ALLOWED_SIGNAL_KEYS = frozenset(
    {
        "pct_vs_50dma",
        "pct_vs_200dma",
        "bollinger_position",
        "rsi14",
        "mfi",
        "vix_regime",
        "fear_greed",
        "fear_greed_zone",
        "put_call",
        "high_yield_spread",
        "intraday_close_position",
        "middle_band_regime",
    }
)

_NOTE_SUFFIX = "_note"

FRAMEWORK_BLEED_KEYS = frozenset(
    {
        "rsi_divergence",
        "mfi_divergence",
        "bearish_divergence",
        "bullish_divergence",
    }
)


def _is_null_or_empty(value: Any) -> bool:
    return value is None or value == "" or value == {}


@dataclass(frozen=True)
class NormalizeAudit:
    merged: list[dict[str, Any]] = field(default_factory=list)
    dropped: list[dict[str, Any]] = field(default_factory=list)
    untouched_unknown: list[str] = field(default_factory=list)
    structural_coercions: list[dict[str, Any]] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return bool(self.merged or self.dropped or self.structural_coercions)

    def to_dict(self) -> dict[str, Any]:
        return {
            "merged": list(self.merged),
            "dropped": list(self.dropped),
            "untouched_unknown": list(self.untouched_unknown),
            "structural_coercions": list(self.structural_coercions),
        }


@dataclass
class Pass1ResolveResult:
    daily_state: DailyState | None
    validation: ValidationReport
    original_tool_input: dict[str, Any]
    normalized_tool_input: dict[str, Any]
    normalize_audit: NormalizeAudit
    original_valid: bool
    normalized: bool
    repair_triggered: bool
    final_valid: bool
    validation_errors_original: list[str]
    validation_errors_after_normalize: list[str]
    repair_tool_input: dict[str, Any] | None = None
    repair_raw_response: dict[str, Any] | None = None
    repair_usage: dict[str, Any] | None = None

    def pass1_schema_status(self) -> dict[str, Any]:
        wct = self.normalized_tool_input.get("what_changed_today")
        wct_count = len(wct) if isinstance(wct, list) else 0
        repair_avoided = (
            not self.original_valid and not self.repair_triggered and self.final_valid
        )
        return {
            "original_valid": self.original_valid,
            "normalized": self.normalized,
            "repair_triggered": self.repair_triggered,
            "final_valid": self.final_valid,
            "repair_avoided": repair_avoided,
            "what_changed_today_count": wct_count,
            "what_changed_today_count_warning": wct_count < 2,
            "normalize_audit": self.normalize_audit.to_dict(),
            "validation_errors_original": self.validation_errors_original,
            "validation_errors_after_normalize": self.validation_errors_after_normalize,
            "repair_usage": self.repair_usage,
        }


def _schema_error_messages(report: ValidationReport) -> list[str]:
    return [issue.message for issue in report.errors]


def _vix_level_present(vix_regime: str | None, value: float) -> bool:
    if not vix_regime:
        return False
    text = vix_regime.lower()
    formatted = f"{value:.2f}"
    if formatted in text:
        return True
    whole = str(int(value)) if value == int(value) else None
    return whole is not None and whole in text


def _append_field(signals: dict[str, Any], field: str, extra: str, *, action: str) -> None:
    base = signals.get(field)
    if isinstance(base, str) and base.strip():
        signals[field] = f"{base} — {extra}"
    else:
        signals[field] = extra


def coalesce_signals_drift(tool_input: dict[str, Any]) -> tuple[dict[str, Any], NormalizeAudit]:
    """Apply allowlisted signals coalescence; leave unknown extras untouched (fail closed)."""
    out = copy.deepcopy(tool_input)
    signals = out.get("signals")
    if not isinstance(signals, dict):
        return out, NormalizeAudit()

    audit = NormalizeAudit()
    keys = list(signals.keys())

    for key in keys:
        if key in ALLOWED_SIGNAL_KEYS:
            continue

        value = signals.get(key)

        if key == "vix_regime_detail":
            if isinstance(value, str) and value.strip():
                _append_field(signals, "vix_regime", value.strip(), action="append")
                audit.merged.append(
                    {
                        "from_key": f"signals.{key}",
                        "to_key": "signals.vix_regime",
                        "action": "append",
                        "value": value.strip(),
                    }
                )
            else:
                audit.dropped.append({"key": f"signals.{key}", "reason": "empty_or_non_string"})
            del signals[key]
            continue

        if key == "vix":
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                vix_regime = signals.get("vix_regime")
                snippet = f"VIX {float(value):.2f}"
                if isinstance(vix_regime, str) and _vix_level_present(vix_regime, float(value)):
                    audit.dropped.append(
                        {"key": f"signals.{key}", "reason": "level_already_in_vix_regime"}
                    )
                else:
                    _append_field(signals, "vix_regime", snippet, action="append")
                    audit.merged.append(
                        {
                            "from_key": f"signals.{key}",
                            "to_key": "signals.vix_regime",
                            "action": "append",
                            "value": snippet,
                        }
                    )
            else:
                audit.dropped.append({"key": f"signals.{key}", "reason": "empty_or_non_numeric"})
            del signals[key]
            continue

        if key.endswith(_NOTE_SUFFIX):
            base_key = key[: -len(_NOTE_SUFFIX)]
            if base_key in ALLOWED_SIGNAL_KEYS:
                base_val = signals.get(base_key)
                if isinstance(value, str) and value.strip() and isinstance(base_val, str):
                    _append_field(signals, base_key, value.strip(), action="append")
                    audit.merged.append(
                        {
                            "from_key": f"signals.{key}",
                            "to_key": f"signals.{base_key}",
                            "action": "append",
                            "value": value.strip(),
                        }
                    )
                else:
                    audit.dropped.append(
                        {
                            "key": f"signals.{key}",
                            "reason": "base_missing_or_non_string_or_note_empty",
                        }
                    )
                del signals[key]
                continue

        if key.endswith("_zone") and key != "fear_greed_zone":
            audit.dropped.append({"key": f"signals.{key}", "reason": "zone_key_except_fear_greed"})
            del signals[key]
            continue

        if key in FRAMEWORK_BLEED_KEYS and _is_null_or_empty(value):
            audit.dropped.append(
                {"key": f"signals.{key}", "reason": "framework_bleed_null_or_empty"}
            )
            del signals[key]
            continue

        if _is_null_or_empty(value):
            audit.dropped.append({"key": f"signals.{key}", "reason": "null_or_empty_unknown"})
            del signals[key]
            continue

        audit.untouched_unknown.append(f"signals.{key}")

    return out, audit


def coalesce_pass1_drift(tool_input: dict[str, Any]) -> tuple[dict[str, Any], NormalizeAudit]:
    """Apply structural coercion plus signals drift coalescence for Pass 1 output."""
    out = copy.deepcopy(tool_input)
    structural: list[dict[str, Any]] = []

    wct = out.get("what_changed_today")
    if isinstance(wct, str) and wct.strip():
        out["what_changed_today"] = [wct.strip()]
        structural.append({"field": "what_changed_today", "action": "wrap_str_as_list"})

    out, audit = coalesce_signals_drift(out)
    if structural:
        audit = NormalizeAudit(
            merged=audit.merged,
            dropped=audit.dropped,
            untouched_unknown=audit.untouched_unknown,
            structural_coercions=structural,
        )
    return out, audit


def resolve_pass1_daily_state(
    original_tool_input: dict[str, Any],
    date: str,
    *,
    repair_fn: Callable[[dict[str, Any], str], tuple[dict[str, Any], dict[str, Any]]] | None = None,
) -> Pass1ResolveResult:
    """Coalesce known drift, parse, and optionally repair schema-invalid Pass 1 output."""
    original = copy.deepcopy(original_tool_input)
    _, original_report = parse_daily_state(original, date)
    original_valid = original_report.passed
    validation_errors_original = _schema_error_messages(original_report)

    normalized_input, audit = coalesce_pass1_drift(original)
    normalized_changed = normalized_input != original
    daily_state, normalized_report = parse_daily_state(normalized_input, date)
    validation_errors_after_normalize = _schema_error_messages(normalized_report)

    repair_triggered = False
    repair_tool_input: dict[str, Any] | None = None
    repair_raw: dict[str, Any] | None = None
    repair_usage: dict[str, Any] | None = None

    if daily_state is None and repair_fn is not None:
        repair_triggered = True
        repair_tool_input, repair_raw = repair_fn(
            normalized_input, validation_errors_text(normalized_report)
        )
        daily_state, normalized_report = parse_daily_state(repair_tool_input or {}, date)
        validation_errors_after_normalize = _schema_error_messages(normalized_report)
        repair_usage = (repair_raw or {}).get("usage")

    final_valid = daily_state is not None and normalized_report.passed

    return Pass1ResolveResult(
        daily_state=daily_state,
        validation=normalized_report,
        original_tool_input=original,
        normalized_tool_input=normalized_input,
        normalize_audit=audit,
        original_valid=original_valid,
        normalized=normalized_changed,
        repair_triggered=repair_triggered,
        final_valid=final_valid,
        validation_errors_original=validation_errors_original,
        validation_errors_after_normalize=validation_errors_after_normalize,
        repair_tool_input=repair_tool_input,
        repair_raw_response=repair_raw,
        repair_usage=repair_usage,
    )


def coalesced_signal_equivalence(
    normalized_signals: dict[str, Any],
    repaired_signals: dict[str, Any],
    audit: NormalizeAudit,
) -> bool:
    """Check material equivalence for fields touched by the coalescer."""
    for entry in audit.merged:
        to_key = entry["to_key"]
        if not to_key.startswith("signals."):
            continue
        field = to_key.split(".", 1)[1]
        normalized_val = normalized_signals.get(field)
        repaired_val = repaired_signals.get(field)
        if normalized_val == repaired_val:
            continue
        if isinstance(normalized_val, str) and isinstance(repaired_val, str):
            if normalized_val.startswith(repaired_val):
                continue
        return False

    for key in normalized_signals:
        if key not in ALLOWED_SIGNAL_KEYS:
            return False
    for key in audit.dropped:
        dropped_key = key["key"].split(".", 1)[-1]
        if normalized_signals.get(dropped_key) != repaired_signals.get(dropped_key):
            if dropped_key in repaired_signals:
                return False
    return True
