import json

import pytest

from src import files
from src.files import InputError

from tests.conftest import build_run_dir


def test_load_manifest_and_chart_paths(tmp_path):
    run_dir = build_run_dir(tmp_path, n=3)
    manifest = files.load_manifest(run_dir)
    assert manifest.chart_count == 3
    paths = files.chart_paths(run_dir, manifest)
    assert len(paths) == 3
    assert all(p.exists() for p in paths)


def test_load_manifest_missing_chart_file(tmp_path):
    run_dir = build_run_dir(tmp_path, n=2)
    (run_dir / "charts" / "01_chart.png").unlink()
    with pytest.raises(InputError):
        files.load_manifest(run_dir)


def test_load_manifest_invalid_json(tmp_path):
    run_dir = build_run_dir(tmp_path, n=1)
    (run_dir / "manifest.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(InputError):
        files.load_manifest(run_dir)


def test_load_framework_missing(settings):
    settings.framework_path.unlink()
    with pytest.raises(InputError):
        files.load_framework(settings)
