"""Unit tests for diff.py — uses in-memory SQLite."""

from __future__ import annotations

import pytest

from mcpgauge.diff import compute_diff
from mcpgauge.store import (
    CaseResult,
    Judgment,
    Run,
    get_engine,
    init_db,
    save_case_result,
    save_judgment,
    save_run,
)


@pytest.fixture
def engine():
    eng = get_engine(":memory:")
    init_db(eng)
    return eng


def _make_run(engine, suite_name: str = "test_suite") -> Run:
    run = Run(suite_name=suite_name)
    save_run(engine, run)
    return run


def _make_case(engine, run_id: str, case_id: str, status: str) -> CaseResult:
    cr = CaseResult(
        run_id=run_id,
        case_id=case_id,
        status=status,
        prompt="test prompt",
        final_response="response",
    )
    save_case_result(engine, cr)
    return cr


def _make_judgment(engine, case_result_id: str, criterion: str, passed: bool) -> Judgment:
    j = Judgment(
        case_result_id=case_result_id,
        criterion_name=criterion,
        passed=passed,
        reasoning="test reasoning",
    )
    save_judgment(engine, j)
    return j


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_compute_diff_regression(engine):
    run_a = _make_run(engine)
    run_b = _make_run(engine)
    _make_case(engine, run_a.id, "case_1", "passed")
    _make_case(engine, run_b.id, "case_1", "failed")

    d = compute_diff(engine, run_a.id, run_b.id)

    assert d.regressions == 1
    assert d.fixes == 0
    assert d.unchanged == 0
    assert len(d.cases) == 1
    assert d.cases[0].change == "regression"
    assert d.cases[0].status_a == "passed"
    assert d.cases[0].status_b == "failed"


def test_compute_diff_fix(engine):
    run_a = _make_run(engine)
    run_b = _make_run(engine)
    _make_case(engine, run_a.id, "case_1", "failed")
    _make_case(engine, run_b.id, "case_1", "passed")

    d = compute_diff(engine, run_a.id, run_b.id)

    assert d.fixes == 1
    assert d.regressions == 0
    assert d.cases[0].change == "fix"


def test_compute_diff_same(engine):
    run_a = _make_run(engine)
    run_b = _make_run(engine)
    _make_case(engine, run_a.id, "case_1", "passed")
    _make_case(engine, run_b.id, "case_1", "passed")

    d = compute_diff(engine, run_a.id, run_b.id)

    assert d.unchanged == 1
    assert d.regressions == 0
    assert d.fixes == 0
    assert d.cases[0].change == "same"


def test_compute_diff_missing_case(engine):
    """Case in A but not in B → status_b='missing', change='regression'."""
    run_a = _make_run(engine)
    run_b = _make_run(engine)
    _make_case(engine, run_a.id, "case_x", "passed")
    # run_b has no case_x

    d = compute_diff(engine, run_a.id, run_b.id)

    assert len(d.cases) == 1
    assert d.cases[0].status_b == "missing"
    assert d.cases[0].change == "regression"
    assert d.regressions == 1


def test_compute_diff_new_case(engine):
    """Case in B but not in A → status_a='missing', change='new'."""
    run_a = _make_run(engine)
    run_b = _make_run(engine)
    _make_case(engine, run_b.id, "case_new", "passed")

    d = compute_diff(engine, run_a.id, run_b.id)

    assert len(d.cases) == 1
    assert d.cases[0].status_a == "missing"
    assert d.cases[0].change == "new"


def test_compute_diff_invalid_run(engine):
    """Non-existent run ID raises ValueError."""
    run_a = _make_run(engine)
    with pytest.raises(ValueError, match="Run not found"):
        compute_diff(engine, run_a.id, "nonexistent-id")

    with pytest.raises(ValueError, match="Run not found"):
        compute_diff(engine, "nonexistent-id", run_a.id)


def test_criterion_diff(engine):
    """Differing judgments produce CriterionDiff.changed=True."""
    run_a = _make_run(engine)
    run_b = _make_run(engine)
    cr_a = _make_case(engine, run_a.id, "case_1", "passed")
    cr_b = _make_case(engine, run_b.id, "case_1", "failed")

    _make_judgment(engine, cr_a.id, "correctness", True)
    _make_judgment(engine, cr_b.id, "correctness", False)
    _make_judgment(engine, cr_a.id, "format", True)
    _make_judgment(engine, cr_b.id, "format", True)

    d = compute_diff(engine, run_a.id, run_b.id)

    assert len(d.cases) == 1
    case_diff = d.cases[0]
    assert len(case_diff.criteria) == 2

    by_name = {cr.criterion_name: cr for cr in case_diff.criteria}
    assert by_name["correctness"].changed is True
    assert by_name["correctness"].passed_a is True
    assert by_name["correctness"].passed_b is False
    assert by_name["format"].changed is False


def test_compute_diff_regression_error_status(engine):
    """pass→error is also a regression."""
    run_a = _make_run(engine)
    run_b = _make_run(engine)
    _make_case(engine, run_a.id, "case_1", "passed")
    _make_case(engine, run_b.id, "case_1", "error")

    d = compute_diff(engine, run_a.id, run_b.id)

    assert d.regressions == 1
    assert d.cases[0].change == "regression"
