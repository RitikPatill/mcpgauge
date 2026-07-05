"""Unit tests for judge.py — mocks Anthropic API, no real API calls."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from mcpgauge.judge import CriterionVerdict, judge_case
from mcpgauge.runner import AgentTrace, ToolCallRecord
from mcpgauge.schema import Case, Criterion, Rubric

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TWO_CRITERIA_CASE = Case(
    id="judge_case_1",
    prompt="List files in /tmp",
    rubric=Rubric(
        criteria=[
            Criterion(name="used_list_tool", description="Called the list_files tool"),
            Criterion(name="correct_output", description="Output contains file names"),
        ]
    ),
)

ONE_CRITERION_CASE = Case(
    id="judge_case_2",
    prompt="Echo hello",
    rubric=Rubric(criteria=[Criterion(name="echoed", description="Agent echoed hello")]),
)


def _make_trace_with_tool_call():
    return AgentTrace(
        tool_calls=[
            ToolCallRecord(
                turn=0,
                tool_name="list_files",
                arguments={"path": "/tmp"},
                result_content=[{"type": "text", "text": "file1.txt\nfile2.txt"}],
                is_error=False,
                duration_ms=50,
            )
        ],
        final_response="Found: file1.txt, file2.txt",
    )


def _make_record_judgments_block(verdicts: list[dict]):
    block = MagicMock()
    block.type = "tool_use"
    block.name = "record_judgments"
    block.input = {"verdicts": verdicts}
    return block


def _make_judge_response(verdicts: list[dict]):
    resp = MagicMock()
    resp.content = [_make_record_judgments_block(verdicts)]
    return resp


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_judge_returns_verdicts():
    """Mock returns record_judgments tool call → judge_case returns correct CriterionVerdict list."""
    mock_verdicts = [
        {"criterion_name": "used_list_tool", "passed": True, "reasoning": "list_files was called"},
        {
            "criterion_name": "correct_output",
            "passed": True,
            "reasoning": "Output contains file names",
        },
    ]

    anthropic_client = AsyncMock()
    anthropic_client.messages.create.return_value = _make_judge_response(mock_verdicts)

    trace = _make_trace_with_tool_call()
    verdicts = await judge_case(TWO_CRITERIA_CASE, trace, anthropic_client)

    assert len(verdicts) == 2
    assert all(isinstance(v, CriterionVerdict) for v in verdicts)
    assert verdicts[0].criterion_name == "used_list_tool"
    assert verdicts[0].passed is True
    assert "list_files" in verdicts[0].reasoning
    assert verdicts[1].criterion_name == "correct_output"
    assert verdicts[1].passed is True


@pytest.mark.asyncio
async def test_judge_criterion_count_matches_rubric():
    """Verify returned verdicts count equals rubric criteria count when model is cooperative."""
    mock_verdicts = [
        {"criterion_name": "echoed", "passed": True, "reasoning": "Agent said hello"},
    ]

    anthropic_client = AsyncMock()
    anthropic_client.messages.create.return_value = _make_judge_response(mock_verdicts)

    trace = AgentTrace(final_response="hello")
    verdicts = await judge_case(ONE_CRITERION_CASE, trace, anthropic_client)

    # Count matches rubric criteria count
    assert len(verdicts) == len(ONE_CRITERION_CASE.rubric.criteria)
    assert verdicts[0].passed is True


@pytest.mark.asyncio
async def test_judge_fallback_when_no_tool_call():
    """If judge model doesn't call record_judgments, return all-failed fallback verdicts."""
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = "I think it passed"

    resp = MagicMock()
    resp.content = [text_block]

    anthropic_client = AsyncMock()
    anthropic_client.messages.create.return_value = resp

    trace = AgentTrace(final_response="hello")
    verdicts = await judge_case(ONE_CRITERION_CASE, trace, anthropic_client)

    # Fallback returns all criteria as failed
    assert len(verdicts) == len(ONE_CRITERION_CASE.rubric.criteria)
    assert all(not v.passed for v in verdicts)


@pytest.mark.asyncio
async def test_judge_passes_tool_choice_any():
    """Verify tool_choice={'type': 'any'} is passed to force the model to call record_judgments."""
    anthropic_client = AsyncMock()
    anthropic_client.messages.create.return_value = _make_judge_response(
        [{"criterion_name": "echoed", "passed": True, "reasoning": "ok"}]
    )

    trace = AgentTrace(final_response="hello")
    await judge_case(ONE_CRITERION_CASE, trace, anthropic_client)

    call_kwargs = anthropic_client.messages.create.call_args.kwargs
    assert call_kwargs.get("tool_choice") == {"type": "any"}
