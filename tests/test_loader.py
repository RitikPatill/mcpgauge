from pathlib import Path

import pytest

from mcpgauge.loader import SuiteLoadError, load_suite

EXAMPLES = Path(__file__).parent.parent / "examples"


def test_load_filesystem_basic():
    suite = load_suite(EXAMPLES / "filesystem_basic.yaml")
    assert suite.name == "filesystem_basic"
    assert len(suite.cases) == 2


def test_load_sqlite_basic():
    suite = load_suite(EXAMPLES / "sqlite_basic.yaml")
    assert suite.name == "sqlite_basic"
    assert len(suite.cases) == 2


def test_file_not_found():
    with pytest.raises(SuiteLoadError) as exc_info:
        load_suite("/nonexistent/path/suite.yaml")
    assert "suite.yaml" in str(exc_info.value)


def test_invalid_yaml(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("key: [unclosed")
    with pytest.raises(SuiteLoadError) as exc_info:
        load_suite(bad)
    assert "bad.yaml" in str(exc_info.value)


def test_not_a_mapping(tmp_path):
    lst = tmp_path / "list.yaml"
    lst.write_text("- item1\n- item2\n")
    with pytest.raises(SuiteLoadError) as exc_info:
        load_suite(lst)
    assert "mapping" in str(exc_info.value)


def test_missing_required_field(tmp_path):
    f = tmp_path / "suite.yaml"
    f.write_text(
        "transport: stdio\n"
        "server_command: [echo, hi]\n"
        "cases:\n"
        "  - id: c1\n"
        "    prompt: hello\n"
        "    rubric:\n"
        "      criteria:\n"
        "        - name: x\n"
        "          description: y\n"
    )
    with pytest.raises(SuiteLoadError) as exc_info:
        load_suite(f)
    assert "name" in str(exc_info.value)


def test_bad_transport_value(tmp_path):
    f = tmp_path / "suite.yaml"
    f.write_text(
        "name: test\n"
        "transport: grpc\n"
        "server_command: [echo, hi]\n"
        "cases:\n"
        "  - id: c1\n"
        "    prompt: hello\n"
        "    rubric:\n"
        "      criteria:\n"
        "        - name: x\n"
        "          description: y\n"
    )
    with pytest.raises(SuiteLoadError):
        load_suite(f)


def test_error_contains_field_path(tmp_path):
    f = tmp_path / "suite.yaml"
    # rubric with no criteria key → validation error inside cases -> 0 -> rubric
    f.write_text(
        "name: test\n"
        "transport: stdio\n"
        "server_command: [echo, hi]\n"
        "cases:\n"
        "  - id: c1\n"
        "    prompt: hello\n"
        "    rubric: {}\n"
    )
    with pytest.raises(SuiteLoadError) as exc_info:
        load_suite(f)
    assert "cases -> 0" in str(exc_info.value)
