"""Import raw screenshots from Images/<date>/ into a production run directory."""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass
from pathlib import Path

from .chart_pack import CANONICAL_CHART_FILES, CHART_PACK_SIZE, build_manifest
from .config import PACKAGE_ROOT, Settings, get_settings
from .files import (
    ANALYSIS_CONTEXT_FILENAME,
    CHARTS_DIRNAME,
    MANIFEST_FILENAME,
    InputError,
    load_manifest,
    read_json,
    write_json,
)
from .market_data import MARKET_HISTORY_FILENAME, cache_market_series, fetch_market_series
from .schemas import DailyManifest

logger = logging.getLogger(__name__)

PLACEHOLDER_CHART = "00_placeholder.png"


@dataclass(frozen=True)
class ImportRunResult:
    run_dir: Path
    manifest: DailyManifest
    close: float
    warnings: list[str]


def default_images_dir(date: str) -> Path:
    """Repo-root Images/<date>/ sibling to the spx-analyst package."""
    return PACKAGE_ROOT.parent / "Images" / date


def _intake_files(images_dir: Path) -> list[Path]:
    """Non-hidden files in the intake folder (ignores .DS_Store etc.)."""
    return [p for p in images_dir.iterdir() if p.is_file() and not p.name.startswith(".")]


def _collect_png_sources(images_dir: Path) -> list[Path]:
    if not images_dir.is_dir():
        raise InputError(f"images directory not found: {images_dir}")

    all_files = _intake_files(images_dir)
    non_png = sorted(p.name for p in all_files if p.suffix.lower() != ".png")
    if non_png:
        raise InputError(
            f"images directory contains non-PNG files (PNG only): {non_png}. "
            f"Remove or convert them in {images_dir}"
        )

    pngs = sorted(p for p in all_files if p.suffix.lower() == ".png")
    if len(pngs) != CHART_PACK_SIZE:
        names = [p.name for p in pngs]
        raise InputError(
            f"expected {CHART_PACK_SIZE} PNG files in {images_dir}, found {len(pngs)}: {names}"
        )
    return pngs


def _has_canonical_charts(run_dir: Path) -> bool:
    charts_dir = run_dir / CHARTS_DIRNAME
    if not charts_dir.is_dir():
        return False
    return any((charts_dir / name).is_file() for name in CANONICAL_CHART_FILES)


def _manifest_chart_count(run_dir: Path) -> int | None:
    manifest_path = run_dir / MANIFEST_FILENAME
    if not manifest_path.is_file():
        return None
    try:
        return int(read_json(manifest_path).get("chart_count", 0))
    except (InputError, TypeError, ValueError):
        return None


def _assert_can_import(run_dir: Path, *, force: bool) -> None:
    chart_count = _manifest_chart_count(run_dir)
    has_canonical = _has_canonical_charts(run_dir)

    if chart_count == CHART_PACK_SIZE:
        if not force:
            raise InputError(f"run {run_dir} already imported. Use --force to overwrite.")
        return

    if has_canonical and not force:
        raise InputError(
            f"incomplete import detected at {run_dir} "
            "(canonical charts present but manifest not ready). Use --force to retry."
        )


def _purge_stale_precompute(run_dir: Path) -> None:
    analysis_context = run_dir / ANALYSIS_CONTEXT_FILENAME
    if analysis_context.is_file():
        analysis_context.unlink()
        logger.info("removed stale %s", analysis_context)


def _copy_charts(sources: list[Path], charts_dir: Path) -> None:
    charts_dir.mkdir(parents=True, exist_ok=True)
    placeholder = charts_dir / PLACEHOLDER_CHART
    if placeholder.is_file():
        placeholder.unlink()

    for src, target_name in zip(sources, CANONICAL_CHART_FILES, strict=True):
        shutil.copy2(src, charts_dir / target_name)


def _purge_stale_market_history(run_dir: Path) -> None:
    cache_path = run_dir / MARKET_HISTORY_FILENAME
    if cache_path.is_file():
        cache_path.unlink()
        logger.info("removed stale %s", cache_path)


def _resolve_close(
    date: str,
    run_dir: Path,
    *,
    close_override: float | None,
    settings: Settings,
) -> tuple[float, list[str]]:
    warnings: list[str] = []
    fetched_close: float | None = None

    try:
        series = fetch_market_series(date, settings=settings)
        cache_market_series(run_dir, series)
        fetched_close = float(series.bars[-1].close)
        if series.as_of_date.isoformat() != date:
            msg = (
                f"run date ({date}) is not the latest yfinance session "
                f"({series.as_of_date}); using prior trading day close {fetched_close}"
            )
            warnings.append(msg)
            logger.warning(msg)
    except ValueError as exc:
        _purge_stale_market_history(run_dir)
        if close_override is None:
            raise InputError(
                f"market data fetch failed for {date}: {exc}. "
                "Ensure network access or pass --close to set manifest.close manually."
            ) from exc
        warnings.append(
            "market_history.json not written — network fetch failed; precompute will need network"
        )

    if close_override is not None:
        return close_override, warnings
    assert fetched_close is not None
    return fetched_close, warnings


def import_run(
    date: str,
    *,
    images_dir: Path | None = None,
    run_dir: Path | None = None,
    force: bool = False,
    close_override: float | None = None,
    settings: Settings | None = None,
) -> ImportRunResult:
    """Copy intake screenshots into run_dir and write a canonical manifest."""
    settings = settings or get_settings()
    images_dir = images_dir or default_images_dir(date)
    run_dir = run_dir or settings.runs_dir / date

    sources = _collect_png_sources(images_dir)

    _assert_can_import(run_dir, force=force)

    _purge_stale_precompute(run_dir)

    close, warnings = _resolve_close(date, run_dir, close_override=close_override, settings=settings)

    charts_dir = run_dir / CHARTS_DIRNAME
    _copy_charts(sources, charts_dir)

    write_json(run_dir / MANIFEST_FILENAME, build_manifest(date, close))

    manifest = load_manifest(run_dir)
    return ImportRunResult(run_dir=run_dir, manifest=manifest, close=close, warnings=warnings)
