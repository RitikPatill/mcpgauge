"""Agent loop and suite orchestrator for MCPGauge."""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import anthropic

from mcpgauge.client import MCPClient
from mcpgauge.schema import Case, Suite
from mcpgauge.store import CaseResult, Run, ToolCall, init_db, save_case_result, save_run, save_tool_call


@dataclass
class ToolCallRecord:
    turn: int
    tool_name: str
    arguments: dict[str, Any]
    result_content: list[dict]
    is_error: bool
    duration_ms: int


@dataclass
class AgentTrace:
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    final_response: str = ""
    error: str | None = None


def _mcp_tools_to_anthropic(tools) -> list[dict]:
    """Convert MCP tool definitions to Anthropic tool format."""
    result = []
    for t in tools:
        result.append(
            {
                "name": t.name,
                "description": t.description or "",
                "input_schema": t.inputSchema,
            }
        )
    return result


async def run_case(
    case: Case,
    client: MCPClient,
    anthropic_client: anthropic.AsyncAnthropic,
    model: str = "claude-haiku-4-5-20251001",
) -> AgentTrace:
    """Drive the agent loop for a single test case."""
    trace = AgentTrace()

    try:
        mcp_tools = await client.list_tools()
        anthropic_tools = _mcp_tools_to_anthropic(mcp_tools)

        messages: list[dict] = [{"role": "user", "content": case.prompt}]

        for turn in range(case.max_turns):
            response = await anthropic_client.messages.create(
                model=model,
                max_tokens=4096,
                tools=anthropic_tools,
                messages=messages,
            )

            if response.stop_reason == "end_turn":
                # Extract final text response
                for block in response.content:
                    if hasattr(block, "text"):
                        trace.final_response = block.text
                        break
                break

            if response.stop_reason == "tool_use":
                # Append the assistant message with full content
                messages.append({"role": "assistant", "content": response.content})

                tool_result_blocks = []
                for block in response.content:
                    if block.type != "tool_use":
                        continue

                    t_start = time.monotonic()
                    tool_result = await client.call_tool(block.name, block.input)
                    duration_ms = int((time.monotonic() - t_start) * 1000)

                    trace.tool_calls.append(
                        ToolCallRecord(
                            turn=turn,
                            tool_name=block.name,
                            arguments=block.input,
                            result_content=tool_result.content,
                            is_error=tool_result.is_error,
                            duration_ms=duration_ms,
                        )
                    )

                    tool_result_blocks.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": tool_result.content,
                            "is_error": tool_result.is_error,
                        }
                    )

                messages.append({"role": "user", "content": tool_result_blocks})
            else:
                # Unknown stop reason — capture any text and exit
                for block in response.content:
                    if hasattr(block, "text"):
                        trace.final_response = block.text
                        break
                break

    except Exception as exc:
        trace.error = str(exc)

    return trace


async def run_suite(
    suite: Suite,
    engine,
    anthropic_client: anthropic.AsyncAnthropic,
    model: str = "claude-haiku-4-5-20251001",
    on_case_done=None,
) -> str:
    """Run all cases in a suite, persist results, and return the run UUID."""
    # Lazy import to avoid circular dep
    from mcpgauge.judge import judge_case
    from mcpgauge.store import Judgment, save_judgment

    run_id = str(uuid.uuid4())
    run = Run(
        id=run_id,
        suite_name=suite.name,
        total_cases=len(suite.cases),
        passed_cases=0,
    )
    save_run(engine, run)

    client = MCPClient()
    if suite.transport == "stdio" and suite.server_command:
        cmd = suite.server_command[0]
        args = suite.server_command[1:]
        await client.connect_stdio(cmd, args)
    elif suite.transport == "sse" and suite.server_url:
        await client.connect_sse(suite.server_url)

    passed_count = 0

    try:
        for case in suite.cases:
            trace = await run_case(case, client, anthropic_client, model)
            verdicts = await judge_case(case, trace, anthropic_client, model)

            all_passed = all(v.passed for v in verdicts) and trace.error is None
            status = "passed" if all_passed else "failed"
            if trace.error:
                status = "error"

            if all_passed:
                passed_count += 1

            cr = CaseResult(
                run_id=run_id,
                case_id=case.id,
                status=status,
                prompt=case.prompt,
                final_response=trace.final_response,
                error=trace.error,
            )
            save_case_result(engine, cr)

            for tc in trace.tool_calls:
                save_tool_call(
                    engine,
                    ToolCall(
                        case_result_id=cr.id,
                        turn=tc.turn,
                        tool_name=tc.tool_name,
                        arguments_json=json.dumps(tc.arguments),
                        result_json=json.dumps(tc.result_content),
                        is_error=tc.is_error,
                        duration_ms=tc.duration_ms,
                    ),
                )

            for v in verdicts:
                save_judgment(
                    engine,
                    Judgment(
                        case_result_id=cr.id,
                        criterion_name=v.criterion_name,
                        passed=v.passed,
                        reasoning=v.reasoning,
                    ),
                )

            if on_case_done:
                on_case_done(case, cr, trace, verdicts)

    finally:
        await client.disconnect()

    # Update passed count on the run record
    from sqlmodel import Session

    with Session(engine) as session:
        db_run = session.get(Run, run_id)
        if db_run:
            db_run.passed_cases = passed_count
            session.add(db_run)
            session.commit()

    return run_id
