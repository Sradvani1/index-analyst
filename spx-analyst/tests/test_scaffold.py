"""Tests for setup-run scaffolding."""

from pathlib import Path

from src.files import scaffold_run_dir


def test_scaffold_run_dir_writes_manifest_and_placeholder(tmp_path: Path):
    run_dir = tmp_path / "2026-06-20"
    scaffold_run_dir(run_dir, "2026-06-20")
    assert (run_dir / "manifest.json").exists()
    assert (run_dir / "charts" / "00_placeholder.png").exists()

    from src.files import load_manifest

    manifest = load_manifest(run_dir)
    assert manifest.chart_count == 1
