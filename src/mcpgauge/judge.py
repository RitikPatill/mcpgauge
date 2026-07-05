"""LLM-as-judge scorer for MCPGauge."""

from __future__ import annotations

from dataclasses import dataclass

import anthropic

from mcpgauge.runner import AgentTrace
from mcpgauge.schema import Case

JUDGE_SYSTEM_PROMPT = """\
You are an impartial evaluator assessing an AI agent's performance on a test case.
You will be given:
1. The original prompt given to the agent
2. The rubric criteria to evaluate against
3. A trace of tool calls the agent made (tool name, arguments, result)
4. The agent's final response

Your job is to evaluate each criterion independently and record a pass/fail verdict
with reasoning. Be objective and base your judgments strictly on the evidence in the trace.
You MUST call the `record_judgments` tool with all verdicts.
"""

JUDGE_TOOL = {
    "name": "record_judgments",
    "description": "Record per-criterion pass/fail verdicts for the agent's performance.",
    "input_schema": {
        "type": "object",
        "properties": {
            "verdicts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "criterion_name": {"type": "string"},
                        "passed": {"type": "boolean"},
                        "reasoning": {"type": "string"},
                    },
                    "required": ["criterion_name", "passed", "reasoning"],
                },
            }
        },
        "required": ["verdicts"],
    },
}


@dataclass
class CriterionVerdict:
    criterion_name: str
    passed: bool
    reasoning: str


def _format_trace(trace: AgentTrace) -> str:
    """Format an AgentTrace into readable text for the judge prompt."""
    lines = []
    if not trace.tool_calls:
        lines.append("(No tool calls were made)")
    else:
        for i, tc in enumerate(trace.tool_calls, 1):
            lines.append(f"Tool call {i} (turn {tc.turn}):")
            lines.append(f"  Tool: {tc.tool_name}")
            lines.append(f"  Arguments: {tc.arguments}")
            lines.append(f"  Result: {tc.result_content}")
            if tc.is_error:
                lines.append("  [ERROR]")
            lines.append(f"  Duration: {tc.duration_ms}ms")
    if trace.error:
        lines.append(f"\nAgent error: {trace.error}")
    return "\n".join(lines)


def _build_judge_prompt(case: Case, trace: AgentTrace) -> str:
    criteria_text = "\n".join(
        f"- {c.name}: {c.description}" for c in case.rubric.criteria
    )
    trace_text = _format_trace(trace)

    return f"""\
## Test Case Prompt
{case.prompt}

## Rubric Criteria
{criteria_text}

## Agent Tool Call Trace
{trace_text}

## Agent Final Response
{trace.final_response or "(No final response)"}

Please evaluate each criterion and call `record_judgments` with your verdicts.
"""


async def judge_case(
    case: Case,
    trace: AgentTrace,
    anthropic_client: anthropic.AsyncAnthropic,
    model: str = "claude-haiku-4-5-20251001",
) -> list[CriterionVerdict]:
    """Score a completed trace against the rubric using an LLM judge."""
    user_prompt = _build_judge_prompt(case, trace)

    response = await anthropic_client.messages.create(
        model=model,
        max_tokens=4096,
        system=JUDGE_SYSTEM_PROMPT,
        tools=[JUDGE_TOOL],
        tool_choice={"type": "any"},
        messages=[{"role": "user", "content": user_prompt}],
    )

    # Find the record_judgments tool call in the response
    for block in response.content:
        if block.type == "tool_use" and block.name == "record_judgments":
            raw_verdicts = block.input.get("verdicts", [])
            return [
                CriterionVerdict(
                    criterion_name=v["criterion_name"],
                    passed=bool(v["passed"]),
                    reasoning=v.get("reasoning", ""),
                )
                for v in raw_verdicts
            ]

    # Fallback: return all criteria as failed if parsing fails
    return [
        CriterionVerdict(
            criterion_name=c.name,
            passed=False,
            reasoning="Judge did not return a verdict for this criterion.",
        )
        for c in case.rubric.criteria
    ]
