"""Tests for Pass 1 signals drift coalescer and historical equivalence."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.state_normalize import (
    coalesce_signals_drift,
    coalesced_signal_equivalence,
    resolve_pass1_daily_state,
)
from src.validation import parse_daily_state

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "state_normalize"
FIXTURE_SLUGS = [
    "2026-06-02",
    "2026-06-04",
    "2026-06-08",
    "2026-06-10",
    "2026-06-12",
    "ab-test-off",
]


def _load_fixture(slug: str) -> dict:
    return json.loads((FIXTURES_DIR / f"{slug}.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("slug", FIXTURE_SLUGS)
def test_historical_fixture_coalesce_then_parse(slug: str):
    fixture = _load_fixture(slug)
    date = fixture["date"]
    original = fixture["original_tool_input"]

    _, original_report = parse_daily_state(original, date)
    assert not original_report.passed

    normalized, audit = coalesce_signals_drift(original)
    assert not audit.untouched_unknown

    state, report = parse_daily_state(normalized, date)
    assert state is not None
    assert report.passed

    repaired_signals = fixture["repaired_signals"]
    assert coalesced_signal_equivalence(
        state.signals.model_dump(mode="json"),
        repaired_signals,
        audit,
    )


@pytest.mark.parametrize("slug", FIXTURE_SLUGS)
def test_resolve_pass1_skips_repair_for_historical_fixture(slug: str):
    fixture = _load_fixture(slug)
    result = resolve_pass1_daily_state(fixture["original_tool_input"], fixture["date"])

    assert result.final_valid
    assert not result.repair_triggered
    assert result.daily_state is not None


def test_unknown_extra_left_untouched_fail_closed():
    payload = {
        "date": "2026-06-12",
        "signals": {"vix_regime": "elevated", "mystery_field": "oops"},
    }
    _, audit = coalesce_signals_drift(payload)
    assert audit.untouched_unknown == ["signals.mystery_field"]
    assert "mystery_field" in payload["signals"]


def test_vix_regime_detail_appends():
    payload = {
        "signals": {
            "vix_regime": "Elevated (>20)",
            "vix_regime_detail": "VIX 22.22, above 20 threshold",
        }
    }
    normalized, audit = coalesce_signals_drift(payload)
    assert "vix_regime_detail" not in normalized["signals"]
    assert normalized["signals"]["vix_regime"] == (
        "Elevated (>20) — VIX 22.22, above 20 threshold"
    )
    assert audit.merged[0]["from_key"] == "signals.vix_regime_detail"


def test_note_appends_to_base_field():
    payload = {
        "signals": {
            "middle_band_regime": "Below 20-day SMA",
            "middle_band_regime_note": "short-term broken",
        }
    }
    normalized, audit = coalesce_signals_drift(payload)
    assert normalized["signals"]["middle_band_regime"] == "Below 20-day SMA — short-term broken"
    assert audit.merged


def test_put_call_zone_dropped():
    payload = {"signals": {"put_call": 0.7, "put_call_zone": "complacent"}}
    normalized, audit = coalesce_signals_drift(payload)
    assert "put_call_zone" not in normalized["signals"]
    assert audit.dropped


def test_vix_float_appends_when_level_missing():
    payload = {"signals": {"vix_regime": "complacent", "vix": 14.5}}
    normalized, audit = coalesce_signals_drift(payload)
    assert "vix" not in normalized["signals"]
    assert "VIX 14.50" in normalized["signals"]["vix_regime"]
    assert audit.merged


def test_vix_float_skips_append_when_level_present():
    payload = {"signals": {"vix_regime": "VIX 14.50 neutral", "vix": 14.5}}
    normalized, audit = coalesce_signals_drift(payload)
    assert normalized["signals"]["vix_regime"] == "VIX 14.50 neutral"
    assert audit.dropped
