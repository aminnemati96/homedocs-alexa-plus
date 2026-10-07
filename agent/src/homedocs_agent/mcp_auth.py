"""Access tokens for the AgentCore-hosted MCP server (Cognito client credentials).

Tokens last an hour; we reuse one until a minute before it expires.
"""

from __future__ import annotations

import time

import httpx


class CognitoTokens:
    def __init__(self, token_url: str, client_id: str, client_secret: str, scope: str):
        self._token_url = token_url
        self._auth = (client_id, client_secret)
        self._scope = scope
        self._token = ""
        self._expires_at = 0.0

    async def get(self) -> str:
        if time.time() < self._expires_at - 60:
            return self._token
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                self._token_url,
                auth=self._auth,
                data={"grant_type": "client_credentials", "scope": self._scope},
            )
        response.raise_for_status()
        body = response.json()
        self._token = body["access_token"]
        self._expires_at = time.time() + body["expires_in"]
        return self._token
