import pytest
from pydantic import ValidationError

from src.schemas import DailyManifest, DailyState


def test_daily_state_round_trip(sample_state):
    dumped = sample_state.model_dump(mode="json")
    assert DailyState.model_validate(dumped) == sample_state


def _manifest(charts, chart_count=None):
    return {
        "date": "2026-06-12",
        "index_symbol": "SPX",
        "instrument_symbol": "SCHK",
        "close": 7450.25,
        "chart_count": chart_count if chart_count is not None else len(charts),
        "charts": charts,
    }


def test_manifest_valid():
    charts = [
        {"order": 1, "file": "a.png", "label": "A", "category": "technical"},
        {"order": 2, "file": "b.png", "label": "B", "category": "technical"},
    ]
    m = DailyManifest.model_validate(_manifest(charts))
    assert [c.order for c in m.ordered_charts()] == [1, 2]


def test_manifest_rejects_duplicate_order():
    charts = [
        {"order": 1, "file": "a.png", "label": "A", "category": "technical"},
        {"order": 1, "file": "b.png", "label": "B", "category": "technical"},
    ]
    with pytest.raises(ValidationError):
        DailyManifest.model_validate(_manifest(charts))


def test_manifest_rejects_noncontiguous_order():
    charts = [
        {"order": 1, "file": "a.png", "label": "A", "category": "technical"},
        {"order": 3, "file": "b.png", "label": "B", "category": "technical"},
    ]
    with pytest.raises(ValidationError):
        DailyManifest.model_validate(_manifest(charts))


def test_manifest_rejects_count_mismatch():
    charts = [{"order": 1, "file": "a.png", "label": "A", "category": "technical"}]
    with pytest.raises(ValidationError):
        DailyManifest.model_validate(_manifest(charts, chart_count=5))
