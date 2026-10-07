# MCP server image for Amazon Bedrock AgentCore Runtime (requires linux/arm64).
# Build: docker buildx build --platform linux/arm64 -t <repo>:<tag> --push .
FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /bin/uv

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

# Dependencies first so code changes don't reinstall them.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-dev --no-install-project

COPY src ./src
COPY data/sample_documents.json ./data/
RUN uv sync --locked --no-dev

RUN useradd --create-home --uid 1000 app
USER app

# AgentCore expects the MCP endpoint at 0.0.0.0:8000/mcp.
ENV PATH="/app/.venv/bin:$PATH" \
    HOMEDOCS_HOST=0.0.0.0 \
    HOMEDOCS_PORT=8000 \
    HOMEDOCS_STORE=dynamodb \
    HOMEDOCS_SEARCH=s3vectors
EXPOSE 8000

CMD ["homedocs-mcp"]
