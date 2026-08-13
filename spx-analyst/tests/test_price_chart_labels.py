from datetime import date

from src.price_charts import _daily_tick_labels, _format_date


def test_price_chart_dates_omit_year_for_compact_labels() -> None:
    assert _format_date(date(2025, 8, 13)) == "Aug 13"
    assert _format_date(date(2026, 1, 2)) == "Jan 02"


def test_daily_tick_labels_preserve_first_and_last_dates() -> None:
    dates = [date(2025, 8, 13), date(2025, 10, 3), date(2025, 11, 24), date(2026, 1, 2)]
    positions, labels = _daily_tick_labels(dates, n_ticks=3)
    assert positions == [0, 2, 3]
    assert labels == ["Aug 13", "Nov 24", "Jan 02"]
