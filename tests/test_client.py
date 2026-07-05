"""Tests for MCPClient.

Unit tests: spawn the Python echo_server helper (no Node.js required).
Integration tests: spawn the reference filesystem MCP server via npx
(skipped automatically when npx is not on PATH).
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

from mcpgauge.client import MCPClient, ToolResult

HELPERS_DIR = Path(__file__).parent / "helpers"
ECHO_SERVER = HELPERS_DIR / "echo_server.py"


# ---------------------------------------------------------------------------
# Fixture: echo server (Python subprocess — no Node.js required)
# ---------------------------------------------------------------------------


@pytest.fixture
async def echo_client():
    """MCPClient connected to the in-repo echo_server helper."""
    async with MCPClient() as client:
        await client.connect_stdio(sys.executable, [str(ECHO_SERVER)])
        yield client


# ---------------------------------------------------------------------------
# Unit tests (Python subprocess only)
# ---------------------------------------------------------------------------


class TestListToolsUnit:
    async def test_list_tools_returns_echo(self, echo_client: MCPClient) -> None:
        tools = await echo_client.list_tools()
        names = [t.name for t in tools]
        assert "echo" in names

    async def test_list_tools_includes_fail_tool(self, echo_client: MCPClient) -> None:
        tools = await echo_client.list_tools()
        names = [t.name for t in tools]
        assert "fail" in names


class TestCallToolUnit:
    async def test_call_echo_returns_content(self, echo_client: MCPClient) -> None:
        result = await echo_client.call_tool("echo", {"msg": "hi"})
        assert isinstance(result, ToolResult)
        assert result.is_error is False
        texts = [block.get("text", "") for block in result.content]
        assert any("hi" in (t or "") for t in texts)

    async def test_call_tool_error_sets_is_error(self, echo_client: MCPClient) -> None:
        result = await echo_client.call_tool("fail", {"reason": "test"})
        assert isinstance(result, ToolResult)
        assert result.is_error is True

    async def test_tool_result_content_is_normalized(self, echo_client: MCPClient) -> None:
        result = await echo_client.call_tool("echo", {"msg": "normalize-me"})
        for block in result.content:
            assert "type" in block
            assert "text" in block


# ---------------------------------------------------------------------------
# Integration tests (require npx / Node.js)
# ---------------------------------------------------------------------------

_NPX = shutil.which("npx")

pytestmark_integration = pytest.mark.skipif(
    _NPX is None,
    reason="npx not found — skipping filesystem MCP integration tests",
)


@pytest.fixture
async def filesystem_client(tmp_path):
    """MCPClient connected to the reference @modelcontextprotocol/server-filesystem."""
    if _NPX is None:
        pytest.skip("npx not found")
    async with MCPClient() as client:
        await client.connect_stdio(
            _NPX,
            ["-y", "@modelcontextprotocol/server-filesystem", str(tmp_path)],
        )
        yield client


@pytest.mark.skipif(_NPX is None, reason="npx not found")
class TestFilesystemIntegration:
    async def test_list_tools_includes_read_file(
        self, filesystem_client: MCPClient
    ) -> None:
        tools = await filesystem_client.list_tools()
        names = [t.name for t in tools]
        assert "read_file" in names

    async def test_list_directory_succeeds(
        self, filesystem_client: MCPClient, tmp_path
    ) -> None:
        result = await filesystem_client.call_tool(
            "list_directory", {"path": str(tmp_path)}
        )
        assert isinstance(result, ToolResult)
        assert result.is_error is False
