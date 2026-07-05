"""Minimal FastMCP server used as a subprocess in unit tests.

Run as:
    python -m tests.helpers.echo_server

Exposes a single tool ``echo`` that returns its ``msg`` argument,
and a tool ``fail`` that always raises so tests can verify error handling.
"""

from mcp.server.fastmcp import FastMCP

app = FastMCP("echo-test-server")


@app.tool()
def echo(msg: str) -> str:
    """Return *msg* unchanged."""
    return msg


@app.tool()
def fail(reason: str = "intentional") -> str:
    """Always raises to exercise error handling."""
    raise ValueError(f"Tool error: {reason}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(app.run_stdio_async())
