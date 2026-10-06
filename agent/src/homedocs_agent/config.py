"""Settings from environment variables."""

from __future__ import annotations

import os

MCP_URL = os.environ.get("MCP_URL", "http://127.0.0.1:8000/mcp")
MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
POLLY_VOICE = os.environ.get("POLLY_VOICE", "Joanna")
HOST = os.environ.get("AGENT_HOST", "127.0.0.1")
PORT = int(os.environ.get("AGENT_PORT", "8001"))
