# MCPGauge

[![CI](https://github.com/RitikPatill/mcpgauge/actions/workflows/ci.yml/badge.svg)](https://github.com/RitikPatill/mcpgauge/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)
![uv](https://img.shields.io/badge/package%20manager-uv-purple)

> Benchmark any MCP server with rubric-driven tests, LLM-as-judge scoring, and a live web dashboard showing tool-call traces and regressions.

<!-- TODO: replace with a 5-10 second demo gif. Record with ScreenToGif on
     Windows or peek on macOS. Save to docs/demo.gif and update path here. -->
![demo](docs/demo.gif)

## What it is

MCPGauge is a self-hostable eval harness for MCP (Model Context Protocol) servers. Point it at any server reachable over stdio or SSE, write a YAML suite of scenarios, and it runs a Claude agent against the server's tools, scores each run with an LLM-as-judge against your rubric, and stores the results in a local SQLite database — no external infra, one file, your own API key.

The dashboard lets you drill into every tool call in an agent trace, compare two runs side-by-side to catch regressions before they ship, and watch live case results stream in as a suite executes. A bundled security suite checks whether prompt-injection payloads embedded in tool outputs can hijack the agent — coverage the MCP ecosystem currently has no standard tooling for.

## Quickstart

```bash
git clone https://github.com/RitikPatill/mcpgauge.git
cd mcpgauge
make install                    # uv sync
export ANTHROPIC_API_KEY=sk-ant-...
make demo                       # run the poisoning suite end-to-end
make serve                      # open dashboard at http://localhost:8000/runs
```

Requires Python 3.11+, [uv](https://github.com/astral-sh/uv), and Node.js/npx for the filesystem and sqlite example suites.

## Usage

Run a YAML suite from the CLI:

```bash
mcpgauge run examples/filesystem_basic.yaml
# Running suite: filesystem_basic (2 cases)
#   [pass] list_tmp
#   [fail] read_missing_file
# Run 3f8a2...: 1/2 passed
```

Compare two runs to detect regressions:

```bash
mcpgauge diff 3f8a2... 9c1b4...
# Case              A       B       Change
# list_tmp          pass    pass    unchanged
# read_missing_file fail    pass    fixed
```

Open the dashboard with `mcpgauge serve` — paste a stdio command or SSE URL to connect a server, click *Run Suite* to trigger a YAML suite, then click any case to see the full agent trace: tool arguments, raw results, timing, and the judge's per-criterion verdict with reasoning. The *Compare* widget lets you pick a second run from a dropdown to view a highlighted diff.

## Architecture

```
CLI (typer)          Web UI (HTMX + Tailwind)
     |                        |
     +----------+-------------+
                |
           runner.py  ── SSE stream ──> Web UI
        Agent loop + orchestrator
         /           |           \
   client.py     judge.py     store.py
   MCP client    LLM rubric   SQLite
   stdio / SSE   scorer       (SQLModel)
        |             |
   Target MCP    Anthropic API
   server        (claude-haiku-4-5)
```

## Project structure

```
src/mcpgauge/    core package — client, runner, judge, store, diff, FastAPI app, CLI
examples/        three ready-to-run YAML suites: filesystem, sqlite, poisoning
tests/           unit and integration tests (pytest + anyio)
docs/            design notes, demo GIF, screenshot
```

## Roadmap

- [ ] SSE transport: end-to-end example suites over SSE (client is implemented; current suites target stdio only)
- [ ] Multi-model judges: plug in OpenAI or a local Ollama model as the judge instead of Claude
- [ ] HTML report export: `mcpgauge export <run_id>` producing a self-contained file for sharing without the dashboard
- [ ] Parallel case execution: run suite cases concurrently with `asyncio.gather` for faster suites
- [ ] pytest plugin: `pytest-mcpgauge` so existing pytest users can write `.py` test files that invoke MCPGauge cases

## License

MIT — see [LICENSE](LICENSE).

---

Built autonomously by [autodev](https://github.com/RitikPatill/autodev),
a multi-agent orchestrator I designed. Each commit in this repo was
authored by me; the implementation work was performed by Sonnet under
the orchestrator's control. Read the orchestrator's README to see how.
