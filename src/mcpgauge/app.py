"""FastAPI web application for the MCPGauge dashboard."""

from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlmodel import Session, select

from mcpgauge.store import (
    CaseResult,
    Run,
    ToolCall,
    get_case_results,
    get_engine,
    get_judgments,
    get_run,
    get_tool_calls,
    init_db,
)

_templates = Jinja2Templates(directory=Path(__file__).parent / "templates")

# Module-level state: MCP server connection config and per-run SSE queues
_session: dict = {"transport": "stdio", "server_command": None, "server_url": None}
_run_queues: dict[str, asyncio.Queue] = {}


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class RunOut(BaseModel):
    id: str
    suite_name: str
    created_at: str
    total_cases: int
    passed_cases: int


class CaseOut(BaseModel):
    id: str
    case_id: str
    status: str
    prompt: str
    final_response: str
    error: Optional[str]


class ToolCallOut(BaseModel):
    id: str
    turn: int
    tool_name: str
    arguments_json: str
    result_json: str
    is_error: bool
    duration_ms: int


class JudgmentOut(BaseModel):
    id: str
    criterion_name: str
    passed: bool
    reasoning: str


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class ConnectRequest(BaseModel):
    transport: str
    command: Optional[str] = None
    url: Optional[str] = None


class RunRequest(BaseModel):
    suite_path: str


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------


