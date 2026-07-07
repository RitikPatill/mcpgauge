"""Tests for the FastAPI dashboard endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from mcpgauge.app import create_app
from mcpgauge.store import (
    CaseResult,
    Judgment,
    Run,
    ToolCall,
    get_engine,
    init_db,
    save_case_result,
    save_judgment,
    save_run,
    save_tool_call,
)

# ---------------------------------------------------------------------------
# Module-scoped fixture: one in-memory DB shared by all tests in this module
# ---------------------------------------------------------------------------

_RUN_ID = "aaaaaaaa-0000-0000-0000-000000000001"
_CASE_ID = "bbbbbbbb-0000-0000-0000-000000000002"
_TOOL_ID = "cccccccc-0000-0000-0000-000000000003"
_JUDGMENT_ID = "dddddddd-0000-0000-0000-000000000004"
_CRITERION = "Uses correct tool"


@pytest.fixture(scope="module")
def client():
    engine = get_engine(":memory:")
    init_db(engine)

    run = Run(
        id=_RUN_ID,
        suite_name="test_suite",
        total_cases=1,
        passed_cases=1,
    )
    save_run(engine, run)

    cr = CaseResult(
        id=_CASE_ID,
        run_id=_RUN_ID,
        case_id="case_001",
        status="passed",
        prompt="List files in /tmp",
        final_response="Here are the files: a.txt, b.txt",
        error=None,
    )
    save_case_result(engine, cr)

    tc = ToolCall(
        id=_TOOL_ID,
        case_result_id=_CASE_ID,
        turn=0,
        tool_name="list_directory",
        arguments_json='{"path": "/tmp"}',
        result_json='[{"type": "text", "text": "a.txt\\nb.txt"}]',
        is_error=False,
        duration_ms=42,
    )
    save_tool_call(engine, tc)

    jud = Judgment(
        id=_JUDGMENT_ID,
        case_result_id=_CASE_ID,
        criterion_name=_CRITERION,
        passed=True,
        reasoning="The agent called list_directory with the correct path.",
    )
    save_judgment(engine, jud)

    app = create_app(db_path=":memory:", engine=engine)
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_list_runs_empty():
    """Fresh in-memory DB returns an empty list."""
    engine = get_engine(":memory:")
    init_db(engine)
    app = create_app(db_path=":memory:", engine=engine)
    with TestClient(app) as c:
        resp = c.get("/api/runs")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_runs_one(client):
    resp = client.get("/api/runs")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["id"] == _RUN_ID
    assert data[0]["suite_name"] == "test_suite"
    assert data[0]["total_cases"] == 1
    assert data[0]["passed_cases"] == 1


def test_get_run_ok(client):
    resp = client.get(f"/api/runs/{_RUN_ID}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == _RUN_ID
    assert "cases" in data
    assert len(data["cases"]) == 1
    assert data["cases"][0]["id"] == _CASE_ID


def test_get_run_not_found(client):
    resp = client.get("/api/runs/nonexistent-run-id")
    assert resp.status_code == 404


def test_get_case_ok(client):
    resp = client.get(f"/api/runs/{_RUN_ID}/cases/{_CASE_ID}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == _CASE_ID
    assert len(data["tool_calls"]) == 1
    assert data["tool_calls"][0]["tool_name"] == "list_directory"
    assert len(data["judgments"]) == 1
    assert data["judgments"][0]["criterion_name"] == _CRITERION


def test_runs_page_200(client):
    resp = client.get("/runs")
    assert resp.status_code == 200
    assert "MCPGauge" in resp.text


def test_run_detail_page_200(client):
    resp = client.get(f"/runs/{_RUN_ID}")
    assert resp.status_code == 200
    assert "test_suite" in resp.text


def test_case_detail_page_200(client):
    resp = client.get(f"/runs/{_RUN_ID}/cases/{_CASE_ID}")
    assert resp.status_code == 200
    assert _CRITERION in resp.text


def test_root_redirects(client):
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code == 307
    assert resp.headers["location"] == "/runs"


def test_connect_bad_transport(client):
    resp = client.post("/api/connect", json={"transport": "stdio"})
    assert resp.status_code == 422


def test_api_diff_endpoint():
    """GET /api/runs/{a}/diff/{b} returns expected JSON shape."""
    engine = get_engine(":memory:")
    init_db(engine)

    run_a = Run(suite_name="test_suite", total_cases=1, passed_cases=1)
    run_b = Run(suite_name="test_suite", total_cases=1, passed_cases=0)
    save_run(engine, run_a)
    save_run(engine, run_b)

    cr_a = CaseResult(
        run_id=run_a.id,
        case_id="case_001",
        status="passed",
        prompt="Do something",
    )
    cr_b = CaseResult(
        run_id=run_b.id,
        case_id="case_001",
        status="failed",
        prompt="Do something",
    )
    save_case_result(engine, cr_a)
    save_case_result(engine, cr_b)

    save_judgment(engine, Judgment(case_result_id=cr_a.id, criterion_name="correctness", passed=True, reasoning="ok"))
    save_judgment(engine, Judgment(case_result_id=cr_b.id, criterion_name="correctness", passed=False, reasoning="nope"))

    app = create_app(db_path=":memory:", engine=engine)
    with TestClient(app) as c:
        resp = c.get(f"/api/runs/{run_a.id}/diff/{run_b.id}")

    assert resp.status_code == 200
    data = resp.json()
    assert data["regressions"] == 1
    assert data["fixes"] == 0
    assert len(data["cases"]) == 1
    assert data["cases"][0]["change"] == "regression"
    assert data["cases"][0]["criteria"][0]["criterion_name"] == "correctness"
    assert data["cases"][0]["criteria"][0]["changed"] is True


def test_api_diff_not_found(client):
    resp = client.get(f"/api/runs/{_RUN_ID}/diff/nonexistent-id")
    assert resp.status_code == 404
