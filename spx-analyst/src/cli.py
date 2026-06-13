"""Command-line interface for the analysis engine."""

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

app = typer.Typer(add_completion=False, help="SPX / SCHK daily analysis engine.")


def _today() -> str:
    return dt.date.today().isoformat()


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    # --verbose raises detail for our own modules only. Third-party DEBUG logs
    # (anthropic/httpx) dump full request bodies, including base64 images, so
    # keep them quiet regardless.
    logging.getLogger("src").setLevel(logging.DEBUG if verbose else logging.INFO)
    for noisy in ("anthropic", "httpx", "httpcore", "urllib3", "PIL"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def _print_validation(report: ValidationReport) -> None:
    status = "PASS" if report.passed else "FAIL"
    typer.echo(f"[{status}] {report.target} ({report.date})")
    for issue in report.issues:
        typer.echo(f"  {issue.severity.upper()} [{issue.code}] {issue.message}")


@app.command()
def run(
    date: str = typer.Option(None, help="Trade date YYYY-MM-DD (default: today)."),
    input_dir: str = typer.Option(None, help="Run directory (default: data/runs/<date>)."),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Run a complete daily analysis from a dated chart folder."""
    _setup_logging(verbose)
    date = date or _today()
    from .analysis_engine import RunError, run_daily_analysis

    try:
        result = run_daily_analysis(date, input_dir)
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


@app.command("migrate-perplexity")
def migrate_perplexity(
    history: str = typer.Option(
        "../perplexity_analysis_history.md",
        help="Path to Perplexity export markdown.",
    ),
    from_date: str = typer.Option(None, "--from", help="Start date YYYY-MM-DD (inclusive)."),
    to_date: str = typer.Option(None, "--to", help="End date YYYY-MM-DD (inclusive)."),
    dry_run: bool = typer.Option(False, help="Parse and list sessions only; no API calls."),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Migrate historical Perplexity Full 7-Step analyses into engine artifacts."""
    _setup_logging(verbose)
    from .migrate_perplexity import MigrationError, filter_sessions, migrate_history, parse_history

    history_path = Path(history)
    if not history_path.is_absolute():
        history_path = Path.cwd() / history_path
    if not history_path.exists():
        typer.secho(f"History file not found: {history_path}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    try:
        sessions = filter_sessions(parse_history(history_path), from_date=from_date, to_date=to_date)
    except MigrationError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    if not sessions:
        typer.secho("No sessions matched the date range.", fg=typer.colors.YELLOW)
        raise typer.Exit(code=1)

    typer.echo(f"Found {len(sessions)} session(s):")
    for s in sessions:
        typer.echo(f"  {s.date}  close={s.spx_close}  chars={len(s.clean_markdown)}")

    if dry_run:
        typer.secho("Dry run complete.", fg=typer.colors.GREEN)
        return

    try:
        results = migrate_history(
            history_path,
            from_date=from_date,
            to_date=to_date,
        )
    except MigrationError as exc:
        typer.secho(f"Migration failed: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    failed = 0
    for result in results:
        state_ok = result.state_validation.passed
        report_ok = result.report_validation.passed
        color = typer.colors.GREEN if state_ok and report_ok else typer.colors.YELLOW
        typer.secho(
            f"{result.date}: state={'PASS' if state_ok else 'FAIL'} "
            f"report={'PASS' if report_ok else 'FAIL'} -> {result.output_dir}",
            fg=color,
        )
        if result.warnings:
            for w in result.warnings:
                typer.echo(f"  warning: {w}")
        if not (state_ok and report_ok):
            failed += 1

    if failed:
        raise typer.Exit(code=1)


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
