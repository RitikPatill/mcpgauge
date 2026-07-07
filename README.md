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

## What works now (M6)

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
| **Suite schema** (`src/mcpgauge/schema.py`) — Pydantic v2 models: `Criterion`, `Rubric`, `Case`, `Suite` | **done** |
| **YAML loader** (`src/mcpgauge/loader.py`) — `load_suite(path)` with readable validation errors | **done** |
| **Example suites** (`examples/filesystem_basic.yaml`, `examples/sqlite_basic.yaml`) | **done** |
| **Agent runner** (`src/mcpgauge/runner.py`) — drives Claude Haiku's tool-use API turn-by-turn until `end_turn`, recording every `ToolCallRecord` into an `AgentTrace` | **done** |
| **Suite orchestrator** (`run_suite`) — connects the MCP client, iterates cases, calls judge, persists results | **done** |
| **LLM-as-judge** (`src/mcpgauge/judge.py`) — sends the trace to a second Claude call with `tool_choice: any`, forcing structured `record_judgments` output; returns `CriterionVerdict` per rubric criterion | **done** |
| **SQLite store** (`src/mcpgauge/store.py`) — SQLModel table models: `Run`, `CaseResult`, `ToolCall`, `Judgment`; thin CRUD helpers; `init_db` / `get_engine` | **done** |
| **`mcpgauge run`** — functional CLI command: loads suite, initialises DB, runs agent + judge, prints per-case pass/fail, writes run UUID | **done** |
| **FastAPI app** (`src/mcpgauge/app.py`) — REST API (`/api/runs`, `/api/runs/{id}`, `/api/runs/{id}/cases/{id}`), SSE live-stream (`/api/runs/{id}/events`), Connect MCP server endpoint (`/api/connect`), trigger run from UI (`POST /api/runs`) | **done** |
| **HTMX + Tailwind dashboard** — runs list page, run detail page with live case streaming, case detail page with agent trace timeline and per-criterion judge verdicts | **done** |
| **`mcpgauge serve`** — starts FastAPI on `localhost:8000`, opens browser automatically | **done** |
| **Run diff** (`src/mcpgauge/diff.py`) — `compute_diff(engine, run_id_a, run_id_b)` returns a `RunDiff` with per-case status changes, per-criterion verdict diffs, and regression/fix/unchanged counts | **done** |
| **`GET /api/runs/{a}/diff/{b}`** — JSON diff endpoint | **done** |
| **`GET /runs/{a}/diff/{b}`** — HTML diff page with summary chips, colour-coded case table, and expandable criterion details | **done** |
| **Compare widget** on run detail page — pick a second run from a dropdown and navigate to the diff view | **done** |
| **`mcpgauge diff <run_a> <run_b>`** — CLI command printing a plain-text regression table | **done** |

### Loading a suite

```python
from mcpgauge.loader import load_suite, SuiteLoadError

try:
    suite = load_suite("examples/filesystem_basic.yaml")
    print(suite.name, len(suite.cases))  # filesystem_basic 2
except SuiteLoadError as e:
    print(e)  # human-readable field-path error
```

### Suite YAML structure

```yaml
name: my_suite
description: "Optional description."
transport: stdio                        # stdio | sse
server_command: [npx, -y, my-mcp-server]  # required for stdio
# server_url: http://localhost:8000/sse  # required for sse

cases:
  - id: unique_case_id
    prompt: "Natural-language instruction for the agent."
    expected_tools: [tool_name]         # optional; used for later scoring
    max_turns: 10                       # default 10, max 50
    golden_output: "Optional reference answer."
    rubric:
      criteria:
        - name: criterion_name
          description: "What the judge checks for."
          required: true                # default true
```

Full worked examples: [`examples/filesystem_basic.yaml`](examples/filesystem_basic.yaml), [`examples/sqlite_basic.yaml`](examples/sqlite_basic.yaml).

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
  run      Run a YAML test suite against an MCP server.
  serve    Start the dashboard web UI.
  diff     Compare two runs side by side.
```

Start the dashboard:

```bash
mcpgauge serve
# opens http://localhost:8000/runs in your browser
# paste a stdio command or SSE URL to connect an MCP server
# click "Run Suite" to trigger a YAML suite run and watch cases stream in live
```

Run a suite from the CLI:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
mcpgauge run examples/filesystem_basic.yaml
# Running suite: filesystem_basic (2 cases)
#   [✓] list_tmp: passed
#   [✗] write_file: failed
# Run 3f8a2...: 1/2 passed
```

Compare two runs from the CLI:

```bash
mcpgauge diff 3f8a2... 9c1b4...
# Case             A        B        Change
# list_tmp         passed   passed   unchanged
# write_file       failed   passed   fixed
# delete_file      passed   failed   regressed
# 1 regression, 1 fix, 1 unchanged
```

Results are written to `mcpgauge.db` (SQLite). Override the path with `--db`:

```bash
mcpgauge run examples/filesystem_basic.yaml --db /tmp/eval.db
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
+----------------------------+       +----------------------------------+
|  CLI (typer)               |       |  Web UI (HTMX + Tailwind)        |
|  mcpgauge run / serve      |       |  served by FastAPI)               |
|  mcpgauge diff             |       |  /runs/{a}/diff/{b} diff page    |
+-------------+--------------+       +-----------+----------------------+
              |                                  |
              v                                  v
+---------------------------------------------------------------+
|                    Core: runner + scheduler                    |
|  - loads YAML suite                                            |
|  - spawns MCP client (stdio/SSE)                               |
|  - drives agent loop (Anthropic tool-use)                      |
|  - streams events via server-sent events                       |
+------+------------------+----------+-----------+---------------+
       |                  |          |           |
       v                  v          v           v
  +----------+     +--------------+ +--------+ +------------------+
  | MCP      |     | Judge        | | Diff   | | Store (SQLite)   |
  | client   |     | (LLM rubric  | | engine | | runs, cases,     |
  | (SDK)    |     |  scorer)     | | diff.py| | tool_calls,      |
  +----+-----+     +------+-------+ +--------+ | judgments        |
       |                  |                    +------------------+
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
- [x] **M2** — MCP client: stdio + SSE transport, tool/resource/prompt discovery
- [x] **M3** — Suite schema (Pydantic v2) + YAML loader + example suites
- [x] **M4** — Agent runner (Anthropic tool-use loop) + LLM-as-judge scorer + SQLite persistence via SQLModel
- [x] **M5** — FastAPI + HTMX dashboard: runs list + case detail
- [x] **M6** — Run diff view: per-case status changes, per-criterion verdict diffs, CLI `mcpgauge diff`
- [ ] **M7** — Example suites: filesystem, sqlite, security/poisoning

---

## License

MIT — see [LICENSE](LICENSE).
