from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Annotated

import typer

app = typer.Typer(name="mcpgauge", help="Eval harness for MCP servers.")


@app.command()
def version():
    """Print the version and exit."""
    typer.echo("mcpgauge 0.1.0")


@app.command()
def run(
    suite_path: Annotated[Path, typer.Argument(help="Path to suite YAML")],
    db: Annotated[Path, typer.Option(help="SQLite DB path")] = Path("mcpgauge.db"),
    model: Annotated[str, typer.Option(help="Anthropic model")] = "claude-haiku-4-5-20251001",
) -> None:
    """Run a test suite against an MCP server and store results."""
    from mcpgauge.loader import SuiteLoadError, load_suite
    from mcpgauge.runner import run_suite
    from mcpgauge.store import get_engine, init_db

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        typer.echo("Error: ANTHROPIC_API_KEY environment variable is not set.", err=True)
        raise typer.Exit(1)

    try:
        suite = load_suite(suite_path)
    except SuiteLoadError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)

    import anthropic

    engine = get_engine(str(db))
    init_db(engine)

    anthropic_client = anthropic.AsyncAnthropic(api_key=api_key)

    results_summary: list[tuple[str, str]] = []

    def on_case_done(case, cr, trace, verdicts):
        icon = "✓" if cr.status == "passed" else "✗"
        results_summary.append((case.id, cr.status))
        typer.echo(f"  [{icon}] {case.id}: {cr.status}")

    typer.echo(f"Running suite: {suite.name} ({len(suite.cases)} cases)")

    run_id = asyncio.run(
        run_suite(suite, engine, anthropic_client, model, on_case_done=on_case_done)
    )

    passed = sum(1 for _, s in results_summary if s == "passed")
    total = len(results_summary)
    typer.echo(f"\nRun {run_id}: {passed}/{total} passed")


@app.command()
def serve(
    db: str = typer.Option("mcpgauge.db", help="Path to SQLite database"),
    host: str = typer.Option("127.0.0.1", help="Host to bind to"),
    port: int = typer.Option(8000, help="Port to listen on"),
    open_browser: bool = typer.Option(True, "--open/--no-open", help="Open browser on start"),
) -> None:
    """Start the MCPGauge web dashboard."""
    import threading
    import webbrowser

    import uvicorn

    from mcpgauge.app import create_app

    web_app = create_app(db_path=db)
    if open_browser:
        threading.Timer(1.0, lambda: webbrowser.open(f"http://{host}:{port}/runs")).start()
    uvicorn.run(web_app, host=host, port=port)


@app.command()
def diff(
    run_a: str = typer.Argument(..., help="First run ID (baseline)"),
    run_b: str = typer.Argument(..., help="Second run ID (comparison)"),
    db: Path = typer.Option(Path("mcpgauge.db"), "--db", help="Path to SQLite DB"),
) -> None:
    """Print a regression diff between two runs."""
    from mcpgauge.diff import compute_diff
    from mcpgauge.store import get_engine, init_db

    engine = get_engine(str(db))
    init_db(engine)

    try:
        d = compute_diff(engine, run_a, run_b)
    except ValueError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1)

    typer.echo(f"Diff  A={run_a[:8]}  vs  B={run_b[:8]}  (suite: {d.run_a.suite_name})")
    typer.echo(f"Regressions: {d.regressions}  Fixes: {d.fixes}  Unchanged: {d.unchanged}")
    typer.echo("")

    header = f"{'CASE':<30}  {'STATUS_A':<10}  {'STATUS_B':<10}  CHANGE"
    typer.echo(header)
    typer.echo("-" * len(header))
    for c in d.cases:
        marker = {"regression": "!!!", "fix": "+++", "same": "   "}.get(c.change, "   ")
        typer.echo(f"{c.case_id:<30}  {c.status_a:<10}  {c.status_b:<10}  {marker} {c.change}")
        for cr in c.criteria:
            if cr.changed:
                a_sym = "(P)" if cr.passed_a else ("(F)" if cr.passed_a is not None else "(-)")
                b_sym = "(P)" if cr.passed_b else ("(F)" if cr.passed_b is not None else "(-)")
                typer.echo(f"  criterion {cr.criterion_name}: {a_sym} -> {b_sym}")


if __name__ == "__main__":
    app()
