"""Pure-Python diff logic for comparing two MCPGauge runs."""

from __future__ import annotations

from dataclasses import dataclass, field

from mcpgauge.store import CaseResult, Run, get_case_results, get_judgments, get_run


@dataclass
class CriterionDiff:
    criterion_name: str
    passed_a: bool | None  # None = criterion absent in that run
    passed_b: bool | None
    changed: bool  # True when passed_a != passed_b


@dataclass
class CaseDiff:
    case_id: str
    status_a: str  # "passed" | "failed" | "error" | "missing"
    status_b: str
    change: str  # "regression" | "fix" | "same" | "new"
    criteria: list[CriterionDiff] = field(default_factory=list)


@dataclass
class RunDiff:
    run_a: Run
    run_b: Run
    cases: list[CaseDiff]
    regressions: int
    fixes: int
    unchanged: int


def compute_diff(engine, run_id_a: str, run_id_b: str) -> RunDiff:
    """Compare two stored runs and return a RunDiff.

    Raises ValueError if either run_id is not found.
    """
    run_a = get_run(engine, run_id_a)
    if run_a is None:
        raise ValueError(f"Run not found: {run_id_a}")

    run_b = get_run(engine, run_id_b)
    if run_b is None:
        raise ValueError(f"Run not found: {run_id_b}")

    cases_a: dict[str, CaseResult] = {
        cr.case_id: cr for cr in get_case_results(engine, run_id_a)
    }
    cases_b: dict[str, CaseResult] = {
        cr.case_id: cr for cr in get_case_results(engine, run_id_b)
    }

    all_case_ids = sorted(set(cases_a) | set(cases_b))

    case_diffs: list[CaseDiff] = []
    regressions = 0
    fixes = 0
    unchanged = 0

    for case_id in all_case_ids:
        cr_a = cases_a.get(case_id)
        cr_b = cases_b.get(case_id)

        status_a = cr_a.status if cr_a is not None else "missing"
        status_b = cr_b.status if cr_b is not None else "missing"

        if status_a == "missing":
            # Case only exists in run B
            change = "new"
        elif status_a == "passed" and status_b in {"failed", "error", "missing"}:
            change = "regression"
            regressions += 1
        elif status_a in {"failed", "error"} and status_b == "passed":
            change = "fix"
            fixes += 1
        else:
            change = "same"
            unchanged += 1

        # Build criterion diffs
        judgments_a = (
            {j.criterion_name: j.passed for j in get_judgments(engine, cr_a.id)}
            if cr_a is not None
            else {}
        )
        judgments_b = (
            {j.criterion_name: j.passed for j in get_judgments(engine, cr_b.id)}
            if cr_b is not None
            else {}
        )

        all_criteria = sorted(set(judgments_a) | set(judgments_b))
        criteria: list[CriterionDiff] = []
        for cname in all_criteria:
            pa = judgments_a.get(cname)
            pb = judgments_b.get(cname)
            criteria.append(
                CriterionDiff(
                    criterion_name=cname,
                    passed_a=pa,
                    passed_b=pb,
                    changed=(pa != pb),
                )
            )

        case_diffs.append(
            CaseDiff(
                case_id=case_id,
                status_a=status_a,
                status_b=status_b,
                change=change,
                criteria=criteria,
            )
        )

    return RunDiff(
        run_a=run_a,
        run_b=run_b,
        cases=case_diffs,
        regressions=regressions,
        fixes=fixes,
        unchanged=unchanged,
    )
