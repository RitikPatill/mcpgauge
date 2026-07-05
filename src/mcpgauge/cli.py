import typer

app = typer.Typer(name="mcpgauge", help="Eval harness for MCP servers.")


@app.command()
def version():
    """Print the version and exit."""
    typer.echo("mcpgauge 0.1.0")


if __name__ == "__main__":
    app()
