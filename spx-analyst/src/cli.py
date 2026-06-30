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
    precompute: bool = typer.Option(False, help="Run yfinance precompute if EPS resolves."),
    force_fetch: bool = typer.Option(False, help="Force fresh yfinance fetch."),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Scaffold a run directory and optionally run Step 0 precompute."""
    _setup_logging(verbose)
    date = date or _today()
    settings = get_settings()
    from .eps_history import get_eps_for_run, require_eps_for_run
    from .files import resolve_run_dir, scaffold_run_dir

    run_dir = Path(input_dir) if input_dir else settings.runs_dir / date
    scaffold_run_dir(run_dir, date)

    resolution = get_eps_for_run(date, settings=settings)
    if resolution.eps is None:
        for warning in resolution.warnings:
            typer.secho(warning, fg=typer.colors.YELLOW, err=True)
        typer.secho(
            "Run is not ready — append EPS to data/master/eps_history.json before precompute/run.",
            fg=typer.colors.YELLOW,
        )
    else:
        typer.echo(
            f"EPS resolved: forward={resolution.forward_eps} trailing={resolution.trailing_eps} "
            f"(effective_from={resolution.effective_from})"
        )

    if precompute:
        from .files import load_manifest
        from .precompute import run_precompute

        try:
            manifest = load_manifest(run_dir)
        except InputError as exc:
            typer.secho(f"Cannot precompute: {exc}", fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1)
        try:
            eps, _ = require_eps_for_run(date, settings=settings)
        except InputError as exc:
            typer.secho(str(exc), fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1)
        ctx = run_precompute(date, run_dir, manifest, eps, settings=settings, force_fetch=force_fetch)
        typer.secho(f"Wrote analysis_context.json (close={ctx.market_data.spx_close})", fg=typer.colors.GREEN)

    typer.echo(f"Run directory ready: {run_dir}")


@app.command("import-run")
def import_run_cmd(
    date: str = typer.Option(None, help="Trade date YYYY-MM-DD (default: today)."),
    images_dir: str = typer.Option(
        None, help="Intake folder with 15 PNGs (default: ../Images/<date>)."
    ),
    input_dir: str = typer.Option(None, help="Run directory (default: data/runs/<date>)."),
    force: bool = typer.Option(False, help="Overwrite an existing imported run."),
    close: float = typer.Option(None, help="Override manifest.close (default: yfinance)."),
    precompute: bool = typer.Option(False, help="Run Step 0 precompute after import."),
    force_fetch: bool = typer.Option(False, help="Force fresh yfinance fetch during precompute."),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Import 15 PNG screenshots from Images/<date>/ into a production run directory."""
    _setup_logging(verbose)
    date = date or _today()
    settings = get_settings()
    from .eps_history import require_eps_for_run
    from .import_run import default_images_dir, import_run
    from .precompute import run_precompute

    images_path = Path(images_dir) if images_dir else default_images_dir(date)
    run_dir = Path(input_dir) if input_dir else settings.runs_dir / date
    close_override = close if close is not None else None

    try:
        result = import_run(
            date,
            images_dir=images_path,
            run_dir=run_dir,
            force=force,
            close_override=close_override,
            settings=settings,
        )
    except InputError as exc:
        typer.secho(f"Import failed: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    typer.secho(
        f"Imported {result.manifest.chart_count} charts → {result.run_dir}",
        fg=typer.colors.GREEN,
    )
    typer.echo(f"manifest.close={result.close}")
    for warning in result.warnings:
        typer.secho(warning, fg=typer.colors.YELLOW, err=True)

    if precompute:
        try:
            eps, _ = require_eps_for_run(date, settings=settings)
        except InputError as exc:
            typer.secho(str(exc), fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1)
        ctx = run_precompute(
            date, run_dir, result.manifest, eps, settings=settings, force_fetch=force_fetch
        )
        typer.secho(
            f"Wrote analysis_context.json (close={ctx.market_data.spx_close})",
            fg=typer.colors.GREEN,
        )


