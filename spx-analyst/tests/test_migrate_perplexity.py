"""Tests for Perplexity history parsing (offline, no API)."""

from pathlib import Path

import pytest

from src.migrate_perplexity import MigrationError, filter_sessions, parse_history

JUNE_10_SNIPPET = """\
---

# 📊 SPX Full 7-Step Analysis — Tuesday, June 10, 2026 | Close: 7,266.99

---

## Step 1 — Price Action: 23.6% Fib Broken, Correction Accelerating

SPX closed at 7,266.99, down −119.66 (−1.62%).

## Step 5 — Monte Carlo: 100,000 Paths, 60 Days

| Test | Probability |
| :-- | :-- |
| **P(Wave 1 7,696 first vs 38.2% Fib 7,151)** | **29.1% / 70.6%** |

**🎯 RECOMMENDED ACTION: HOLD SCHK — PREPARE ACTIVE RE-ENTRY DEPLOYMENT AT 7,151**

<span style="display:none">[^58_12]</span>

<div align="center">⁂</div>

[^58_1]: IMG_1058.jpeg
[^58_2]: IMG_1055.jpeg
"""


def test_parse_history_extracts_june_10(tmp_path: Path):
    path = tmp_path / "history.md"
    path.write_text(JUNE_10_SNIPPET, encoding="utf-8")
    sessions = parse_history(path)
    assert len(sessions) == 1
    s = sessions[0]
    assert s.date == "2026-06-10"
    assert s.spx_close == 7266.99
    assert "23.6% Fib Broken" in s.clean_markdown
    assert "IMG_1058.jpeg" not in s.clean_markdown
    assert "[^58_1]" not in s.clean_markdown


def test_filter_sessions_by_date_range(tmp_path: Path):
    path = tmp_path / "history.md"
    path.write_text(
        JUNE_10_SNIPPET
        + "\n---\n\n"
        + JUNE_10_SNIPPET.replace("June 10", "June 8").replace("7,266.99", "7,405.73"),
        encoding="utf-8",
    )
    sessions = parse_history(path)
    assert len(sessions) == 2
    filtered = filter_sessions(sessions, from_date="2026-06-10", to_date="2026-06-10")
    assert len(filtered) == 1
    assert filtered[0].date == "2026-06-10"


def test_parse_history_empty_raises(tmp_path: Path):
    path = tmp_path / "empty.md"
    path.write_text("# unrelated content\n", encoding="utf-8")
    with pytest.raises(MigrationError):
        parse_history(path)
