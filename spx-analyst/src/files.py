"""Filesystem operations: run discovery, validation, and IO.

Keeps the engine file-centric so the same layout serves a script today and a web
backend later.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

from .config import Settings, get_settings
from .schemas import DailyManifest, DailyState

MANIFEST_FILENAME = "manifest.json"
ANALYSIS_CONTEXT_FILENAME = "analysis_context.json"
CHARTS_DIRNAME = "charts"


class InputError(Exception):
    """Raised for unrecoverable input problems (hard failures)."""


# --- Generic JSON / text IO --------------------------------------------------


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise InputError(f"file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise InputError(f"invalid JSON in {path}: {exc}") from exc


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = data.model_dump(mode="json") if isinstance(data, BaseModel) else data
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise InputError(f"file not found: {path}") from exc


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


# --- Framework ---------------------------------------------------------------


def load_framework(settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    path = settings.framework_path
    if not path.exists():
        raise InputError(
            f"analysis framework not found at {path}. "
            "Place SPX-Daily-Analysis-Framework.md in the framework/ directory."
        )
    text = read_text(path)
    if not text.strip():
        raise InputError(f"analysis framework is empty: {path}")
    return text


def load_role(settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    path = settings.role_path
    if not path.exists():
        raise InputError(
            f"role block not found at {path}. "
            "Place SPX-Claude-Role-Block.md in the framework/ directory."
        )
    text = read_text(path)
    if not text.strip():
        raise InputError(f"role block is empty: {path}")
    return text


# --- Run directory resolution / manifest -------------------------------------


def resolve_run_dir(date: str, input_dir: str | None, settings: Settings | None = None) -> Path:
    settings = settings or get_settings()
    run_dir = Path(input_dir) if input_dir else (settings.runs_dir / date)
    run_dir = run_dir if run_dir.is_absolute() else (Path.cwd() / run_dir)
    if not run_dir.exists():
        raise InputError(f"run directory not found: {run_dir}")
    return run_dir


def load_manifest(run_dir: Path) -> DailyManifest:
    manifest_path = run_dir / MANIFEST_FILENAME
    raw = read_json(manifest_path)
    try:
        manifest = DailyManifest.model_validate(raw)
    except ValidationError as exc:
        raise InputError(f"invalid manifest {manifest_path}:\n{exc}") from exc
    _verify_chart_files(run_dir, manifest)
    return manifest


def _verify_chart_files(run_dir: Path, manifest: DailyManifest) -> None:
    charts_dir = run_dir / CHARTS_DIRNAME
    if not charts_dir.is_dir():
        raise InputError(f"charts directory missing: {charts_dir}")
    missing = [c.file for c in manifest.charts if not (charts_dir / c.file).is_file()]
    if missing:
        raise InputError(f"manifest references missing chart files: {missing}")


def chart_paths(run_dir: Path, manifest: DailyManifest) -> list[Path]:
    charts_dir = run_dir / CHARTS_DIRNAME
    return [charts_dir / c.file for c in manifest.ordered_charts()]


def scaffold_run_dir(run_dir: Path, date: str) -> None:
    """Create charts dir, placeholder chart, and minimal manifest if missing."""
    from PIL import Image

    run_dir.mkdir(parents=True, exist_ok=True)
    charts_dir = run_dir / CHARTS_DIRNAME
    charts_dir.mkdir(exist_ok=True)

    placeholder_name = "00_placeholder.png"
    placeholder_path = charts_dir / placeholder_name
    if not placeholder_path.exists():
        Image.new("RGB", (32, 32), color=(128, 128, 128)).save(placeholder_path)

    manifest_path = run_dir / MANIFEST_FILENAME
    if not manifest_path.exists():
        manifest = {
            "date": date,
            "index_symbol": "SPX",
            "close": 0.0,
            "chart_count": 1,
            "charts": [
                {
                    "order": 1,
                    "file": placeholder_name,
                    "label": "Placeholder (replace with chart pack)",
                    "category": "technical",
                }
            ],
        }
        write_json(manifest_path, manifest)


# --- Output persistence ------------------------------------------------------


def output_dir_for(date: str, settings: Settings | None = None) -> Path:
    settings = settings or get_settings()
    out = settings.output_dir / date
    out.mkdir(parents=True, exist_ok=True)
    return out


def save_outputs(
    *,
    date: str,
    daily_state: DailyState,
    report_md: str,
    request_snapshot: dict,
    response_raw: dict,
    run_log: dict,
    validation_reports: list[dict],
    mirror_to_memory: bool = True,
    settings: Settings | None = None,
) -> Path:
    """Write all run artifacts; optionally mirror canonical files into memory/.

    `mirror_to_memory` must stay False for failed runs so a placeholder state
    never enters the rolling memory that future runs reason over.
    """
    settings = settings or get_settings()
    out = output_dir_for(date, settings)

    write_text(out / f"{date}-analysis.md", report_md)
    write_json(out / f"{date}-state.json", daily_state)
    write_json(out / "request_snapshot.json", request_snapshot)
    write_json(out / "response_raw.json", response_raw)
    write_json(out / "run_log.json", run_log)
    write_json(out / "validation_report.json", validation_reports)

    if mirror_to_memory:
        write_json(settings.daily_states_dir / f"{date}-state.json", daily_state)
        write_text(settings.daily_reports_dir / f"{date}-analysis.md", report_md)

    return out