@app.command("show-eps")
def show_eps(
    date: str = typer.Option(None, help="Trade date YYYY-MM-DD (default: today)."),
) -> None:
    """Show EPS resolved from master history for a run date."""
    date = date or _today()
    settings = get_settings()
    from .eps_history import get_eps_for_run

    resolution = get_eps_for_run(date, settings=settings)
    if resolution.eps is None:
        for warning in resolution.warnings:
            typer.secho(warning, fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    typer.echo(
        f"EPS for {date}: forward={resolution.forward_eps} trailing={resolution.trailing_eps} "
        f"(effective_from={resolution.effective_from})"
    )


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


@app.command("export-report")
def export_report(
    date: str = typer.Option(None, help="Trade date YYYY-MM-DD (default: today)."),
    input_path: Path = typer.Option(
        None,
        "--input",
        help="Path to markdown report (default: memory/daily_reports/{date}-analysis.md).",
    ),
    output: Path = typer.Option(
        None,
        "--output",
        "-o",
        help="Output PDF path (default: daily_pdfs/{date}-investor-report.pdf).",
    ),
    open_file: bool = typer.Option(False, "--open", help="Open the PDF after export."),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Render a formatted investor PDF report from daily markdown."""
    _setup_logging(verbose)
    date = date or _today()
    settings = get_settings()
    settings.daily_pdfs_dir.mkdir(parents=True, exist_ok=True)
    source = input_path or (settings.daily_reports_dir / f"{date}-analysis.md")

    if not source.is_file():
        typer.secho(f"Report not found: {source}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    from .investor_report_export import export_investor_report

    dest = export_investor_report(
        source,
        output,
        fallback_date=date,
        pdf_dir=settings.daily_pdfs_dir,
    )
    typer.secho(f"Wrote {dest}", fg=typer.colors.GREEN)

    if open_file:
        import subprocess
        import sys

        if sys.platform == "darwin":
            subprocess.run(["open", str(dest)], check=False)
        elif sys.platform.startswith("linux"):
            subprocess.run(["xdg-open", str(dest)], check=False)
        elif sys.platform == "win32":
            subprocess.run(["start", "", str(dest)], shell=True, check=False)


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
    except InputError as exc:
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


@app.command("index-rag")
def index_rag(
    date: str = typer.Option(None, help="Trade date YYYY-MM-DD to index."),
    backfill: bool = typer.Option(False, help="Index all reports in memory/daily_reports/."),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Upload report sections to the OpenAI vector store for historical retrieval."""
    _setup_logging(verbose)
    from .rag_index import RagIndexError, backfill_rag_index, index_report_rag

    try:
        if backfill:
            manifests = backfill_rag_index()
            typer.secho(f"Indexed {len(manifests)} report(s)", fg=typer.colors.GREEN)
            for manifest in manifests:
                typer.echo(f"  {manifest.date}: {len(manifest.sections)} sections")
            return

        if not date:
            typer.secho("Provide --date YYYY-MM-DD or --backfill", fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1)

        manifest = index_report_rag(date)
    except RagIndexError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    typer.secho(
        f"Indexed {len(manifest.sections)} sections for {manifest.date}",
        fg=typer.colors.GREEN,
    )


@app.command()
def chat(
    session_id: str = typer.Option(None, help="Resume an existing session id."),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Interactive research assistant REPL (OpenAI Responses + latest-run preload)."""
    _setup_logging(verbose)
    from .chat_service import ChatService, ChatServiceError, SessionNotFoundError
    from .chat_sessions import get_session

    service = ChatService()
    try:
        if session_id:
            record = get_session(session_id, service.settings)
            typer.echo(f"Resumed session {record.id}: {record.title}")
        else:
            record = service.create_session()
            typer.echo(f"New session {record.id}")
    except SessionNotFoundError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)
    except ChatServiceError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    typer.echo("Ask about current posture or historical runs. Type 'exit' or 'quit' to leave.")
    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            typer.echo("")
            break
        if not user_input:
            continue
        if user_input.lower() in {"exit", "quit"}:
            break

        typer.echo("Assistant:", nl=False)
        try:
            for chunk in service.stream_reply(record.id, user_input):
                typer.echo(chunk, nl=False)
        except ChatServiceError as exc:
            typer.echo("")
            typer.secho(str(exc), fg=typer.colors.RED, err=True)
            continue
        typer.echo("")


def main() -> None:
    app()


if __name__ == "__main__":
    sys.exit(app())  # type: ignore[func-returns-value]
