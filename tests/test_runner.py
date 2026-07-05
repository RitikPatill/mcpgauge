"""Unit tests for runner.py — mocks Anthropic API, no real API calls."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcpgauge.runner import AgentTrace, ToolCallRecord, _mcp_tools_to_anthropic, run_case
from mcpgauge.schema import Case, Criterion, Rubric

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SIMPLE_CASE = Case(
    id="case_simple",
    prompt="Say hello",
    rubric=Rubric(criteria=[Criterion(name="greeting", description="Says hello")]),
    max_turns=5,
)

ONE_TOOL_CASE = Case(
    id="case_tool",
    prompt="Echo 'hello' using the echo tool",
    rubric=Rubric(criteria=[Criterion(name="used_echo", description="Called echo tool")]),
    max_turns=5,
)

MAX_TURNS_CASE = Case(
    id="case_loops",
    prompt="Keep calling tools",
    rubric=Rubric(criteria=[Criterion(name="stopped", description="Did not loop forever")]),
    max_turns=3,
)


def _make_text_block(text: str):
    block = MagicMock()
    block.type = "text"
    block.text = text
    return block


def _make_tool_use_block(tool_id: str, name: str, input_: dict):
    block = MagicMock()
    block.type = "tool_use"
    block.id = tool_id
    block.name = name
    block.input = input_
    return block


def _make_response(stop_reason: str, content: list):
    resp = MagicMock()
    resp.stop_reason = stop_reason
    resp.content = content
    return resp


def _make_mcp_client(tool_result_content=None, is_error=False):
    """Return a mock MCPClient."""
    from mcpgauge.client import ToolResult

    client = AsyncMock()
    client.list_tools.return_value = []  # No tools by default

    result = ToolResult(
        content=tool_result_content or [{"type": "text", "text": "echoed"}],
        is_error=is_error,
    )
    client.call_tool.return_value = result
    return client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_case_no_tools():
    """Agent returns end_turn immediately → empty tool_calls, final_response set."""
    anthropic_client = AsyncMock()
    anthropic_client.messages.create.return_value = _make_response(
        "end_turn", [_make_text_block("Hello there!")]
    )

    client = _make_mcp_client()
    trace = await run_case(SIMPLE_CASE, client, anthropic_client)

    assert isinstance(trace, AgentTrace)
    assert trace.tool_calls == []
    assert trace.final_response == "Hello there!"
    assert trace.error is None


@pytest.mark.asyncio
async def test_run_case_one_tool_call():
    """Agent makes one tool call then ends → one ToolCallRecord with correct fields."""
    tool_block = _make_tool_use_block("tu_1", "echo", {"msg": "hello"})
    first_response = _make_response("tool_use", [tool_block])
    second_response = _make_response("end_turn", [_make_text_block("Done")])

    anthropic_client = AsyncMock()
    anthropic_client.messages.create.side_effect = [first_response, second_response]

    # Client with real echo tool listed
    from unittest.mock import MagicMock as MM
    from mcpgauge.client import ToolResult

    mock_tool = MM()
    mock_tool.name = "echo"
    mock_tool.description = "Echo a message"
    mock_tool.inputSchema = {"type": "object", "properties": {"msg": {"type": "string"}}}

    client = AsyncMock()
    client.list_tools.return_value = [mock_tool]
    client.call_tool.return_value = ToolResult(
        content=[{"type": "text", "text": "hello"}], is_error=False
    )

    trace = await run_case(ONE_TOOL_CASE, client, anthropic_client)

    assert len(trace.tool_calls) == 1
    tc = trace.tool_calls[0]
    assert tc.tool_name == "echo"
    assert tc.arguments == {"msg": "hello"}
    assert tc.is_error is False
    assert tc.duration_ms >= 0
    assert trace.final_response == "Done"
    assert trace.error is None

    # Verify call_tool was called with correct args
    client.call_tool.assert_awaited_once_with("echo", {"msg": "hello"})


@pytest.mark.asyncio
async def test_run_case_max_turns_respected():
    """Agent always returns tool_use → loop stops at case.max_turns, no infinite loop."""
    tool_block = _make_tool_use_block("tu_loop", "echo", {"msg": "again"})
    always_tool_response = _make_response("tool_use", [tool_block])

    from mcpgauge.client import ToolResult

    anthropic_client = AsyncMock()
    # Always return tool_use — loop must stop at max_turns
    anthropic_client.messages.create.return_value = always_tool_response

    client = AsyncMock()
    client.list_tools.return_value = []
    client.call_tool.return_value = ToolResult(
        content=[{"type": "text", "text": "ok"}], is_error=False
    )

    trace = await run_case(MAX_TURNS_CASE, client, anthropic_client)

    # Must have stopped at max_turns=3, no infinite loop
    assert anthropic_client.messages.create.call_count == MAX_TURNS_CASE.max_turns
    assert len(trace.tool_calls) == MAX_TURNS_CASE.max_turns


def test_mcp_tools_to_anthropic():
    """_mcp_tools_to_anthropic converts MCP tool list to Anthropic format."""
    tool = MagicMock()
    tool.name = "my_tool"
    tool.description = "Does stuff"
    tool.inputSchema = {"type": "object", "properties": {}}

    result = _mcp_tools_to_anthropic([tool])

    assert len(result) == 1
    assert result[0]["name"] == "my_tool"
    assert result[0]["description"] == "Does stuff"
    assert result[0]["input_schema"] == {"type": "object", "properties": {}}
