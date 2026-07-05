# MCPGauge

**MCPGauge is a self-hostable eval harness for MCP servers.**

[![CI](https://github.com/your-org/mcpgauge/actions/workflows/ci.yml/badge.svg)](https://github.com/your-org/mcpgauge/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Why it exists

The MCP ecosystem exploded in 2025, but shipping an MCP server is only half the problem. Right now people evaluate them by hand in Claude Desktop. There is no equivalent of `pytest` for MCP that measures whether the LLM can actually discover and call your tools correctly, whether outputs match a rubric (correctness, safety, format), or whether a new server version regresses against the previous one.

MCPGauge fills that gap with a small, focused, open-source tool. Point it at any MCP server (stdio or SSE transport), write a YAML suite of scenarios, and MCPGauge runs an agent against the server's tools, scores each run with an LLM-as-judge against your rubric, stores results in a local SQLite database, and renders a live dashboard where you can drill into every tool call.

## Target user

MCP server authors who want automated regression testing — anyone who has written an MCP server and currently tests it by hand in Claude Desktop or by eyeballing logs.

---

## What works now (M2)

| Area | Status |
|---|---|
| Package scaffold (`src/mcpgauge`, `pyproject.toml`) | done |
| Dependency management via `uv` | done |
| CLI entry point (`mcpgauge version`) | done |
| Linting via `ruff` (E, F, I, UP rules; line-length 100) | done |
| Test suite via `pytest` + `anyio` | done |
| Pre-commit hooks (ruff format + lint) | done |
| CI (GitHub Actions: lint + test on push/PR) | done |
| MIT license | done |
| **MCP client** (`src/mcpgauge/client.py`) — stdio + SSE transport | **done** |
| **Tool/resource/prompt discovery** via `list_tools` / `list_resources` / `list_prompts` | **done** |
| **Tool invocation** via `call_tool` returning normalised `ToolResult` | **done** |
| **Unit tests** (Python subprocess echo server, no Node.js required) | **done** |
| **Integration tests** (reference filesystem MCP server via `npx`, auto-skipped if no Node.js) | **done** |

`run`, `serve`, and `diff` commands are stubs — they will be implemented in M3–M8.

---

## Quickstart

```bash
git clone https://github.com/your-org/mcpgauge
cd mcpgauge
uv sync
mcpgauge --help
```

```
Usage: mcpgauge [OPTIONS] COMMAND [ARGS]...

  Eval harness for MCP servers.

Commands:
  version  Print the version and exit.
  run      [coming soon] Run a YAML test suite against an MCP server.
  serve    [coming soon] Start the dashboard web UI.
  diff     [coming soon] Compare two runs side by side.
```

Use `MCPClient` directly in Python:

```python
import asyncio
from mcpgauge.client import MCPClient

async def main():
    async with MCPClient() as client:
        # stdio transport: spawn a local server process
        await client.connect_stdio(
            "npx", ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]
        )
        tools = await client.list_tools()
        print([t.name for t in tools])

        result = await client.call_tool("list_directory", {"path": "/tmp"})
        print(result.is_error, result.content)

asyncio.run(main())
```

For an SSE server that is already running:

```python
await client.connect_sse("http://localhost:8000/sse")
```

Run the test suite and linter locally:

```bash
uv run pytest          # unit + integration tests (integration skipped without npx)
uv run ruff check .    # lint
uv run ruff format .   # format
```

---

## Architecture

```
+----------------------------+       +-------------------------+
|  CLI (typer)               |       |  Web UI (HTMX + Tailwind|
|  mcpgauge run / serve      |       |  served by FastAPI)     |
+-------------+--------------+       +-----------+-------------+
              |                                  |
              v                                  v
+---------------------------------------------------------------+
|                    Core: runner + scheduler                    |
|  - loads YAML suite                                            |
|  - spawns MCP client (stdio/SSE)                               |
|  - drives agent loop (Anthropic tool-use)                      |
|  - streams events via server-sent events                       |
+------+------------------+----------------------+---------------+
       |                  |                      |
       v                  v                      v
  +----------+     +--------------+     +------------------+
  | MCP      |     | Judge        |     | Store (SQLite)   |
  | client   |     | (LLM rubric  |     | runs, cases,     |
  | (SDK)    |     |  scorer)     |     | tool_calls,      |
  +----+-----+     +------+-------+     | judgments        |
       |                  |             +------------------+
       v                  v
  +----------+     +--------------+
  | Target   |     | Anthropic /  |
  | MCP      |     | OpenAI API   |
  | server   |     +--------------+
  +----------+
```

---

## Roadmap

- [x] **M1** — Scaffold + README
- [x] **M2** — MCP client: stdio + SSE transport, tool/resource/prompt discovery (you are here)
- [ ] **M3** — Agent loop: Anthropic tool-use API, conversation driver
- [ ] **M4** — YAML suite loader + scenario runner
- [ ] **M5** — LLM-as-judge scorer with structured rubric
- [ ] **M6** — SQLite store (SQLModel): runs, cases, tool calls, judgments
- [ ] **M7** — FastAPI + HTMX dashboard: runs list + case detail
- [ ] **M8** — Trace timeline + run diff view
- [ ] **M9** — Example suites: filesystem, sqlite, security/poisoning

---

## License

MIT — see [LICENSE](LICENSE).
