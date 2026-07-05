"""Thin async wrapper around the MCP Python SDK."""

from __future__ import annotations

from contextlib import AsyncExitStack
from dataclasses import dataclass, field

import mcp.types as types
from mcp import ClientSession
from mcp.client.sse import sse_client
from mcp.client.stdio import StdioServerParameters, stdio_client


@dataclass
class ToolResult:
    content: list[dict]
    is_error: bool


class MCPClient:
    """Async client for a single MCP server (stdio or SSE transport).

    Use as an async context manager or call ``connect_stdio``/``connect_sse``
    manually and ``disconnect`` when done.
    """

    def __init__(self) -> None:
        self._session: ClientSession | None = None
        self._exit_stack: AsyncExitStack = field(default_factory=AsyncExitStack)  # type: ignore[assignment]
        self._exit_stack = AsyncExitStack()

    # ------------------------------------------------------------------
    # Connection helpers
    # ------------------------------------------------------------------

    async def connect_stdio(self, command: str, args: list[str]) -> None:
        """Spawn *command* with *args* and connect over stdio."""
        params = StdioServerParameters(command=command, args=args)
        read, write = await self._exit_stack.enter_async_context(stdio_client(params))
        session = ClientSession(read, write)
        self._session = await self._exit_stack.enter_async_context(session)
        await self._session.initialize()

    async def connect_sse(self, url: str) -> None:
        """Connect to an already-running SSE MCP server at *url*."""
        read, write = await self._exit_stack.enter_async_context(sse_client(url))
        session = ClientSession(read, write)
        self._session = await self._exit_stack.enter_async_context(session)
        await self._session.initialize()

    async def disconnect(self) -> None:
        """Close transport and session."""
        await self._exit_stack.aclose()
        self._session = None

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    async def list_tools(self) -> list[types.Tool]:
        assert self._session is not None, "Not connected — call connect_stdio or connect_sse first"
        result = await self._session.list_tools()
        return result.tools

    async def list_resources(self) -> list[types.Resource]:
        assert self._session is not None, "Not connected"
        result = await self._session.list_resources()
        return result.resources

    async def list_prompts(self) -> list[types.Prompt]:
        assert self._session is not None, "Not connected"
        result = await self._session.list_prompts()
        return result.prompts

    # ------------------------------------------------------------------
    # Tool invocation
    # ------------------------------------------------------------------

    async def call_tool(self, name: str, arguments: dict) -> ToolResult:
        """Call *name* with *arguments* and return a normalised :class:`ToolResult`."""
        assert self._session is not None, "Not connected"
        raw = await self._session.call_tool(name, arguments)
        content = [
            {"type": item.type, "text": getattr(item, "text", None)}
            for item in raw.content
        ]
        return ToolResult(content=content, is_error=bool(raw.isError))

    # ------------------------------------------------------------------
    # Async context manager
    # ------------------------------------------------------------------

    async def __aenter__(self) -> MCPClient:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.disconnect()
