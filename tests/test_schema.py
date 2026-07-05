import pytest
from pydantic import ValidationError

from mcpgauge.schema import Case, Criterion, Rubric, Suite


def _minimal_suite_dict(**overrides) -> dict:
    base = {
        "name": "test_suite",
        "transport": "stdio",
        "server_command": ["echo", "hello"],
        "cases": [
            {
                "id": "case1",
                "prompt": "Do something.",
                "rubric": {
                    "criteria": [
                        {"name": "works", "description": "It works."}
                    ]
                },
            }
        ],
    }
    base.update(overrides)
    return base


def test_criterion_defaults():
    c = Criterion(name="foo", description="bar")
    assert c.required is True


def test_case_defaults():
    case = Case(
        id="c1",
        prompt="hello",
        rubric=Rubric(criteria=[Criterion(name="x", description="y")]),
    )
    assert case.expected_tools == []
    assert case.golden_output is None
    assert case.max_turns == 10


def test_suite_stdio_requires_server_command():
    data = _minimal_suite_dict()
    del data["server_command"]
    with pytest.raises(ValidationError):
        Suite.model_validate(data)


def test_suite_sse_requires_server_url():
    data = _minimal_suite_dict(transport="sse", server_command=None)
    with pytest.raises(ValidationError):
        Suite.model_validate(data)


def test_suite_cases_nonempty():
    data = _minimal_suite_dict(cases=[])
    with pytest.raises(ValidationError):
        Suite.model_validate(data)


def test_max_turns_bounds():
    base_case = {
        "id": "c",
        "prompt": "p",
        "rubric": {"criteria": [{"name": "n", "description": "d"}]},
    }
    with pytest.raises(ValidationError):
        Case.model_validate({**base_case, "max_turns": 0})
    with pytest.raises(ValidationError):
        Case.model_validate({**base_case, "max_turns": 51})


def test_full_roundtrip():
    data = _minimal_suite_dict()
    suite = Suite.model_validate(data)
    assert suite.name == "test_suite"
    assert suite.transport == "stdio"
    assert len(suite.cases) == 1
    assert suite.cases[0].id == "case1"
    assert suite.cases[0].rubric.criteria[0].name == "works"
