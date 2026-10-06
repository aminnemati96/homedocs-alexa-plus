"""Bridge between the MCP server's tools and Bedrock Converse tool specs."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.types import CallToolResult, TextContent, Tool


def to_converse_tool(tool: Tool) -> dict[str, Any]:
    return {
        "toolSpec": {
            "name": tool.name,
            "description": tool.description or tool.title or tool.name,
            "inputSchema": {"json": tool.inputSchema},
        }
    }


def result_to_json(result: CallToolResult) -> dict[str, Any]:
    """Converse wants a JSON object; prefer the tool's structured output."""
    if result.structuredContent is not None:
        return result.structuredContent
    text = "\n".join(c.text for c in result.content if isinstance(c, TextContent))
    return {"text": text}


class McpToolbox:
    """An open MCP session plus its tools in Converse format."""

    def __init__(self, session: ClientSession, tools: list[Tool]):
        self._session = session
        self.converse_tools = [to_converse_tool(t) for t in tools]

    async def call(self, name: str, arguments: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        """Returns (json result, is_error)."""
        result = await self._session.call_tool(name, arguments)
        return result_to_json(result), bool(result.isError)


@asynccontextmanager
async def open_toolbox(url: str) -> AsyncIterator[McpToolbox]:
    async with streamable_http_client(url) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            listed = await session.list_tools()
            yield McpToolbox(session, listed.tools)
