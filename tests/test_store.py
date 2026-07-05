"""Unit tests for store.py — uses in-memory SQLite."""

from __future__ import annotations

import pytest
from sqlmodel import Session, inspect, text

from mcpgauge.store import (
    CaseResult,
    Judgment,
    Run,
    ToolCall,
    get_engine,
    get_case_results,
    get_judgments,
    get_run,
    get_tool_calls,
    init_db,
    save_case_result,
    save_judgment,
    save_run,
    save_tool_call,
)


@pytest.fixture
def engine():
    eng = get_engine(":memory:")
    init_db(eng)
    return eng


def test_init_db_creates_tables(engine):
    """init_db should create all four tables."""
    with Session(engine) as session:
        tables = session.exec(
            text("SELECT name FROM sqlite_master WHERE type='table'")
        ).fetchall()
    table_names = {row[0] for row in tables}
    assert "runs" in table_names
    assert "case_results" in table_names
    assert "tool_calls" in table_names
    assert "judgments" in table_names


def test_save_and_retrieve_run(engine):
    run = Run(suite_name="test_suite", total_cases=3, passed_cases=2)
    save_run(engine, run)

    retrieved = get_run(engine, run.id)
    assert retrieved is not None
    assert retrieved.suite_name == "test_suite"
    assert retrieved.total_cases == 3
    assert retrieved.passed_cases == 2


def test_full_cascade(engine):
    """Save Run → CaseResult → ToolCall → Judgment and query by run_id."""
    run = Run(suite_name="cascade_suite")
    save_run(engine, run)

    cr = CaseResult(
        run_id=run.id,
        case_id="case_1",
        status="passed",
        prompt="Do something",
        final_response="Done",
    )
    save_case_result(engine, cr)

    tc = ToolCall(
        case_result_id=cr.id,
        turn=0,
        tool_name="echo",
        arguments_json='{"msg": "hello"}',
        result_json='[{"type": "text", "text": "hello"}]',
        is_error=False,
        duration_ms=42,
    )
    save_tool_call(engine, tc)

    j = Judgment(
        case_result_id=cr.id,
        criterion_name="correctness",
        passed=True,
        reasoning="The agent echoed correctly.",
    )
    save_judgment(engine, j)

    # Query back via run_id
    case_results = get_case_results(engine, run.id)
    assert len(case_results) == 1
    assert case_results[0].case_id == "case_1"

    tool_calls = get_tool_calls(engine, cr.id)
    assert len(tool_calls) == 1
    assert tool_calls[0].tool_name == "echo"
    assert tool_calls[0].duration_ms == 42

    judgments = get_judgments(engine, cr.id)
    assert len(judgments) == 1
    assert judgments[0].criterion_name == "correctness"
    assert judgments[0].passed is True


def test_get_run_missing(engine):
    assert get_run(engine, "nonexistent-id") is None


def test_multiple_cases_for_run(engine):
    run = Run(suite_name="multi_suite")
    save_run(engine, run)

    for i in range(3):
        cr = CaseResult(
            run_id=run.id,
            case_id=f"case_{i}",
            status="passed" if i < 2 else "failed",
            prompt=f"Prompt {i}",
        )
        save_case_result(engine, cr)

    cases = get_case_results(engine, run.id)
    assert len(cases) == 3