def create_app(db_path: str = "mcpgauge.db", engine=None) -> FastAPI:
    """Create and return the FastAPI application.

    Parameters
    ----------
    db_path:
        Path to the SQLite database file.  Use ``":memory:"`` in tests.
    engine:
        Optional pre-built SQLAlchemy engine (skips ``get_engine``/``init_db``).
    """
    fastapi_app = FastAPI(title="MCPGauge", version="0.1.0")

    if engine is None:
        engine = get_engine(db_path)
        init_db(engine)

    fastapi_app.state.engine = engine

    # ------------------------------------------------------------------
    # HTML pages
    # ------------------------------------------------------------------

    @fastapi_app.get("/", include_in_schema=False)
    async def root():
        return RedirectResponse(url="/runs", status_code=307)

    @fastapi_app.get("/runs", response_class=HTMLResponse)
    async def runs_page(request: Request):
        return _templates.TemplateResponse(request, "runs.html")

    @fastapi_app.get("/runs/{run_id}", response_class=HTMLResponse)
    async def run_detail_page(request: Request, run_id: str):
        run = get_run(fastapi_app.state.engine, run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        cases = get_case_results(fastapi_app.state.engine, run_id)
        return _templates.TemplateResponse(
            request,
            "run_detail.html",
            {"run": run, "cases": cases},
        )

    @fastapi_app.get("/runs/{run_id}/cases/{case_result_id}", response_class=HTMLResponse)
    async def case_detail_page(request: Request, run_id: str, case_result_id: str):
        run = get_run(fastapi_app.state.engine, run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        cases = get_case_results(fastapi_app.state.engine, run_id)
        case = next((c for c in cases if c.id == case_result_id), None)
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")
        tool_calls = get_tool_calls(fastapi_app.state.engine, case_result_id)
        judgments = get_judgments(fastapi_app.state.engine, case_result_id)
        return _templates.TemplateResponse(
            request,
            "case_detail.html",
            {
                "run": run,
                "case": case,
                "tool_calls": tool_calls,
                "judgments": judgments,
            },
        )

    # ------------------------------------------------------------------
    # REST API
    # ------------------------------------------------------------------

    @fastapi_app.get("/api/runs", response_model=list[RunOut])
    async def api_list_runs():
        with Session(fastapi_app.state.engine) as session:
            runs = list(session.exec(select(Run).order_by(Run.created_at.desc())).all())
        return [
            RunOut(
                id=r.id,
                suite_name=r.suite_name,
                created_at=r.created_at.isoformat(),
                total_cases=r.total_cases,
                passed_cases=r.passed_cases,
            )
            for r in runs
        ]

    @fastapi_app.get("/api/runs/{run_id}")
    async def api_get_run(run_id: str):
        run = get_run(fastapi_app.state.engine, run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        cases = get_case_results(fastapi_app.state.engine, run_id)
        run_out = RunOut(
            id=run.id,
            suite_name=run.suite_name,
            created_at=run.created_at.isoformat(),
            total_cases=run.total_cases,
            passed_cases=run.passed_cases,
        )
        cases_out = [
            CaseOut(
                id=c.id,
                case_id=c.case_id,
                status=c.status,
                prompt=c.prompt,
                final_response=c.final_response,
                error=c.error,
            ).model_dump()
            for c in cases
        ]
        return {**run_out.model_dump(), "cases": cases_out}

    @fastapi_app.get("/api/runs/{run_id}/cases/{case_result_id}")
    async def api_get_case(run_id: str, case_result_id: str):
        cases = get_case_results(fastapi_app.state.engine, run_id)
        case = next((c for c in cases if c.id == case_result_id), None)
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")
        tool_calls = get_tool_calls(fastapi_app.state.engine, case_result_id)
        judgments = get_judgments(fastapi_app.state.engine, case_result_id)
        return {
            **CaseOut(
                id=case.id,
                case_id=case.case_id,
                status=case.status,
                prompt=case.prompt,
                final_response=case.final_response,
                error=case.error,
            ).model_dump(),
            "tool_calls": [
                ToolCallOut(
                    id=tc.id,
                    turn=tc.turn,
                    tool_name=tc.tool_name,
                    arguments_json=tc.arguments_json,
                    result_json=tc.result_json,
                    is_error=tc.is_error,
                    duration_ms=tc.duration_ms,
                ).model_dump()
                for tc in tool_calls
            ],
            "judgments": [
                JudgmentOut(
                    id=j.id,
                    criterion_name=j.criterion_name,
                    passed=j.passed,
                    reasoning=j.reasoning,
                ).model_dump()
                for j in judgments
            ],
        }

    @fastapi_app.get("/api/runs/{run_id}/events")
    async def api_run_events(request: Request, run_id: str):
        # If there's no live queue for this run, check if it's already finished
        # and immediately send run_done.
        if run_id not in _run_queues:
            run = get_run(fastapi_app.state.engine, run_id)

            async def _done_gen():
                yield 'event: run_done\ndata: {}\n\n'

            if run:
                return StreamingResponse(
                    _done_gen(),
                    media_type="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
                )

        q: asyncio.Queue = _run_queues.get(run_id, asyncio.Queue())
        _run_queues[run_id] = q

        async def _event_gen():
            try:
                while True:
                    if await request.is_disconnected():
                        break
                    try:
                        msg = await asyncio.wait_for(q.get(), timeout=15)
                    except asyncio.TimeoutError:
                        yield 'data: {"event":"ping"}\n\n'
                        continue
                    event_name = msg.get("event", "message")
                    data = msg.get("data", "")
                    # Data may be a string (HTML fragment) or dict
                    if isinstance(data, dict):
                        data_str = json.dumps(data)
                    else:
                        data_str = str(data)
                    yield f"event: {event_name}\ndata: {data_str}\n\n"
                    if event_name == "run_done":
                        break
            finally:
                _run_queues.pop(run_id, None)

        return StreamingResponse(
            _event_gen(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @fastapi_app.post("/api/connect")
    async def api_connect(req: ConnectRequest):
        from mcpgauge.client import MCPClient

        if req.transport not in ("stdio", "sse"):
            raise HTTPException(status_code=422, detail=f"Unknown transport: {req.transport}")
        if req.transport == "stdio" and not req.command:
            raise HTTPException(status_code=422, detail="command is required for stdio transport")
        if req.transport == "sse" and not req.url:
            raise HTTPException(status_code=422, detail="url is required for sse transport")

        client = MCPClient()
        try:
            if req.transport == "stdio":
                parts = req.command.split()  # type: ignore[union-attr]
                await client.connect_stdio(parts[0], parts[1:])
            else:
                await client.connect_sse(req.url)  # type: ignore[arg-type]
            tools = await client.list_tools()
            tool_list = [{"name": t.name, "description": t.description or ""} for t in tools]
            _session["transport"] = req.transport
            _session["server_command"] = req.command
            _session["server_url"] = req.url
            await client.disconnect()
            return {"tools": tool_list, "transport": req.transport, "command": req.command}
        except HTTPException:
            raise
        except Exception as exc:
            return {"error": str(exc)}

    @fastapi_app.post("/api/runs")
    async def api_create_run(req: RunRequest):
        import os
        from pathlib import Path as _Path

        import anthropic

        from mcpgauge.loader import SuiteLoadError, load_suite
        from mcpgauge.runner import run_suite

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise HTTPException(status_code=400, detail="ANTHROPIC_API_KEY not set")

        try:
            suite = load_suite(_Path(req.suite_path))
        except SuiteLoadError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

        run_id = str(uuid.uuid4())
        q: asyncio.Queue = asyncio.Queue()
        _run_queues[run_id] = q

        anthropic_client = anthropic.AsyncAnthropic(api_key=api_key)

        def on_case_done(case, cr, trace, verdicts):
            loop = asyncio.get_running_loop()
            _q = _run_queues.get(run_id)
            if _q:
                status_icon = "✓" if cr.status == "passed" else ("✗" if cr.status == "failed" else "⚠")
                snippet = (cr.final_response or "")[:80]
                row_html = (
                    f'<tr class="border-b hover:bg-gray-50">'
                    f'<td class="px-4 py-2 font-mono text-sm">{cr.case_id}</td>'
                    f'<td class="px-4 py-2">'
                    f'<span class="{"text-green-600" if cr.status == "passed" else "text-red-600"} font-bold">'
                    f'{status_icon} {cr.status}</span></td>'
                    f'<td class="px-4 py-2 text-sm text-gray-600">'
                    f'<a href="/runs/{run_id}/cases/{cr.id}" class="hover:underline">'
                    f'{snippet}{"..." if len(cr.final_response or "") > 80 else ""}</a></td>'
                    f'</tr>'
                )
                loop.create_task(_q.put({"event": "case_done", "data": row_html}))

        async def _background_run():
            try:
                await run_suite(
                    suite,
                    fastapi_app.state.engine,
                    anthropic_client,
                    on_case_done=on_case_done,
                    run_id=run_id,
                )
            finally:
                _q = _run_queues.get(run_id)
                if _q:
                    await _q.put({"event": "run_done", "data": {}})

        asyncio.create_task(_background_run())
        return {"run_id": run_id}

    return fastapi_app
