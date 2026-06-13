from src.memory import build_recent_summary, load_recent_states, rebuild_rolling_summary

from tests.conftest import write_state


def test_load_recent_states_orders_newest_first(settings):
    for date in ["2026-06-09", "2026-06-10", "2026-06-11"]:
        write_state(settings, date)
    states = load_recent_states(limit=5, settings=settings)
    assert [s.date for s in states] == ["2026-06-11", "2026-06-10", "2026-06-09"]


def test_load_recent_states_respects_limit_and_before(settings):
    for date in ["2026-06-09", "2026-06-10", "2026-06-11", "2026-06-12"]:
        write_state(settings, date)
    states = load_recent_states(limit=2, before_date="2026-06-12", settings=settings)
    assert [s.date for s in states] == ["2026-06-11", "2026-06-10"]


def test_load_recent_states_skips_malformed(settings):
    write_state(settings, "2026-06-10")
    bad = settings.daily_states_dir / "2026-06-11-state.json"
    bad.write_text("{broken", encoding="utf-8")
    states = load_recent_states(limit=5, settings=settings)
    assert [s.date for s in states] == ["2026-06-10"]


def test_build_recent_summary_empty():
    assert "No prior sessions" in build_recent_summary([])


def test_rebuild_rolling_summary_writes_files(settings):
    write_state(settings, "2026-06-11")
    summary, path = rebuild_rolling_summary(days=5, settings=settings)
    assert path.exists()
    assert "2026-06-11" in summary
    assert "Primary tension:" in summary
    assert (settings.rolling_dir / "recent_memory.json").exists()
