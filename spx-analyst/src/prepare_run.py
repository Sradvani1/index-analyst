"""Orchestrate Step 1: generate charts, write manifest, run precompute."""

from __future__ import annotations

import datetime as dt
import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from .chart_pack import CHART_PACK_SIZE, build_manifest
from .config import Settings, get_settings
from .eps_history import require_eps_for_run
from .fear_greed import RAW_DATA_FILENAME, fetch_and_generate as generate_fear_greed
from .files import (
    ANALYSIS_CONTEXT_FILENAME,
    CHARTS_DIRNAME,
    MANIFEST_FILENAME,
    InputError,
    load_manifest,
    write_json,
)
from .market_data import MARKET_HISTORY_FILENAME, cache_market_series, fetch_market_series
from .precompute import run_precompute
from .price_charts import fetch_and_generate as generate_price_charts
from .schemas import AnalysisContext

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PrepareRunResult:
    run_dir: Path
    close: float
    analysis_context: AnalysisContext
    chart_count: int
    warnings: list[str] = field(default_factory=list)


def _assert_can_prepare(run_dir: Path, *, force: bool) -> None:
    manifest_path = run_dir / MANIFEST_FILENAME
    charts_dir = run_dir / CHARTS_DIRNAME
    precompute_path = run_dir / ANALYSIS_CONTEXT_FILENAME

    has_existing = manifest_path.is_file() or precompute_path.is_file()
    if not has_existing and charts_dir.is_dir():
        has_existing = any(charts_dir.iterdir())

    if not has_existing:
        return

    if manifest_path.is_file():
        try:
            manifest = load_manifest(run_dir)
        except InputError:
            pass
        else:
            if manifest.chart_count == CHART_PACK_SIZE and not force:
                raise InputError(
                    f"run {run_dir} already prepared. Use --force to regenerate."
                )

    if not force:
        raise InputError(
            f"files already exist in {run_dir}. Use --force to overwrite."
        )


def _purge_stale_artifacts(run_dir: Path) -> None:
    charts_dir = run_dir / CHARTS_DIRNAME
    if charts_dir.is_dir():
        shutil.rmtree(charts_dir)

    for filename in [
        MANIFEST_FILENAME,
        ANALYSIS_CONTEXT_FILENAME,
        MARKET_HISTORY_FILENAME,
    ]:
        p = run_dir / filename
        if p.is_file():
            p.unlink()
            logger.info("removed stale %s", p.name)


def _resolve_close(
    date: str,
    run_dir: Path,
    *,
    settings: Settings,
) -> tuple[float, list[str]]:
    warnings: list[str] = []
    try:
        series = fetch_market_series(date, settings=settings)
        cache_market_series(run_dir, series)
        close = float(series.bars[-1].close)
    except ValueError as exc:
        raise InputError(
            f"market data fetch failed for {date}: {exc}. "
            "Ensure network access."
        ) from exc

    if series.as_of_date.isoformat() != date:
        msg = (
            f"run date ({date}) is not the latest yfinance session "
            f"({series.as_of_date}); using prior trading day close {close}"
        )
        warnings.append(msg)
        logger.warning(msg)

    return close, warnings


def prepare_run(
    date: str,
    *,
    run_dir: Path | None = None,
    force: bool = False,
    settings: Settings | None = None,
) -> PrepareRunResult:
    settings = settings or get_settings()
    run_dir = run_dir or settings.runs_dir / date
    warnings: list[str] = []

    _assert_can_prepare(run_dir, force=force)

    if force:
        _purge_stale_artifacts(run_dir)

    charts_dir = run_dir / CHARTS_DIRNAME
    charts_dir.mkdir(parents=True, exist_ok=True)

    run_date = dt.date.fromisoformat(date)

    price_paths = generate_price_charts(charts_dir, run_date)
    logger.info("generated %d price charts in %s", len(price_paths), charts_dir)

    fg_paths = generate_fear_greed(charts_dir)
    logger.info("generated %d fear & greed charts in %s", len(fg_paths), charts_dir)

    chart_count = len(price_paths) + len(fg_paths)

    close, close_warnings = _resolve_close(date, run_dir, settings=settings)
    warnings.extend(close_warnings)

    write_json(run_dir / MANIFEST_FILENAME, build_manifest(date, close))

    eps, _ = require_eps_for_run(date, settings=settings)
    manifest = load_manifest(run_dir)
    ctx = run_precompute(date, run_dir, manifest, eps, settings=settings)

    return PrepareRunResult(
        run_dir=run_dir,
        close=close,
        analysis_context=ctx,
        chart_count=chart_count,
        warnings=warnings,
    )


def print_prepare_summary(result: PrepareRunResult) -> None:
    import typer

    ctx = result.analysis_context
    md = ctx.market_data
    mc = ctx.monte_carlo
    threshold_row = mc.threshold_evaluation.get("65")
    meets = threshold_row.actionable if threshold_row else False
    prob_adj = threshold_row.adjusted_prob_up_first if threshold_row else 0.0

    typer.secho(f"Prepared {result.run_dir.name}", fg=typer.colors.GREEN)
    typer.echo(f"  SPX close:     {md.spx_close}")
    typer.echo(
        f"  Structure:     swing high {ctx.structure.active_swing_high_price} "
        f"({ctx.structure.swing_high_confirmation}), "
        f"swing low {ctx.structure.active_swing_low_price} "
        f"({ctx.structure.swing_low_confirmation})"
    )
    typer.echo(
        f"                 fib 382={ctx.structure.fib_382}, "
        f"fib 618={ctx.structure.fib_618}"
    )
    typer.echo(
        f"  Valuation:     forward PE {ctx.valuation.forward_pe} "
        f"({ctx.valuation.erp_trend})"
    )
    typer.echo(
        f"  Monte Carlo:   {mc.probability_regime}, 65% threshold {'MET' if meets else 'NOT met'} "
        f"(P_up_adj={prob_adj:.1%}), "
        f"exhaustion: {mc.rally_exhaustion_score}"
    )
    typer.echo(f"  {result.chart_count} charts   → {result.run_dir / 'charts'}")