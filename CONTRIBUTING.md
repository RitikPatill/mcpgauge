# Contributing to MCPGauge

## Prerequisites

- **Python 3.11+** — MCPGauge uses `asyncio` features and type hints that require 3.11.
- **[uv](https://docs.astral.sh/uv/)** — used for dependency management and running scripts.
- **Node.js / npx** — only needed if you want to run the filesystem or sqlite example suites locally (they spawn `@modelcontextprotocol/server-filesystem` via `npx`).

## Setup

```bash
git clone https://github.com/your-org/mcpgauge
cd mcpgauge
uv sync
uv run pre-commit install
```

`uv sync` installs the package and all dev dependencies from `pyproject.toml`. `pre-commit install` wires up ruff format + lint to run automatically on every `git commit`.

## Running tests

```bash
uv run pytest                        # unit tests only (no external processes)
uv run pytest -m integration         # includes subprocess-spawning tests (needs npx)
```

Unit tests run without any external dependencies. Integration tests spin up real MCP server subprocesses, so they require `npx` and a network connection for the first run (to download the server packages). They are skipped automatically if `npx` is not on the path.

## Linting and formatting

```bash
uv run ruff check .
uv run ruff format .
```

The pre-commit hook runs both commands on staged files before every commit. If you want to check everything at once, run `make lint` (see the `Makefile` for all available targets).

## Project layout

Source lives in `src/mcpgauge/` — one module per concern: `client.py` (MCP transport), `runner.py` (agent loop + suite orchestrator), `judge.py` (LLM-as-judge), `store.py` (SQLite persistence), `diff.py` (run comparison), `app.py` (FastAPI + HTMX), `cli.py` (typer entry point), `schema.py` (Pydantic models), `loader.py` (YAML parser). Tests live in `tests/`. YAML example suites and mock servers live in `examples/`. Static assets and docs live in `docs/`.

## Adding a test suite

The easiest way to contribute is to add a new YAML suite for an MCP server you care about. Use [`examples/filesystem_basic.yaml`](examples/filesystem_basic.yaml) as the template. New suites do not require any Python changes — drop the `.yaml` file in `examples/` and open a PR. Include at least two cases and at least one `required: true` criterion per case so CI has something to enforce.

## Submitting a PR

1. Branch off `main`: `git checkout -b my-feature`
2. Keep commits small and focused — one logical change per commit.
3. Pre-commit runs automatically on `git commit` and will block the commit if lint or format checks fail. Fix the reported issues and re-stage.
4. Open a pull request against `main`. Describe what the change does and why. Link to any relevant issue.

## Design context

Before making architectural changes, read [`docs/design-notes.md`](docs/design-notes.md). It explains the non-obvious choices: why the judge uses `tool_choice: any`, why SQLite was chosen over a server-based store, why HTMX was chosen over a JS framework, and how the security suite is structured. Keeping changes consistent with these decisions makes reviews faster.
