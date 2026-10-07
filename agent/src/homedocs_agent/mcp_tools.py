"""Bridge between the MCP server's tools and Bedrock Converse tool specs."""

from __future__ import annotations

import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.types import CallToolResult, TextContent, Tool
from pydantic import AnyUrl


# Tools the model never sees; only the agent calls them (e.g. the nightly reset).
ADMIN_PREFIX = "admin_"

# The server's Agent Skill (agentskills.io format), loaded as the model's instructions.
SKILL_URI = "skill://homedocs-paperwork/SKILL.md"


def skill_body(markdown: str) -> str:
    """SKILL.md without its YAML frontmatter."""
    match = re.match(r"^---\s*\n.*?\n---\s*\n", markdown, flags=re.DOTALL)
    return (markdown[match.end():] if match else markdown).strip()


def to_converse_tool(tool: Tool, hidden_args: frozenset[str] = frozenset()) -> dict[str, Any]:
    """Converse tool spec. `hidden_args` are filled in by the agent (see McpToolbox),
    so they are removed from the schema the model sees."""
    schema = dict(tool.inputSchema)
    if hidden_args and "properties" in schema:
        schema["properties"] = {k: v for k, v in schema["properties"].items() if k not in hidden_args}
        if "required" in schema:
            schema["required"] = [r for r in schema["required"] if r not in hidden_args]
    return {
        "toolSpec": {
            "name": tool.name,
            "description": tool.description or tool.title or tool.name,
            "inputSchema": {"json": schema},
        }
    }


def result_to_json(result: CallToolResult) -> dict[str, Any]:
    """Converse wants a JSON object; prefer the tool's structured output."""
    if result.structuredContent is not None:
        return result.structuredContent
    text = "\n".join(c.text for c in result.content if isinstance(c, TextContent))
    return {"text": text}


class McpToolbox:
    """An open MCP session plus its tools in Converse format.

    `context` holds values the agent knows better than the model, such as the
    user's local date (`today`). They are injected into any tool that accepts
    them and hidden from the model's view of the schema.
    """

    def __init__(self, session: ClientSession, tools: list[Tool]):
        self._session = session
        self._params = {t.name: set(t.inputSchema.get("properties", {})) for t in tools}
        self._tools = [t for t in tools if not t.name.startswith(ADMIN_PREFIX)]
        self.context: dict[str, Any] = {}
        self.skill = ""  # the server's Agent Skill, if it publishes one

    @property
    def converse_tools(self) -> list[dict[str, Any]]:
        hidden = frozenset(self.context)
        return [to_converse_tool(t, hidden) for t in self._tools]

    async def call(self, name: str, arguments: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        """Returns (json result, is_error)."""
        accepted = self._params.get(name, set())
        arguments = {**arguments, **{k: v for k, v in self.context.items() if k in accepted}}
        result = await self._session.call_tool(name, arguments)
        return result_to_json(result), bool(result.isError)


@asynccontextmanager
async def open_toolbox(url: str, headers: dict[str, str] | None = None) -> AsyncIterator[McpToolbox]:
    # Timeouts match the SDK defaults: 30 s to connect/send, 5 min for streamed reads.
    http = httpx.AsyncClient(headers=headers, timeout=httpx.Timeout(30, read=300))
    # terminate_on_close=False: don't send a DELETE when done. AgentCore answers it
    # with 404, and we want to keep reusing the same warm session anyway.
    async with http, streamable_http_client(url, http_client=http, terminate_on_close=False) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            listed = await session.list_tools()
            toolbox = McpToolbox(session, listed.tools)
            try:
                result = await session.read_resource(AnyUrl(SKILL_URI))
                toolbox.skill = skill_body("".join(getattr(c, "text", "") for c in result.contents))
            except Exception:  # an older server without the skill still works
                pass
            yield toolbox
