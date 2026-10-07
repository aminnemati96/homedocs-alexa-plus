"""Ask one question from the terminal and print each step. Handy for testing."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from botocore.exceptions import BotoCoreError, ClientError

from homedocs_agent import aws, config
from homedocs_agent.agent import run_turn
from homedocs_agent.connection import open_mcp


async def ask(question: str) -> None:
    async with open_mcp() as toolbox:
        async for event in run_turn(aws.bedrock().converse, config.MODEL_ID, toolbox, [], question):
            if event["type"] == "tool_call":
                print(f"-> {event['name']}({json.dumps(event['input'])})")
            elif event["type"] == "tool_result":
                print(f"<- {event['name']} in {event['ms']} ms")
            else:
                print(f"\n{event['text']}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Ask the homedocs assistant a question.")
    parser.add_argument("question")
    args = parser.parse_args()
    # The MCP client runs inside task groups, so AWS errors arrive wrapped in
    # ExceptionGroups; except* unwraps them.
    # (`return` is not allowed inside except*, hence the variable.)
    exit_code = 0
    try:
        asyncio.run(ask(args.question))
    except* (ClientError, BotoCoreError) as group:
        for e in group.exceptions:
            print(f"AWS error: {e}", file=sys.stderr)
        exit_code = 1
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
