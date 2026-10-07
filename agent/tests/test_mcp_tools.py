"""How the agent presents MCP tools to the model and calls them."""

import asyncio

from mcp.types import CallToolResult, Tool

from homedocs_agent.mcp_tools import McpToolbox

TOOLS = [
    Tool(
        name="list_upcoming_dates",
        description="Upcoming dates",
        inputSchema={
            "type": "object",
            "properties": {"days_ahead": {"type": "integer"}, "today": {"type": "string"}},
        },
    ),
    Tool(name="admin_reset_demo", description="Reset", inputSchema={"type": "object", "properties": {}}),
]


class FakeSession:
    def __init__(self):
        self.calls = []

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        return CallToolResult(content=[], structuredContent={"result": []})


def test_admin_tools_are_hidden_and_user_date_is_injected():
    session = FakeSession()
    toolbox = McpToolbox(session, TOOLS)
    toolbox.context["today"] = "2026-10-15"

    specs = toolbox.converse_tools
    assert [s["toolSpec"]["name"] for s in specs] == ["list_upcoming_dates"]
    assert "today" not in specs[0]["toolSpec"]["inputSchema"]["json"]["properties"]

    # Even if the model passes its own date, the browser's date wins.
    asyncio.run(toolbox.call("list_upcoming_dates", {"days_ahead": 14, "today": "2026-10-16"}))
    assert session.calls == [("list_upcoming_dates", {"days_ahead": 14, "today": "2026-10-15"})]
