"""Command-line interface for the SPX analysis engine."""

from __future__ import annotations

import datetime as dt
import logging
import sys
from pathlib import Path

import typer

from .config import get_settings
from .files import InputError, read_json, read_text
from .memory import rebuild_rolling_summary
from .schemas import ValidationReport
from .validation import parse_daily_state, validate_report

app = typer.Typer(add_completion=False, help="SPX daily analysis engine.")


def _today() -> str:
    return dt.date.today().isoformat()


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logging.getLogger("src").setLevel(logging.DEBUG if verbose else logging.INFO)
    for noisy in ("anthropic", "httpx", "httpcore", "urllib3", "PIL", "yfinance"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def _print_validation(report: ValidationReport) -> None:
    status = "PASS" if report.passed else "FAIL"
    typer.echo(f"[{status}] {report.target} ({report.date})")
    for issue in report.issues:
        typer.echo(f"  {issue.severity.upper()} [{issue.code}] {issue.message}")


@app.command("setup-run")
def setup_run(
    date: str = typer.Option(None, help="Trade date YYYY-MM-DD (default: today)."),
    input_dir: str = typer.Option(None, help="Run directory (default: data/runs/<date>)."),
    precompute: bool = typer.Option(False, help="Run yfinance precompute if EPS is set."),
    force_fetch: bool = typer.Option(False, help="Force fresh yfinance fetch."),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Scaffold a run directory with external_context template and optional precompute."""
    _setup_logging(verbose)
    date = date or _today()
    settings = get_settings()
    from .external_data import blank_context, load_external_context
    from .files import resolve_run_dir, scaffold_run_dir, write_json

    run_dir = Path(input_dir) if input_dir else settings.runs_dir / date
    scaffold_run_dir(run_dir, date)

    ext_path = run_dir / "external_context.json"
    if not ext_path.exists():
        write_json(ext_path, blank_context(date))
        typer.echo(f"Wrote {ext_path}")

    if precompute:
        from .files import load_manifest
        from .precompute import run_precompute

        try:
            manifest = load_manifest(run_dir)
        except InputError as exc:
            typer.secho(f"Cannot precompute: {exc}", fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1)
        ext = load_external_context(date, run_dir, settings=settings)
        if ext.context.forward_eps is None:
            typer.secho("Set forward_eps in external_context.json before precompute.", fg=typer.colors.YELLOW)
            raise typer.Exit(code=1)
        ctx = run_precompute(date, run_dir, manifest, ext.context, settings=settings, force_fetch=force_fetch)
        typer.secho(f"Wrote analysis_context.json (close={ctx.market_data.spx_close})", fg=typer.colors.GREEN)

    typer.echo(f"Run directory ready: {run_dir}")


@app.command()
def run(
    date: str = typer.Option(None, help="Trade date YYYY-MM-DD (default: today)."),
    input_dir: str = typer.Option(None, help="Run directory (default: data/runs/<date>)."),
    force_fetch: bool = typer.Option(False, help="Force fresh yfinance fetch for precompute."),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Run a complete daily analysis from a dated chart folder."""
    _setup_logging(verbose)
    date = date or _today()
    from .analysis_engine import RunError, run_daily_analysis

    try:
        result = run_daily_analysis(date, input_dir, force_fetch=force_fetch)
    except (InputError, RunError) as exc:
        typer.secho(f"Run failed: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    typer.secho(f"Analysis complete for {date}", fg=typer.colors.GREEN)
    typer.echo(f"Output: {result.output_dir}")
    typer.echo(f"Recommended action: {result.daily_state.decision_matrix.recommended_action}")
    _print_validation(result.state_validation)
    _print_validation(result.report_validation)
    if result.warnings:
        typer.echo(f"{len(result.warnings)} warning(s); see run_log.json")


@app.command()
def validate(
    date: str = typer.Option(None, help="Trade date YYYY-MM-DD (default: today)."),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Re-validate previously written outputs for a date."""
    _setup_logging(verbose)
    date = date or _today()
    settings = get_settings()
    out = settings.output_dir / date

    state_path = out / f"{date}-state.json"
    report_path = out / f"{date}-analysis.md"
    if not state_path.exists() or not report_path.exists():
        typer.secho(f"No outputs found for {date} in {out}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    daily_state, state_report = parse_daily_state(read_json(state_path), date)
    report_report = validate_report(
        read_text(report_path),
        date,
        settings.max_report_chars,
        daily_state=daily_state,
    )
    _print_validation(state_report)
    _print_validation(report_report)
    if not (state_report.passed and report_report.passed):
        raise typer.Exit(code=1)


@app.command("migrate-perplexity")
def migrate_perplexity(
    history: Path = typer.Option(..., "--history", help="Path to perplexity_analysis_history.md."),
    from_date: str = typer.Option(None, "--from", help="Start date YYYY-MM-DD (inclusive)."),
    to_date: str = typer.Option(None, "--to", help="End date YYYY-MM-DD (inclusive)."),
    force_fetch: bool = typer.Option(False, help="Force fresh yfinance fetch for precompute."),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Backfill memory from Perplexity markdown (text-only; no chart packs required)."""
    _setup_logging(verbose)
    from .migrate_perplexity import MigrationError, migrate_history

    if not history.is_file():
        typer.secho(f"History file not found: {history}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    try:
        results = migrate_history(
            history,
            from_date=from_date,
            to_date=to_date,
            force_fetch=force_fetch,
        )
    except MigrationError as exc:
        typer.secho(f"Migration failed: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    typer.secho(f"Migrated {len(results)} session(s)", fg=typer.colors.GREEN)
    for result in results:
        typer.echo(
            f"  {result.date}: {result.daily_state.decision_matrix.recommended_action} "
            f"-> {result.output_dir}"
        )
        if result.warnings:
            typer.echo(f"    {len(result.warnings)} warning(s); see run_log.json")


@app.command("rebuild-summary")
def rebuild_summary(
    days: int = typer.Option(6, help="Number of recent states to include."),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Regenerate the rolling summary artifact from recent states."""
    _setup_logging(verbose)
    summary, path = rebuild_rolling_summary(days=days)
    typer.secho(f"Wrote rolling summary to {path}", fg=typer.colors.GREEN)
    typer.echo(summary)


@app.command()
def chat(
    date: str = typer.Option(None, help="Trade date YYYY-MM-DD (default: today)."),
) -> None:
    """Phase 2 stub: load a day's context for interactive discussion."""
    date = date or _today()
    from .chat_service import ChatService

    try:
        session = ChatService().start_session(date)
    except InputError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    typer.echo(f"Loaded chat context for {date}:")
    typer.echo(f"  recent states: {len(session.context.recent_states)}")
    typer.echo(f"  report chars: {len(session.context.report_markdown)}")
    typer.secho(
        "Interactive chat is a Phase 2 feature and is not yet implemented.",
        fg=typer.colors.YELLOW,
    )


def main() -> None:
    app()


if __name__ == "__main__":
    sys.exit(app())  # type: ignore[func-returns-value]
