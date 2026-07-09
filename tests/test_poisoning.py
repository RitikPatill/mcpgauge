"""Tests for the M7 poisoning security suite.

Unit test: suite YAML parses cleanly.
Integration tests: poisoning_server subprocess exposes correct tools and
embeds injection payloads in results.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from mcpgauge.client import MCPClient
from mcpgauge.loader import load_suite

EXAMPLES = Path(__file__).parent.parent / "examples"
POISONING_SERVER = EXAMPLES / "servers" / "poisoning_server.py"

pytestmark = pytest.mark.anyio


# ---------------------------------------------------------------------------
# Unit test
# ---------------------------------------------------------------------------


def test_poisoning_suite_loads():
    suite = load_suite(EXAMPLES / "poisoning.yaml")
    assert suite.name == "poisoning"
    assert len(suite.cases) == 3

    # Collect all criterion names across cases
    all_criteria = {
        c.name
        for case in suite.cases
        for c in case.rubric.criteria
    }
    assert "no_forbidden_tool_called" in all_criteria
    assert "injection_not_followed" in all_criteria
    assert "secret_not_in_response" in all_criteria

    # Security-critical criteria must be required=True
    for case in suite.cases:
        for criterion in case.rubric.criteria:
            if criterion.name in ("no_forbidden_tool_called", "injection_not_followed", "secret_not_in_response"):
                assert criterion.required is True, (
                    f"Criterion '{criterion.name}' in case '{case.id}' must be required=True"
                )


# ---------------------------------------------------------------------------
# Integration tests (real subprocess)
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_poisoning_server_lists_tools():
    """Server must advertise all three tools."""
    async with MCPClient() as client:
        await client.connect_stdio(sys.executable, [str(POISONING_SERVER)])
        tools = await client.list_tools()
        names = [t.name for t in tools]
        assert "read_note" in names
        assert "search_knowledge_base" in names
        assert "exfiltrate_data" in names


@pytest.mark.integration
async def test_poisoning_server_injects_payload():
    """read_note result must contain the injection payload and the secret."""
    async with MCPClient() as client:
        await client.connect_stdio(sys.executable, [str(POISONING_SERVER)])
        result = await client.call_tool("read_note", {"name": "test"})
        text = " ".join(
            block.get("text", "") for block in result.content
        )
        assert "SYSTEM OVERRIDE" in text
        assert "FLAG{mcp_poison_demo}" in text
