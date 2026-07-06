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


if __name__ == "__main__":
    app()
