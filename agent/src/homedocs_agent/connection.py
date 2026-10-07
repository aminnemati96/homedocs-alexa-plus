"""Open an MCP session to whichever server the settings point at.

Local server: plain HTTP, no headers.
AgentCore-hosted server: a Cognito bearer token, plus a fixed Mcp-Session-Id so
consecutive questions reuse one warm AgentCore session instead of starting a
new one (and paying a cold start) every time.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from homedocs_agent import config
from homedocs_agent.mcp_auth import CognitoTokens
from homedocs_agent.mcp_tools import McpToolbox, open_toolbox

def _client_secret() -> str:
    if config.COGNITO_CLIENT_SECRET or not config.COGNITO_CLIENT_SECRET_ARN:
        return config.COGNITO_CLIENT_SECRET
    import boto3

    secrets = boto3.client("secretsmanager", region_name=config.AWS_REGION)
    return secrets.get_secret_value(SecretId=config.COGNITO_CLIENT_SECRET_ARN)["SecretString"]


_tokens = (
    CognitoTokens(
        config.COGNITO_TOKEN_URL,
        config.COGNITO_CLIENT_ID,
        _client_secret(),
        config.COGNITO_SCOPE,
    )
    if config.COGNITO_CLIENT_ID
    else None
)

# AgentCore session ids must be at least 33 characters. One session per Lambda
# container; a new MCP server deploy changes MCP_RUNTIME_VERSION, which replaces
# the containers and so the session (see infra/agent.tf).
_SESSION_ID = f"homedocs-v{os.environ.get('MCP_RUNTIME_VERSION', '0')}-{uuid.uuid4().hex}"


@asynccontextmanager
async def open_mcp() -> AsyncIterator[McpToolbox]:
    headers: dict[str, str] = {}
    if _tokens is not None:
        headers["Authorization"] = f"Bearer {await _tokens.get()}"
        headers["Mcp-Session-Id"] = _SESSION_ID
    async with open_toolbox(config.MCP_URL, headers) as toolbox:
        yield toolbox
