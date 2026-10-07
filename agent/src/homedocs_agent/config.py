"""Settings from environment variables."""

from __future__ import annotations

import os

MCP_URL = os.environ.get("MCP_URL", "http://127.0.0.1:8000/mcp")
# The global inference profile routes to any region with spare capacity, which avoids
# most ServiceUnavailableException errors from busy US regions.
MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "global.anthropic.claude-haiku-4-5-20251001-v1:0")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
POLLY_VOICE = os.environ.get("POLLY_VOICE", "Joanna")
# Set these to call the AgentCore-hosted MCP server (values from `terraform output`).
# Leave COGNITO_CLIENT_ID empty for a local MCP server without sign-in.
COGNITO_TOKEN_URL = os.environ.get("COGNITO_TOKEN_URL", "")
COGNITO_CLIENT_ID = os.environ.get("COGNITO_CLIENT_ID", "")
COGNITO_CLIENT_SECRET = os.environ.get("COGNITO_CLIENT_SECRET", "")
COGNITO_SCOPE = os.environ.get("COGNITO_SCOPE", "homedocs/mcp")
# On Lambda the client secret comes from Secrets Manager instead of an env var.
COGNITO_CLIENT_SECRET_ARN = os.environ.get("COGNITO_CLIENT_SECRET_ARN", "")

# Public deployment guards; both are off when empty (local development).
# DEMO_PASSCODE: the browser must send it in the X-Demo-Passcode header.
# ORIGIN_SECRET: CloudFront adds it as X-Origin-Verify, so calls that skip
# CloudFront and hit the Lambda function URL directly are rejected.
DEMO_PASSCODE = os.environ.get("DEMO_PASSCODE", "")
ORIGIN_SECRET = os.environ.get("ORIGIN_SECRET", "")
HOST = os.environ.get("AGENT_HOST", "127.0.0.1")
PORT = int(os.environ.get("AGENT_PORT", "8001"))
